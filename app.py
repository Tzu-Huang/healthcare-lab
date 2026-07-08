from __future__ import annotations

import base64
import json
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix
try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional in minimal test envs
    def load_dotenv(*_args, **_kwargs):
        return False

from backend.lab_store import (
    DCM4CHEE_MWL_STATUS_CREATED,
    DCM4CHEE_MWL_STATUS_FAILED,
    DCM4CHEE_MWL_STATUS_PATIENT_MISSING,
    DCM4CHEE_MWL_STATUS_PENDING,
    DCM4CHEE_MWL_OPERATION_READBACK,
    DemoStore,
    LAB_OPERATION_ACTIONS,
    LAB_HEALTH_STATUSES,
    LAB_SERVER_PROTOCOLS,
    LAB_SERVER_TYPES,
    FHIR_SYNC_STATUS_FAILED,
    FHIR_SYNC_STATUS_PENDING,
    FHIR_SYNC_STATUS_SYNCED,
    OPENEMR_DEFAULT_ALLOWED_PROCEDURE_CODES,
    ORDER_STATUS_ACCEPTED,
    ORDER_STATUS_ERROR,
    ORDER_STATUS_REJECTED,
    ORDER_STATUS_TRANSPORT_ERROR,
    OpenEMRProcedureOrderSource,
    SimulatorValidationError,
    ensure_gdt_bridge_dirs,
    parse_openemr_allowed_procedure_codes,
    validate_gdt_bridge_dirs,
)
from backend.lab_operations import (
    DockerComposeLabOperationAdapter,
    DockerSocketLabOperationAdapter,
    LabOperationError,
)
from backend.dashboard_services import (
    LAB_DASHBOARD_SERVICE_GROUPS,
    collect_dashboard_resource_snapshot,
    dashboard_action_for_group,
    dashboard_health_rank,
    dashboard_servers_for_group,
    dashboard_summary,
    derive_dashboard_group_status,
)

MEDPLUM_DEFAULT_AUTH_GRACE_SECONDS = 300
MEDPLUM_INVENTORY_RESOURCE_TYPES = (
    "Patient",
    "ServiceRequest",
    "Task",
    "DiagnosticReport",
    "Observation",
    "DocumentReference",
)
MEDPLUM_READ_RESOURCE_TYPES = MEDPLUM_INVENTORY_RESOURCE_TYPES + ("Binary",)
MEDPLUM_PATIENT_REFERENCE_FIELDS = ("subject", "patient", "for")
DCM4CHEE_PROFILE_NAME = "local-dcm4chee"
DCM4CHEE_AUTH_MODES = ("none", "basic", "bearer", "oauth2", "mtls")

load_dotenv(Path(__file__).with_name(".env"))

DOCKER_COMPOSE_APPLICATION_URLS = {
    "oie": "http://oie:8080",
    "medplum": "http://medplum:8103/fhir/R4",
    "openemr": "http://openemr:80",
    "dcm4chee": "http://dcm4chee:8080/dcm4chee-arc/ui2",
}


class ValidationError(ValueError):
    pass


class UpstreamFhirError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        response_payload: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.http_status = http_status
        self.response_payload = response_payload or {}
        self.attempt_recorded = False


class UpstreamDcm4cheeError(RuntimeError):
    def __init__(self, message: str, *, http_status: int | None = None, response_body: str = "") -> None:
        super().__init__(message)
        self.http_status = http_status
        self.response_body = response_body


@dataclass(frozen=True)
class MedplumAccessToken:
    access_token: str
    expires_at: float


def derive_medplum_token_url(base_url: str, override: str = "") -> str:
    if override.strip():
        return normalize_fhir_base_url(override)
    parsed = urllib.parse.urlparse(normalize_fhir_base_url(base_url))
    if not parsed.scheme or not parsed.netloc:
        raise ValidationError("Medplum FHIR base URL must include scheme and host.")
    return f"{parsed.scheme}://{parsed.netloc}/oauth2/token"


class MedplumAuthManager:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        scope: str = "",
        token_url: str = "",
        refresh_grace_seconds: int = MEDPLUM_DEFAULT_AUTH_GRACE_SECONDS,
    ) -> None:
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.scope = scope.strip()
        self.token_url = token_url.strip()
        self.refresh_grace_seconds = max(0, int(refresh_grace_seconds))
        self._cache: dict[str, MedplumAccessToken] = {}
        self._lock = threading.Lock()

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def status(self, base_url: str = "") -> dict[str, Any]:
        configured = self.is_configured()
        token_endpoint = ""
        if configured and base_url.strip():
            try:
                token_endpoint = derive_medplum_token_url(base_url, self.token_url)
            except ValidationError:
                token_endpoint = ""
        return {
            "configured": configured,
            "clientIdSuffix": self.client_id[-4:] if configured and len(self.client_id) >= 4 else self.client_id,
            "tokenEndpoint": token_endpoint,
            "scope": self.scope,
        }

    def invalidate(self, base_url: str) -> None:
        token_url = derive_medplum_token_url(base_url, self.token_url)
        with self._lock:
            self._cache.pop(token_url, None)

    def get_access_token(self, base_url: str, *, force_refresh: bool = False) -> str:
        if not self.is_configured():
            raise ValidationError(
                "Medplum client credentials are not configured. "
                "Set MEDPLUM_CLIENT_ID and MEDPLUM_CLIENT_SECRET on the Flask server."
            )

        token_url = derive_medplum_token_url(base_url, self.token_url)
        now = time.time()
        with self._lock:
            cached = self._cache.get(token_url)
            if (
                cached
                and not force_refresh
                and (cached.expires_at - self.refresh_grace_seconds) > now
            ):
                return cached.access_token

        token = self._request_new_token(token_url)
        with self._lock:
            self._cache[token_url] = token
        return token.access_token

    def _request_new_token(self, token_url: str) -> MedplumAccessToken:
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        if self.scope:
            payload["scope"] = self.scope
        request_payload = urllib.parse.urlencode(payload).encode("utf-8")
        auth_bytes = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        basic_auth = base64.b64encode(auth_bytes).decode("ascii")
        api_request = urllib.request.Request(
            token_url,
            data=request_payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {basic_auth}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(api_request, timeout=15) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise UpstreamFhirError(
                f"Medplum token request returned HTTP {exc.code}: {error_body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise UpstreamFhirError(
                f"Medplum token request failed: {exc.reason}"
            ) from exc

        try:
            parsed_body = json.loads(response_body) if response_body else {}
        except json.JSONDecodeError as exc:
            raise UpstreamFhirError(
                "Medplum token request returned a non-JSON response."
            ) from exc

        access_token = str(parsed_body.get("access_token", "")).strip()
        token_type = str(parsed_body.get("token_type", "Bearer")).strip()
        expires_in = int(parsed_body.get("expires_in", 3600) or 3600)
        if not access_token:
            raise UpstreamFhirError(
                "Medplum token request did not return access_token."
            )
        if token_type.lower() != "bearer":
            raise UpstreamFhirError(
                f"Medplum token request returned unsupported token type: {token_type}"
            )
        return MedplumAccessToken(
            access_token=access_token,
            expires_at=time.time() + max(1, expires_in),
        )


def error_response(message: str, status_code: int):
    return jsonify({"success": False, "error": message}), status_code


def normalize_fhir_base_url(value: str) -> str:
    base_url = value.strip().rstrip("/")
    if not base_url:
        raise ValidationError("Medplum FHIR base URL is required.")
    if not base_url.startswith(("http://", "https://")):
        raise ValidationError("Medplum FHIR base URL must start with http:// or https://.")
    return base_url


def parse_config_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise ValidationError(f"Boolean config value is invalid: {value}")


def coerce_config_int(value: Any, *, default: int) -> int | str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    try:
        return int(text)
    except (TypeError, ValueError):
        return text


def coerce_config_bool(value: Any, *, default: bool) -> bool | str:
    try:
        return parse_config_bool(value, default=default)
    except ValidationError:
        return str(value).strip()


def require_http_url(value: Any, field: str) -> str:
    url = str(value or "").strip()
    if not url:
        raise ValidationError(f"{field} is required.")
    if not url.startswith(("http://", "https://")):
        raise ValidationError(f"{field} must start with http:// or https://.")
    return url.rstrip("/")


def dcm4chee_profile_from_config(config: dict[str, Any]) -> dict[str, Any]:
    profile_name = str(config.get("DCM4CHEE_PROFILE_NAME", DCM4CHEE_PROFILE_NAME) or "").strip()
    called_ae_title = str(config.get("DCM4CHEE_CALLED_AE_TITLE", "DCM4CHEE") or "").strip()
    dicomweb_base_url = str(
        config.get(
            "DCM4CHEE_DICOMWEB_BASE_URL",
            f"http://127.0.0.1:8082/dcm4chee-arc/aets/{called_ae_title or 'DCM4CHEE'}/rs",
        )
        or ""
    ).strip().rstrip("/")
    web_ui_url = str(
        config.get("DCM4CHEE_WEB_UI_URL", "http://127.0.0.1:8082/dcm4chee-arc/ui2") or ""
    ).strip().rstrip("/")
    qido_url = str(config.get("DCM4CHEE_QIDO_RS_URL") or dicomweb_base_url).strip().rstrip("/")
    wado_url = str(config.get("DCM4CHEE_WADO_RS_URL") or dicomweb_base_url).strip().rstrip("/")
    stow_url = str(config.get("DCM4CHEE_STOW_RS_URL") or dicomweb_base_url).strip().rstrip("/")
    viewer_url_template = (
        str(config.get("DCM4CHEE_VIEWER_STUDY_URL_TEMPLATE") or "").strip()
        or (f"{web_ui_url}/#/study/{{studyInstanceUid}}" if web_ui_url else "")
    )
    return {
        "profileName": profile_name,
        "displayName": str(config.get("DCM4CHEE_DISPLAY_NAME", "dcm4chee Local Archive") or "").strip(),
        "environmentName": str(config.get("DCM4CHEE_ENVIRONMENT_NAME", "local-docker") or "").strip(),
        "webUiUrl": web_ui_url,
        "dimse": {
            "host": str(config.get("DCM4CHEE_DIMSE_HOST", "127.0.0.1") or "").strip(),
            "port": coerce_config_int(config.get("DCM4CHEE_DIMSE_PORT"), default=11112),
            "calledAETitle": called_ae_title,
            "callingAETitle": str(
                config.get("DCM4CHEE_CALLING_AE_TITLE", "HEALTHCARE_LAB") or ""
            ).strip(),
        },
        "mwl": {
            "aeTitle": str(config.get("DCM4CHEE_MWL_AE_TITLE", called_ae_title) or "").strip(),
            "defaultScheduledStationAETitle": str(
                config.get("DCM4CHEE_DEFAULT_SCHEDULED_STATION_AE_TITLE", "ECG_AP") or ""
            ).strip(),
        },
        "dicomweb": {
            "baseUrl": dicomweb_base_url,
            "qidoRsUrl": qido_url,
            "wadoRsUrl": wado_url,
            "stowRsUrl": stow_url,
        },
        "viewer": {
            "studyUrlTemplate": viewer_url_template,
        },
        "security": {
            "authMode": str(config.get("DCM4CHEE_AUTH_MODE", "none") or "").strip().lower(),
            "tlsEnabled": coerce_config_bool(config.get("DCM4CHEE_TLS_ENABLED"), default=False),
            "tlsVerify": coerce_config_bool(config.get("DCM4CHEE_TLS_VERIFY"), default=True),
            "username": str(config.get("DCM4CHEE_USERNAME", "") or "").strip(),
            "tokenUrl": str(config.get("DCM4CHEE_TOKEN_URL", "") or "").strip(),
            "certificatePath": str(config.get("DCM4CHEE_CERTIFICATE_PATH", "") or "").strip(),
            "privateKeyPath": str(config.get("DCM4CHEE_PRIVATE_KEY_PATH", "") or "").strip(),
            "localLabOnly": str(config.get("DCM4CHEE_AUTH_MODE", "none") or "").strip().lower() == "none",
        },
    }


def validate_dcm4chee_profile(profile: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, str]] = []

    def add_check(name: str, field: str, ok: bool, message: str) -> None:
        checks.append(
            {
                "name": name,
                "field": field,
                "status": "Healthy" if ok else "Down",
                "message": message,
            }
        )

    def required_text(path: tuple[str, ...], label: str) -> str:
        value: Any = profile
        for part in path:
            value = value.get(part, {}) if isinstance(value, dict) else {}
        text = str(value or "").strip()
        add_check(
            "_".join(path),
            ".".join(path),
            bool(text),
            f"{label} is configured." if text else f"{label} is required.",
        )
        return text

    required_text(("profileName",), "Profile name")
    required_text(("displayName",), "Display name")
    required_text(("environmentName",), "Environment name")
    try:
        require_http_url(profile.get("webUiUrl"), "webUiUrl")
        add_check("web_ui_url", "webUiUrl", True, "Web UI URL is valid.")
    except ValidationError as exc:
        add_check("web_ui_url", "webUiUrl", False, str(exc))

    dimse = profile.get("dimse") if isinstance(profile.get("dimse"), dict) else {}
    required_text(("dimse", "host"), "DIMSE host")
    try:
        port = int(dimse.get("port") or 0)
        valid_port = 1 <= port <= 65535
    except (TypeError, ValueError):
        valid_port = False
    add_check(
        "dimse_port",
        "dimse.port",
        valid_port,
        "DIMSE port is valid." if valid_port else "DIMSE port must be an integer between 1 and 65535.",
    )
    required_text(("dimse", "calledAETitle"), "Called AE title")
    required_text(("dimse", "callingAETitle"), "Calling AE title")
    required_text(("mwl", "aeTitle"), "MWL AE title")
    required_text(("mwl", "defaultScheduledStationAETitle"), "Default Scheduled Station AE Title")

    dicomweb = profile.get("dicomweb") if isinstance(profile.get("dicomweb"), dict) else {}
    for field in ("baseUrl", "qidoRsUrl", "wadoRsUrl", "stowRsUrl"):
        try:
            require_http_url(dicomweb.get(field), f"dicomweb.{field}")
            add_check(f"dicomweb_{field}", f"dicomweb.{field}", True, f"DICOMweb {field} is valid.")
        except ValidationError as exc:
            add_check(f"dicomweb_{field}", f"dicomweb.{field}", False, str(exc))

    security = profile.get("security") if isinstance(profile.get("security"), dict) else {}
    auth_mode = str(security.get("authMode") or "").strip().lower()
    add_check(
        "security_auth_mode",
        "security.authMode",
        auth_mode in DCM4CHEE_AUTH_MODES,
        "Auth mode is supported." if auth_mode in DCM4CHEE_AUTH_MODES else "Auth mode is unsupported.",
    )
    tls_enabled_value = security.get("tlsEnabled")
    tls_verify_value = security.get("tlsVerify")
    add_check(
        "security_tls_enabled",
        "security.tlsEnabled",
        isinstance(tls_enabled_value, bool),
        "TLS enabled value is valid." if isinstance(tls_enabled_value, bool) else "TLS enabled must be true or false.",
    )
    add_check(
        "security_tls_verify",
        "security.tlsVerify",
        isinstance(tls_verify_value, bool),
        "TLS verify value is valid." if isinstance(tls_verify_value, bool) else "TLS verify must be true or false.",
    )
    tls_enabled = tls_enabled_value is True
    has_cert_material = bool(security.get("certificatePath") or security.get("privateKeyPath"))
    add_check(
        "security_tls",
        "security.certificatePath",
        tls_enabled or not has_cert_material,
        "TLS settings are consistent."
        if tls_enabled or not has_cert_material
        else "Certificate or key paths require TLS to be enabled.",
    )
    if auth_mode == "none":
        add_check(
            "security_local_lab",
            "security.authMode",
            True,
            "Local profile is unauthenticated and is not production-ready.",
        )

    valid = all(check["status"] == "Healthy" for check in checks)
    return {
        "valid": valid,
        "status": "Healthy" if valid else "Down",
        "summary": "dcm4chee profile is valid." if valid else "dcm4chee profile is incomplete or invalid.",
        "checks": checks,
    }


def current_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def hl7_message_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def request_fhir_raw(
    url: str,
    token: str,
    *,
    method: str,
    body: bytes,
    content_type: str,
    auth_manager: MedplumAuthManager | None = None,
    base_url: str = "",
) -> tuple[int, dict[str, Any], dict[str, str]]:
    def perform_request(access_token: str) -> tuple[int, dict[str, Any], dict[str, str]]:
        headers = {
            "Accept": "application/fhir+json, application/json",
            "Content-Type": content_type,
        }
        if access_token.strip():
            headers["Authorization"] = f"Bearer {access_token.strip()}"
        api_request = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(api_request, timeout=30) as response:
                response_body = response.read().decode("utf-8", errors="replace")
                status_code = response.status
                response_headers = dict(response.headers.items())
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise UpstreamFhirError(
                f"Medplum returned HTTP {exc.code}: {error_body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise UpstreamFhirError(f"Medplum request failed: {exc.reason}") from exc
        try:
            parsed_body = json.loads(response_body) if response_body else {}
        except json.JSONDecodeError:
            parsed_body = {"raw": response_body}
        return status_code, parsed_body, response_headers

    access_token = token.strip()
    if auth_manager is not None:
        access_token = auth_manager.get_access_token(base_url or url)

    try:
        return perform_request(access_token)
    except UpstreamFhirError as exc:
        if (
            auth_manager is None
            or "Medplum returned HTTP 401:" not in str(exc)
        ):
            raise
        auth_manager.invalidate(base_url or url)
        refreshed_token = auth_manager.get_access_token(base_url or url, force_refresh=True)
        return perform_request(refreshed_token)


def request_dcm4chee_mwl_create(
    profile: dict[str, Any],
    payload: dict[str, Any],
) -> tuple[int, str, str]:
    dicomweb = profile.get("dicomweb") if isinstance(profile.get("dicomweb"), dict) else {}
    base_url = require_http_url(dicomweb.get("baseUrl"), "dicomweb.baseUrl")
    url = f"{base_url}/mwlitems"
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    headers = {
        "Accept": "application/dicom+json, application/json, text/plain",
        "Content-Type": "application/dicom+json",
    }
    api_request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(api_request, timeout=30) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            return response.status, response_body, url
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise UpstreamDcm4cheeError(
            f"dcm4chee returned HTTP {exc.code}: {error_body}",
            http_status=exc.code,
            response_body=error_body,
        ) from exc
    except urllib.error.URLError as exc:
        raise UpstreamDcm4cheeError(f"dcm4chee request failed: {exc.reason}") from exc


def request_dcm4chee_mwl_readback(
    profile: dict[str, Any],
    identifiers: dict[str, str],
) -> tuple[int, str, str]:
    dicomweb = profile.get("dicomweb") if isinstance(profile.get("dicomweb"), dict) else {}
    base_url = require_http_url(dicomweb.get("baseUrl"), "dicomweb.baseUrl")
    query = {
        key: value
        for key, value in {
            "StudyInstanceUID": identifiers.get("study_instance_uid", ""),
            "AccessionNumber": identifiers.get("accession_number", ""),
            "RequestedProcedureID": identifiers.get("requested_procedure_id", ""),
            "ScheduledProcedureStepID": identifiers.get("scheduled_procedure_step_id", ""),
            "PatientID": identifiers.get("patient_id", ""),
            "IssuerOfPatientID": identifiers.get("issuer_of_patient_id", ""),
        }.items()
        if value
    }
    url = f"{base_url}/mwlitems"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    headers = {"Accept": "application/dicom+json, application/json, text/plain"}
    api_request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(api_request, timeout=30) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            return response.status, response_body, url
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise UpstreamDcm4cheeError(
            f"dcm4chee read-back returned HTTP {exc.code}: {error_body}",
            http_status=exc.code,
            response_body=error_body,
        ) from exc
    except urllib.error.URLError as exc:
        raise UpstreamDcm4cheeError(f"dcm4chee read-back failed: {exc.reason}") from exc


def sync_order_to_dcm4chee_mwl(
    store: DemoStore,
    order: dict[str, Any],
    profile: dict[str, Any],
    *,
    uid_root: str,
) -> dict[str, Any]:
    diagnostics = validate_dcm4chee_profile(profile)
    dicomweb = profile.get("dicomweb") if isinstance(profile.get("dicomweb"), dict) else {}
    base_url = str(dicomweb.get("baseUrl") or "").strip().rstrip("/")
    request_url = f"{base_url}/mwlitems" if base_url else ""
    if not diagnostics["valid"]:
        return store.create_dcm4chee_mwl_profile_failure_attempt(
            int(order["id"]),
            profile,
            uid_root=uid_root,
            request_url=request_url,
            diagnostics=diagnostics,
        )
    payload = store.build_dcm4chee_mwl_payload(order, profile, uid_root=uid_root)
    existing_mapping = store.get_dcm4chee_mwl_mapping_for_order(int(order["id"]))
    if existing_mapping and existing_mapping.get("status") == DCM4CHEE_MWL_STATUS_CREATED:
        return existing_mapping
    if existing_mapping:
        readback_attempt = store.create_dcm4chee_mwl_attempt(
            int(order["id"]),
            profile,
            uid_root=uid_root,
            request_url=request_url,
            request_payload=payload,
            operation_type=DCM4CHEE_MWL_OPERATION_READBACK,
            mapping_id=int(existing_mapping["id"]),
        )
        try:
            readback_status, readback_body, _readback_url = request_dcm4chee_mwl_readback(
                profile,
                {
                    "study_instance_uid": existing_mapping.get("studyInstanceUid", ""),
                    "accession_number": existing_mapping.get("accessionNumber", ""),
                    "requested_procedure_id": existing_mapping.get("requestedProcedureId", ""),
                    "scheduled_procedure_step_id": existing_mapping.get("scheduledProcedureStepId", ""),
                    "patient_id": existing_mapping.get("patientId", ""),
                    "issuer_of_patient_id": existing_mapping.get("issuerOfPatientId", ""),
                },
            )
            readback_identifiers = store.dcm4chee_identifiers_from_response_body(readback_body)
            try:
                readback_payload = json.loads(readback_body) if readback_body else {}
            except json.JSONDecodeError:
                readback_payload = {"raw": readback_body}
            readback_status_text = (
                DCM4CHEE_MWL_STATUS_CREATED if readback_identifiers else DCM4CHEE_MWL_STATUS_FAILED
            )
            readback_error = "" if readback_identifiers else "dcm4chee read-back returned no identifiers."
            updated_readback_attempt = store.update_dcm4chee_mwl_attempt_result(
                int(readback_attempt["id"]),
                attempt_status=readback_status_text,
                http_status=readback_status,
                response_body=readback_body,
                error_type="" if readback_identifiers else "dcm4chee_readback_empty",
                error_text=readback_error,
            )
            store.update_dcm4chee_mwl_mapping_from_attempt(
                int(order["id"]),
                attempt_id=int(updated_readback_attempt["id"]),
                sync_status=readback_status_text,
                http_status=readback_status,
                response_body=readback_body,
                error_type=updated_readback_attempt["errorType"],
                error_text=updated_readback_attempt["error"],
                error_payload={} if readback_identifiers else {"responseBody": readback_body},
                readback_payload=readback_payload,
                identifiers=readback_identifiers,
            )
            if readback_identifiers:
                return updated_readback_attempt
        except UpstreamDcm4cheeError as exc:
            updated_readback_attempt = store.update_dcm4chee_mwl_attempt_result(
                int(readback_attempt["id"]),
                attempt_status=DCM4CHEE_MWL_STATUS_FAILED,
                http_status=exc.http_status,
                response_body=exc.response_body,
                error_type="dcm4chee_readback_failed",
                error_text=str(exc),
            )
            store.update_dcm4chee_mwl_mapping_from_attempt(
                int(order["id"]),
                attempt_id=int(updated_readback_attempt["id"]),
                sync_status=DCM4CHEE_MWL_STATUS_FAILED,
                http_status=exc.http_status,
                response_body=exc.response_body,
                error_type=updated_readback_attempt["errorType"],
                error_text=updated_readback_attempt["error"],
                error_payload={"responseBody": exc.response_body},
            )
    mapping = store.upsert_dcm4chee_mwl_mapping(
        int(order["id"]),
        profile,
        uid_root=uid_root,
        request_payload=payload,
        sync_status=DCM4CHEE_MWL_STATUS_PENDING,
        increment_retry=existing_mapping is not None,
    )
    attempt = store.create_dcm4chee_mwl_attempt(
        int(order["id"]),
        profile,
        uid_root=uid_root,
        request_url=request_url,
        request_payload=payload,
        mapping_id=int(mapping["id"]),
    )
    try:
        status, response_body, actual_url = request_dcm4chee_mwl_create(profile, payload)
    except UpstreamDcm4cheeError as exc:
        response_body = exc.response_body
        lower_body = response_body.lower()
        is_patient_missing = exc.http_status == 404 and "patient" in lower_body and "exist" in lower_body
        updated_attempt = store.update_dcm4chee_mwl_attempt_result(
            int(attempt["id"]),
            attempt_status=DCM4CHEE_MWL_STATUS_PATIENT_MISSING if is_patient_missing else DCM4CHEE_MWL_STATUS_FAILED,
            http_status=exc.http_status,
            response_body=response_body,
            error_type="patient_missing" if is_patient_missing else "dcm4chee_request_failed",
            error_text=str(exc),
        )
        store.update_dcm4chee_mwl_mapping_from_attempt(
            int(order["id"]),
            attempt_id=int(updated_attempt["id"]),
            sync_status=updated_attempt["status"],
            http_status=exc.http_status,
            response_body=response_body,
            error_type=updated_attempt["errorType"],
            error_text=updated_attempt["error"],
            error_payload={"responseBody": response_body},
        )
        return updated_attempt
    if actual_url != attempt["requestUrl"]:
        request_url = actual_url
    response_identifiers = store.dcm4chee_identifiers_from_response_body(response_body)
    readback_payload: dict[str, Any] | list[Any] | None = None
    readback_identifiers: dict[str, str] = {}
    readback_error_type = ""
    readback_error_text = ""
    try:
        readback_status, readback_body, _readback_url = request_dcm4chee_mwl_readback(
            profile,
            {
                **store.dcm4chee_identifiers_from_payload(order, profile, uid_root=uid_root, payload=payload),
                **response_identifiers,
            },
        )
        try:
            readback_payload = json.loads(readback_body) if readback_body else {}
        except json.JSONDecodeError:
            readback_payload = {"raw": readback_body}
        readback_identifiers = store.dcm4chee_identifiers_from_response_body(readback_body)
    except UpstreamDcm4cheeError as exc:
        readback_status = exc.http_status
        readback_error_type = "dcm4chee_readback_failed"
        readback_error_text = str(exc)
        readback_payload = {"responseBody": exc.response_body}
    updated_attempt = store.update_dcm4chee_mwl_attempt_result(
        int(attempt["id"]),
        attempt_status=DCM4CHEE_MWL_STATUS_CREATED,
        http_status=status,
        response_body=response_body,
        error_type=readback_error_type,
        error_text=readback_error_text,
    )
    store.update_dcm4chee_mwl_mapping_from_attempt(
        int(order["id"]),
        attempt_id=int(updated_attempt["id"]),
        sync_status=DCM4CHEE_MWL_STATUS_CREATED,
        http_status=status,
        response_body=response_body,
        error_type=readback_error_type,
        error_text=readback_error_text,
        error_payload=readback_payload if readback_error_type else {},
        readback_payload=readback_payload,
        identifiers={**response_identifiers, **readback_identifiers},
    )
    return updated_attempt


def request_fhir_json(
    url: str,
    token: str,
    method: str = "GET",
    body: bytes | None = None,
    content_type: str | None = None,
    *,
    auth_manager: MedplumAuthManager | None = None,
    base_url: str = "",
) -> tuple[int, dict[str, Any]]:
    def perform_request(access_token: str) -> tuple[int, dict[str, Any]]:
        headers = {
            "Accept": "application/fhir+json, application/json",
        }
        if content_type:
            headers["Content-Type"] = content_type
        if access_token.strip():
            headers["Authorization"] = f"Bearer {access_token.strip()}"
        api_request = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(api_request, timeout=15) as response:
                response_body = response.read().decode("utf-8")
                status_code = response.status
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            try:
                error_payload = json.loads(error_body) if error_body else {}
            except json.JSONDecodeError:
                error_payload = {"raw": error_body}
            raise UpstreamFhirError(
                f"Medplum returned HTTP {exc.code}: {error_body}",
                http_status=exc.code,
                response_payload=error_payload,
            ) from exc
        except urllib.error.URLError as exc:
            raise UpstreamFhirError(f"Medplum request failed: {exc.reason}") from exc
        try:
            parsed_body = json.loads(response_body) if response_body else {}
        except json.JSONDecodeError:
            parsed_body = {"raw": response_body}
        return status_code, parsed_body

    access_token = token.strip()
    if auth_manager is not None:
        access_token = auth_manager.get_access_token(base_url or url)

    try:
        return perform_request(access_token)
    except UpstreamFhirError as exc:
        if (
            auth_manager is None
            or "Medplum returned HTTP 401:" not in str(exc)
        ):
            raise
        auth_manager.invalidate(base_url or url)
        refreshed_token = auth_manager.get_access_token(base_url or url, force_refresh=True)
        return perform_request(refreshed_token)


def fetch_fhir_service_requests(
    base_url: str,
    token: str,
    *,
    auth_manager: MedplumAuthManager | None = None,
) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        [
            ("_count", 20),
            ("_sort", "-_lastUpdated"),
            ("_include", "ServiceRequest:subject"),
            ("_include", "ServiceRequest:encounter"),
            ("_include", "ServiceRequest:requester"),
            ("_include", "ServiceRequest:performer"),
        ]
    )
    url = f"{base_url}/ServiceRequest?{query}"
    status_code, parsed_body = request_fhir_json(
        url, token, auth_manager=auth_manager, base_url=base_url
    )
    return {
        "resourceType": str(parsed_body.get("resourceType", "")).strip() or "Bundle",
        "status": status_code,
        "body": parsed_body,
        "requestUrl": url,
    }


def normalize_fhir_reference(value: str, resource_type: str) -> str:
    reference = value.strip()
    parts = [part.strip() for part in reference.split("/") if part.strip()]
    if len(parts) != 2 or parts[0] != resource_type:
        raise ValidationError(f"FHIR reference must look like {resource_type}/id.")
    return f"{resource_type}/{parts[1]}"


def fhir_bundle_resources(bundle: dict[str, Any], resource_type: str) -> list[dict[str, Any]]:
    if bundle.get("resourceType") != "Bundle":
        raise UpstreamFhirError(
            f"Medplum {resource_type} search returned a non-Bundle response.",
            response_payload=bundle,
        )
    entries = bundle.get("entry") or []
    if not isinstance(entries, list):
        raise UpstreamFhirError(
            f"Medplum {resource_type} Bundle entry is malformed.",
            response_payload=bundle,
        )
    resources: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource")
        if isinstance(resource, dict) and resource.get("resourceType") == resource_type:
            resources.append(resource)
    return resources


def service_request_references(references: list[str]) -> list[str]:
    return [reference for reference in references if reference.startswith("ServiceRequest/")]


def diagnostic_report_effective_date(resource: dict[str, Any]) -> str:
    effective = str(resource.get("effectiveDateTime") or "").strip()
    if effective:
        return effective
    effective_period = resource.get("effectivePeriod")
    if isinstance(effective_period, dict):
        return str(
            effective_period.get("start")
            or effective_period.get("end")
            or ""
        ).strip()
    return str(resource.get("issued") or "").strip()


def attachment_reference_values(value: Any) -> list[str]:
    references: list[str] = []
    if isinstance(value, dict):
        url = str(value.get("url") or "").strip()
        if url and re.match(r"^[A-Za-z]+/[A-Za-z0-9\-.]+$", url):
            references.append(url)
        for nested in value.values():
            for reference in attachment_reference_values(nested):
                if reference not in references:
                    references.append(reference)
    elif isinstance(value, list):
        for item in value:
            for reference in attachment_reference_values(item):
                if reference not in references:
                    references.append(reference)
    return references


def diagnostic_report_relationships(resource: dict[str, Any]) -> dict[str, Any]:
    media_references: list[str] = []
    for item in resource.get("media") or []:
        if isinstance(item, dict):
            media_references.extend(fhir_reference_values(item.get("link")))
    presented_form = resource.get("presentedForm") if isinstance(resource.get("presentedForm"), list) else []
    presented_form_references = attachment_reference_values(presented_form)
    related_references: list[dict[str, str]] = []
    for reference in all_fhir_references(resource) + presented_form_references:
        resource_type = reference.split("/", 1)[0] if "/" in reference else ""
        if resource_type not in {"Observation", "DocumentReference", "Binary"}:
            continue
        if any(item["reference"] == reference for item in related_references):
            continue
        related_references.append({"resourceType": resource_type, "reference": reference})
    return {
        "subject": fhir_reference_values(resource.get("subject")),
        "basedOn": fhir_reference_values(resource.get("basedOn")),
        "result": fhir_reference_values(resource.get("result")),
        "media": media_references,
        "presentedForm": presented_form_references,
        "related": related_references,
    }


def diagnostic_report_summary(
    resource: dict[str, Any],
    *,
    selected_service_request: str = "",
) -> dict[str, Any]:
    resource_id = str(resource.get("id") or "").strip()
    reference = f"DiagnosticReport/{resource_id}" if resource_id else ""
    relationships = diagnostic_report_relationships(resource)
    based_on = relationships["basedOn"]
    service_refs = service_request_references(based_on)
    result_refs = relationships["result"]
    attachment_count = len(relationships["media"]) + len(relationships["presentedForm"])
    relationship_type = (
        "order-linked"
        if service_refs and (not selected_service_request or selected_service_request in service_refs)
        else "patient-level"
    )
    return {
        "id": resource_id,
        "reference": reference,
        "resourceType": "DiagnosticReport",
        "code": first_code_text(resource.get("code")),
        "display": first_code_text(resource.get("code")) or reference or "DiagnosticReport",
        "status": str(resource.get("status") or "").strip(),
        "date": diagnostic_report_effective_date(resource),
        "issued": str(resource.get("issued") or "").strip(),
        "subject": relationships["subject"][0] if relationships["subject"] else "",
        "basedOn": based_on,
        "linkedOrder": service_refs[0] if service_refs else "",
        "relationshipType": relationship_type,
        "resultCount": len(result_refs),
        "attachmentCount": attachment_count,
        "relationships": relationships,
        "resource": resource,
    }


def fetch_fhir_diagnostic_report_bundle(
    base_url: str,
    token: str,
    *,
    patient_reference: str = "",
    service_request_reference: str = "",
    auth_manager: MedplumAuthManager | None = None,
) -> dict[str, Any]:
    base = normalize_fhir_base_url(base_url)
    patient_ref = normalize_fhir_reference(patient_reference, "Patient") if patient_reference else ""
    service_ref = (
        normalize_fhir_reference(service_request_reference, "ServiceRequest")
        if service_request_reference
        else ""
    )
    if not patient_ref and not service_ref:
        raise ValidationError("Patient or ServiceRequest reference is required.")

    def search(params: list[tuple[str, str]]) -> dict[str, Any]:
        query = urllib.parse.urlencode([("_count", "50"), ("_sort", "-date"), *params])
        url = f"{base}/DiagnosticReport?{query}"
        status_code, parsed_body = request_fhir_json(
            url, token, auth_manager=auth_manager, base_url=base
        )
        fhir_bundle_resources(parsed_body, "DiagnosticReport")
        return {"status": status_code, "body": parsed_body, "requestUrl": url}

    patient_fetch: dict[str, Any] | None = None
    patient_reports: list[dict[str, Any]] = []
    based_on_fetch: dict[str, Any] | None = None
    fallback_reason = ""
    report_resources: list[dict[str, Any]] = []
    strategy = "patient"

    def fetch_patient_reports(*, optional: bool = False) -> list[dict[str, Any]]:
        nonlocal patient_fetch, fallback_reason
        if not patient_ref:
            return []
        try:
            patient_fetch = search([("subject", patient_ref)])
            return fhir_bundle_resources(patient_fetch["body"], "DiagnosticReport")
        except UpstreamFhirError as exc:
            if not optional or exc.http_status not in {400, 404, 422}:
                raise
            fallback_reason = str(exc)
            return []

    if service_ref:
        try:
            based_on_fetch = search([("based-on", service_ref)])
            order_reports = fhir_bundle_resources(based_on_fetch["body"], "DiagnosticReport")
            patient_reports = fetch_patient_reports(optional=True)
            patient_level_reports = [
                item for item in patient_reports
                if not service_request_references(fhir_reference_values(item.get("basedOn")))
            ]
            by_reference: dict[str, dict[str, Any]] = {}
            for item in order_reports + patient_level_reports:
                item_id = str(item.get("id") or "").strip()
                key = f"DiagnosticReport/{item_id}" if item_id else json.dumps(item, sort_keys=True)
                by_reference[key] = item
            report_resources = list(by_reference.values())
            strategy = "based-on"
        except UpstreamFhirError as exc:
            if exc.http_status not in {400, 404, 422}:
                raise
            fallback_reason = str(exc)
            patient_reports = fetch_patient_reports()
            report_resources = [
                item for item in patient_reports
                if service_ref in fhir_reference_values(item.get("basedOn"))
                or not service_request_references(fhir_reference_values(item.get("basedOn")))
            ]
            strategy = "patient-filter"
    else:
        patient_reports = fetch_patient_reports()
        report_resources = patient_reports

    summaries = [
        diagnostic_report_summary(item, selected_service_request=service_ref)
        for item in report_resources
    ]
    return {
        "resourceType": "Bundle",
        "status": patient_fetch["status"] if patient_fetch else based_on_fetch["status"],
        "requestUrl": patient_fetch["requestUrl"] if patient_fetch else based_on_fetch["requestUrl"],
        "patientReference": patient_ref,
        "serviceRequestReference": service_ref,
        "strategy": strategy,
        "fallbackReason": fallback_reason,
        "empty": not summaries,
        "body": patient_fetch["body"] if patient_fetch else based_on_fetch["body"],
        "bundles": {
            "patient": patient_fetch,
            "basedOn": based_on_fetch,
        },
        "reports": summaries,
    }


def operation_outcome_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict) and payload.get("resourceType") == "OperationOutcome":
        return payload
    return {}


def operation_outcome_from_error(message: str) -> dict[str, Any]:
    _, _, body = message.partition(": ")
    if not body:
        return {}
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return {}
    return operation_outcome_from_payload(parsed)


def http_status_from_upstream_error(message: str) -> int | None:
    match = re.search(r"HTTP\s+(\d+)", message)
    return int(match.group(1)) if match else None


def medplum_identifier_search_url(base_url: str, record: dict[str, Any]) -> str:
    identifier = record["identifier"]
    token = f"{identifier['system']}|{identifier['value']}"
    query = urllib.parse.urlencode({"identifier": token})
    return f"{base_url}/{record['resourceType']}?{query}"


def medplum_create_resource_url(base_url: str, record: dict[str, Any]) -> str:
    return f"{base_url}/{record['resourceType']}"


def medplum_update_resource_url(base_url: str, record: dict[str, Any], resource_id: str) -> str:
    return f"{base_url}/{record['resourceType']}/{urllib.parse.quote(resource_id, safe='')}"


def medplum_reference_resource_url(base_url: str, reference: str) -> str:
    parts = [part.strip() for part in reference.strip().split("/") if part.strip()]
    if len(parts) != 2:
        raise ValidationError("Medplum resource reference must look like ResourceType/id.")
    resource_type, resource_id = parts
    if resource_type not in MEDPLUM_READ_RESOURCE_TYPES:
        raise ValidationError("Medplum resource reference type is not supported.")
    return (
        f"{base_url}/{urllib.parse.quote(resource_type, safe='')}/"
        f"{urllib.parse.quote(resource_id, safe='')}"
    )


def fhir_reference_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, dict):
        reference = str(value.get("reference") or "").strip()
        return [reference] if reference else []
    if isinstance(value, list):
        references: list[str] = []
        for item in value:
            references.extend(fhir_reference_values(item))
        return references
    return []


def direct_patient_references(resource: dict[str, Any]) -> list[str]:
    references: list[str] = []
    for field_name in MEDPLUM_PATIENT_REFERENCE_FIELDS:
        for reference in fhir_reference_values(resource.get(field_name)):
            if reference.startswith("Patient/") and reference not in references:
                references.append(reference)
    return references


def all_fhir_references(value: Any) -> list[str]:
    references: list[str] = []
    if isinstance(value, dict):
        reference = str(value.get("reference") or "").strip()
        if reference and reference not in references:
            references.append(reference)
        for nested in value.values():
            for nested_reference in all_fhir_references(nested):
                if nested_reference not in references:
                    references.append(nested_reference)
    elif isinstance(value, list):
        for item in value:
            for nested_reference in all_fhir_references(item):
                if nested_reference not in references:
                    references.append(nested_reference)
    return references


def first_code_text(value: Any) -> str:
    if isinstance(value, dict):
        text = str(value.get("text") or "").strip()
        if text:
            return text
        coding = value.get("coding")
        if isinstance(coding, list):
            for item in coding:
                if not isinstance(item, dict):
                    continue
                display = str(item.get("display") or item.get("code") or "").strip()
                if display:
                    return display
    return ""


def fhir_resource_summary(resource: dict[str, Any], reference: str) -> dict[str, str]:
    resource_type = str(resource.get("resourceType") or "").strip()
    status = str(resource.get("status") or "").strip()
    code = first_code_text(resource.get("code"))
    title = str(resource.get("title") or resource.get("description") or "").strip()
    if resource_type == "Patient":
        names = resource.get("name") if isinstance(resource.get("name"), list) else []
        name = ""
        for item in names:
            if not isinstance(item, dict):
                continue
            name = str(item.get("text") or "").strip()
            if not name:
                given = " ".join(str(value).strip() for value in item.get("given") or [] if str(value).strip())
                family = str(item.get("family") or "").strip()
                name = " ".join(value for value in (given, family) if value)
            if name:
                break
        identifiers = resource.get("identifier") if isinstance(resource.get("identifier"), list) else []
        mrn = ""
        for item in identifiers:
            if isinstance(item, dict) and str(item.get("value") or "").strip():
                mrn = str(item.get("value")).strip()
                break
        return {"primary": name or mrn or reference or "Patient", "secondary": mrn, "status": status}
    if resource_type == "Task":
        return {"primary": code or title or reference or "Task", "secondary": str(resource.get("intent") or "").strip(), "status": status}
    if resource_type == "DiagnosticReport":
        return {
            "primary": code or title or reference or "DiagnosticReport",
            "secondary": str(resource.get("issued") or resource.get("effectiveDateTime") or "").strip(),
            "status": status,
        }
    if resource_type == "Observation":
        value = ""
        if "valueQuantity" in resource and isinstance(resource["valueQuantity"], dict):
            quantity = resource["valueQuantity"]
            value = " ".join(
                str(part).strip()
                for part in (quantity.get("value"), quantity.get("unit") or quantity.get("code"))
                if str(part or "").strip()
            )
        return {"primary": code or reference or "Observation", "secondary": value, "status": status}
    if resource_type == "DocumentReference":
        return {"primary": title or code or reference or "DocumentReference", "secondary": str(resource.get("docStatus") or "").strip(), "status": status}
    return {"primary": code or title or reference or resource_type, "secondary": "", "status": status}


def medplum_inventory_record(record: dict[str, Any]) -> dict[str, Any]:
    sync_status = str((record.get("sync") or {}).get("status") or "")
    medplum = record.get("medplum") or {}
    reference = str(medplum.get("reference") or "").strip()
    resource = record.get("resource") if isinstance(record.get("resource"), dict) else {}
    patient_references = direct_patient_references(resource)
    if record.get("resourceType") == "Patient" and reference and reference not in patient_references:
        patient_references.insert(0, reference)
    references = all_fhir_references(resource)
    return {
        "id": record["id"],
        "localFhirRecordNumber": record["localFhirRecordNumber"],
        "localSourceType": record["localSourceType"],
        "localSourceId": record["localSourceId"],
        "resourceType": record["resourceType"],
        "identifier": record["identifier"],
        "patientReferences": patient_references,
        "references": references,
        "summary": fhir_resource_summary(resource, reference),
        "medplum": medplum,
        "sync": record["sync"],
        "createdAt": record["createdAt"],
        "updatedAt": record["updatedAt"],
        "retryable": sync_status in (FHIR_SYNC_STATUS_PENDING, FHIR_SYNC_STATUS_FAILED),
        "previewSource": (
            "medplum-live"
            if sync_status == FHIR_SYNC_STATUS_SYNCED and reference
            else "local-submitted"
        ),
    }


def first_fhir_bundle_resource(bundle: dict[str, Any], resource_type: str) -> dict[str, Any] | None:
    if bundle.get("resourceType") != "Bundle":
        return None
    for entry in bundle.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource")
        if isinstance(resource, dict) and resource.get("resourceType") == resource_type:
            return resource
    return None


def medplum_resource_reference(resource: dict[str, Any], resource_type: str) -> tuple[str, str]:
    resource_id = str(resource.get("id") or "").strip()
    if not resource_id:
        raise UpstreamFhirError(f"Medplum {resource_type} response did not include an id.")
    return resource_id, f"{resource_type}/{resource_id}"


def sync_fhir_workflow_record_to_medplum(
    store: DemoStore,
    record_id: int,
    *,
    base_url: str,
    auth_manager: MedplumAuthManager,
) -> dict[str, Any]:
    base = normalize_fhir_base_url(base_url)
    current_record = store.get_fhir_workflow_record(record_id)
    original_sync_status = current_record.get("sync", {}).get("status")
    record = store.mark_fhir_syncing(record_id)
    search_url = medplum_identifier_search_url(base, record)

    def sync_request(
        request_url: str,
        *,
        method: str,
        request_payload: dict[str, Any] | None = None,
        body: bytes | None = None,
        content_type: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        try:
            return request_fhir_json(
                request_url,
                "",
                method=method,
                body=body,
                content_type=content_type,
                auth_manager=auth_manager,
                base_url=base,
            )
        except (UpstreamFhirError, ValidationError, SimulatorValidationError) as exc:
            message = str(exc)
            response_payload = (
                exc.response_payload if isinstance(exc, UpstreamFhirError) else {}
            )
            http_status = (
                exc.http_status
                if isinstance(exc, UpstreamFhirError)
                else http_status_from_upstream_error(message)
            )
            outcome = (
                operation_outcome_from_payload(response_payload)
                or operation_outcome_from_error(message)
            )
            store.record_fhir_sync_attempt(
                record_id,
                method=method,
                request_url=request_url,
                request_payload=request_payload or {},
                http_status=http_status,
                response_payload=response_payload,
                operation_outcome=outcome,
                error_text=message,
            )
            if isinstance(exc, UpstreamFhirError):
                exc.attempt_recorded = True
            else:
                setattr(exc, "attempt_recorded", True)
            raise

    try:
        status_code, search_body = sync_request(
            search_url,
            method="GET",
        )
        store.record_fhir_sync_attempt(
            record_id,
            method="GET",
            request_url=search_url,
            http_status=status_code,
            response_payload=search_body,
            operation_outcome=operation_outcome_from_payload(search_body),
        )
        existing = first_fhir_bundle_resource(search_body, record["resourceType"])
        if existing:
            medplum_id, reference = medplum_resource_reference(existing, record["resourceType"])
            return store.mark_fhir_sync_success(
                record_id,
                medplum_resource_id=medplum_id,
                medplum_resource_reference=reference,
            )

        stored_medplum = record.get("medplum") or {}
        stored_medplum_id = str(stored_medplum.get("id") or "").strip()
        if stored_medplum_id:
            if original_sync_status == FHIR_SYNC_STATUS_SYNCED:
                return store.mark_fhir_sync_success(
                    record_id,
                    medplum_resource_id=stored_medplum_id,
                    medplum_resource_reference=str(stored_medplum.get("reference") or "").strip(),
                )
            update_payload = dict(record["resource"])
            update_payload["id"] = stored_medplum_id
            update_url = medplum_update_resource_url(base, record, stored_medplum_id)
            update_status, update_body = sync_request(
                update_url,
                method="PUT",
                request_payload=update_payload,
                body=json.dumps(update_payload).encode("utf-8"),
                content_type="application/fhir+json",
            )
            store.record_fhir_sync_attempt(
                record_id,
                method="PUT",
                request_url=update_url,
                request_payload=update_payload,
                http_status=update_status,
                response_payload=update_body,
                operation_outcome=operation_outcome_from_payload(update_body),
            )
            medplum_id, reference = medplum_resource_reference(update_body, record["resourceType"])
            return store.mark_fhir_sync_success(
                record_id,
                medplum_resource_id=medplum_id,
                medplum_resource_reference=reference,
            )

        create_url = medplum_create_resource_url(base, record)
        request_payload = record["resource"]
        create_status, create_body = sync_request(
            create_url,
            method="POST",
            request_payload=request_payload,
            body=json.dumps(request_payload).encode("utf-8"),
            content_type="application/fhir+json",
        )
        store.record_fhir_sync_attempt(
            record_id,
            method="POST",
            request_url=create_url,
            request_payload=request_payload,
            http_status=create_status,
            response_payload=create_body,
            operation_outcome=operation_outcome_from_payload(create_body),
        )
        medplum_id, reference = medplum_resource_reference(create_body, record["resourceType"])
        return store.mark_fhir_sync_success(
            record_id,
            medplum_resource_id=medplum_id,
            medplum_resource_reference=reference,
        )
    except (UpstreamFhirError, ValidationError, SimulatorValidationError) as exc:
        message = str(exc)
        outcome = operation_outcome_from_error(message)
        if not getattr(exc, "attempt_recorded", False):
            store.record_fhir_sync_attempt(
                record_id,
                method="SYNC",
                request_url=search_url,
                request_payload=record.get("resource") or {},
                http_status=http_status_from_upstream_error(message),
                operation_outcome=outcome,
                error_text=message,
            )
        return store.mark_fhir_sync_failure(
            record_id,
            error_text=message,
            operation_outcome=outcome,
        )


def derive_lab_overall_status(checks: dict[str, str]) -> str:
    values = [checks.get(level, "Unknown") for level in ("process", "application", "protocol")]
    known = [value for value in values if value != "Unknown"]
    if not known:
        return "Unknown"
    if "Down" in known:
        return "Down"
    if "Degraded" in known or len(known) != len(values):
        return "Degraded"
    return "Healthy"


def run_lab_application_check(
    server: dict[str, Any], timeout_seconds: float = 2.0
) -> tuple[str, str]:
    base_url = str(server.get("baseUrl") or "").strip()
    operation = server.get("operation") or {}
    backing_service = str(operation.get("backingService") or "").strip()
    urls = []
    if (
        operation.get("controlType") == "docker-compose"
        and backing_service in DOCKER_COMPOSE_APPLICATION_URLS
    ):
        urls.append(DOCKER_COMPOSE_APPLICATION_URLS[backing_service])
    if base_url and base_url not in urls:
        urls.append(base_url)
    host = str(server.get("host") or "").strip()
    port = server.get("port")
    last_error = ""
    for url in urls:
        try:
            request_obj = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(request_obj, timeout=timeout_seconds) as response:
                if 200 <= int(response.status) < 500:
                    return "Healthy", ""
                return "Down", f"HTTP {response.status}"
        except urllib.error.HTTPError as exc:
            if 400 <= int(exc.code) < 500:
                return "Healthy", f"HTTP {exc.code}"
            return "Down", f"{url}: HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = f"{url}: {exc}"
            continue
    if (
        not urls
        and operation.get("controlType") == "internal-tool"
        and backing_service == "lab-app"
    ):
        return "Healthy", "Internal lab tool is provided by lab-app."
    if host and port:
        try:
            with socket.create_connection((host, int(port)), timeout_seconds):
                return "Healthy", ""
        except (OSError, socket.timeout) as exc:
            return "Down", str(exc)
    if urls:
        return "Down", last_error
    return "Unknown", "No application endpoint configured."


def run_lab_protocol_check(
    server: dict[str, Any], application_status: str
) -> tuple[str, str]:
    protocol = str(server.get("protocol") or "None")
    if protocol == "GDT" and application_status == "Healthy":
        return "Healthy", "File-based GDT contract is represented by the internal lab service."
    if protocol in {"None", "GDT"}:
        return "Unknown", "No Phase 1 protocol endpoint check configured."
    if application_status == "Healthy":
        return "Healthy", "Protocol smoke check passed through application reachability."
    if application_status == "Down":
        return "Unknown", "Protocol smoke check skipped because application check failed."
    return "Unknown", "Protocol smoke check is not implemented for this service."


def smoke_status_from_steps(steps: list[dict[str, Any]]) -> str:
    required = [step for step in steps if step.get("required", True)]
    optional = [step for step in steps if not step.get("required", True)]
    if any(step["status"] == "Down" for step in required):
        return "Down"
    if any(step["status"] == "Degraded" for step in steps):
        return "Degraded"
    if any(step["status"] == "Down" for step in optional):
        return "Degraded"
    known = [step for step in steps if step["status"] != "Unknown"]
    if not known:
        return "Unknown"
    if len(known) != len(steps):
        return "Degraded"
    return "Healthy"


def smoke_step(name: str, status: str, message: str = "", *, required: bool = True) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "message": message,
        "required": required,
    }


def run_http_smoke(url: str, name: str, *, required: bool = True) -> dict[str, Any]:
    if not url:
        return smoke_step(name, "Unknown", "Endpoint is not configured.", required=required)
    try:
        request_obj = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request_obj, timeout=3) as response:
            if 200 <= int(response.status) < 500:
                return smoke_step(name, "Healthy", f"HTTP {response.status}", required=required)
            return smoke_step(name, "Down", f"HTTP {response.status}", required=required)
    except urllib.error.HTTPError as exc:
        if 400 <= int(exc.code) < 500:
            return smoke_step(name, "Healthy", f"HTTP {exc.code}", required=required)
        return smoke_step(name, "Down", f"HTTP {exc.code}", required=required)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return smoke_step(name, "Down", str(exc), required=required)


MEDPLUM_AUTH_NOT_CONFIGURED_MESSAGE = (
    "Auth not configured: set MEDPLUM_CLIENT_ID and MEDPLUM_CLIENT_SECRET on lab-app."
)


def describe_medplum_token_failure(exc: Exception) -> str:
    return f"Token request failed: {exc}"


def describe_medplum_service_request_failure(exc: Exception) -> str:
    message = str(exc)
    if "Medplum returned HTTP 401:" in message:
        return f"FHIR data fetch unauthorized: {message}"
    return f"ServiceRequest fetch failed: {message}"


def describe_medplum_diagnostic_report_failure(exc: Exception) -> str:
    message = str(exc)
    if "Medplum returned HTTP 401:" in message:
        return f"FHIR DiagnosticReport fetch unauthorized: {message}"
    return f"DiagnosticReport fetch failed: {message}"


def run_tcp_smoke(host: str, port: Any, name: str, *, required: bool = True) -> dict[str, Any]:
    if not host or not port:
        return smoke_step(name, "Unknown", "Host or port is not configured.", required=required)
    try:
        port_number = int(port)
    except (TypeError, ValueError):
        return smoke_step(name, "Down", "Port must be an integer between 1 and 65535.", required=required)
    if not 1 <= port_number <= 65535:
        return smoke_step(name, "Down", "Port must be an integer between 1 and 65535.", required=required)
    try:
        with socket.create_connection((host, port_number), 3):
            return smoke_step(name, "Healthy", "TCP reachable.", required=required)
    except (OSError, socket.timeout) as exc:
        return smoke_step(name, "Down", str(exc), required=required)


def mllp_frame(message: str) -> bytes:
    return b"\x0b" + message.encode("utf-8") + b"\x1c\x0d"


def mllp_unframe(payload: bytes) -> str:
    text = payload.decode("utf-8", errors="replace")
    if text.startswith("\x0b"):
        text = text[1:]
    if text.endswith("\x1c\r"):
        text = text[:-2]
    elif text.endswith("\x1c"):
        text = text[:-1]
    return text


def parse_hl7_ack(payload: str) -> dict[str, str]:
    result = {"code": "", "controlId": "", "text": ""}
    for segment in payload.replace("\n", "\r").split("\r"):
        fields = segment.split("|")
        if fields and fields[0] == "MSA":
            result["code"] = fields[1].strip() if len(fields) > 1 else ""
            result["controlId"] = fields[2].strip() if len(fields) > 2 else ""
            result["text"] = fields[3].strip() if len(fields) > 3 else ""
            break
    return result


def _hl7_segments(payload: str) -> list[list[str]]:
    return [
        segment.split("|")
        for segment in payload.replace("\n", "\r").split("\r")
        if segment.strip()
    ]


def _first_component(value: str) -> str:
    return str(value or "").split("^", 1)[0].strip()


def parse_oru_summary(payload: str) -> dict[str, str]:
    segments = _hl7_segments(payload)
    if not segments or segments[0][0] != "MSH":
        raise ValidationError("HL7 payload must start with an MSH segment.")
    summary = {
        "messageType": "",
        "messageControlId": "",
        "patientMrn": "",
        "placerOrderNumber": "",
        "fillerOrderNumber": "",
    }
    for fields in segments:
        segment_id = fields[0]
        if segment_id == "MSH":
            summary["messageType"] = fields[8].strip() if len(fields) > 8 else ""
            summary["messageControlId"] = fields[9].strip() if len(fields) > 9 else ""
        elif segment_id == "PID":
            summary["patientMrn"] = _first_component(fields[3] if len(fields) > 3 else "")
        elif segment_id == "OBR":
            summary["placerOrderNumber"] = _first_component(fields[2] if len(fields) > 2 else "")
            summary["fillerOrderNumber"] = _first_component(fields[3] if len(fields) > 3 else "")
    if not summary["messageType"]:
        raise ValidationError("HL7 MSH-9 message type is required.")
    return summary


def build_hl7_ack(
    inbound_payload: str,
    *,
    code: str,
    text: str = "",
    message_control_id: str = "",
) -> str:
    inbound_msh = next(
        (fields for fields in _hl7_segments(inbound_payload) if fields and fields[0] == "MSH"),
        [],
    )
    sending_app = inbound_msh[4] if len(inbound_msh) > 4 and inbound_msh[4] else "HEALTHCARE_LAB"
    sending_facility = inbound_msh[5] if len(inbound_msh) > 5 and inbound_msh[5] else "LAB_APP"
    receiving_app = inbound_msh[2] if len(inbound_msh) > 2 and inbound_msh[2] else "OIE"
    receiving_facility = inbound_msh[3] if len(inbound_msh) > 3 and inbound_msh[3] else "HL7LAB"
    control_id = message_control_id
    if not control_id and len(inbound_msh) > 9:
        control_id = inbound_msh[9].strip()
    ack_time = hl7_message_timestamp()
    ack_control_id = f"ACK{ack_time}"
    return "\r".join(
        [
            (
                "MSH|^~\\&|"
                f"{sending_app}|{sending_facility}|{receiving_app}|{receiving_facility}|"
                f"{ack_time}||ACK^R01|{ack_control_id}|P|2.3.1"
            ),
            f"MSA|{code}|{control_id}|{text}",
        ]
    )


def accept_oie_result_payload(store: DemoStore, payload: str) -> tuple[str, dict[str, Any], int]:
    try:
        parsed = parse_oru_summary(payload)
        if parsed["messageType"] not in {"ORU^R01", "ORU^W01"}:
            item = store.record_oie_result_error(
                payload,
                parsed["messageType"],
                f"Unsupported message type: {parsed['messageType'] or 'unknown'}.",
            )
            ack = build_hl7_ack(
                payload,
                code="AR",
                text=item["error"],
                message_control_id=parsed.get("messageControlId", ""),
            )
            return ack, item, 400
        item = store.record_oie_result(payload, parsed)
        text = "Duplicate result ignored." if item.get("duplicate") else "Result accepted."
        ack = build_hl7_ack(
            payload,
            code="AA",
            text=text,
            message_control_id=parsed.get("messageControlId", ""),
        )
        return ack, item, 200
    except ValidationError as exc:
        item = store.record_oie_result_error(payload, "", str(exc))
        return build_hl7_ack(payload, code="AE", text=str(exc)), item, 400


GDT_BRIDGE_SUCCESS_MODES = {"archive", "delete"}
GDT_FILENAME_PROFILES = {"permissive", "gdt21", "gdt35"}


def normalize_gdt_bridge_success_mode(value: Any) -> str:
    mode = str(value or "archive").strip().lower()
    if mode not in GDT_BRIDGE_SUCCESS_MODES:
        raise ValidationError("GDT bridge success mode must be archive or delete.")
    return mode


def normalize_gdt_filename_profile(value: Any) -> str:
    profile = str(value or "permissive").strip().lower()
    if profile not in GDT_FILENAME_PROFILES:
        raise ValidationError("GDT filename profile must be permissive, gdt21, or gdt35.")
    return profile


def gdt_path_status(path: Path, status: str, reason: str = "") -> dict[str, Any]:
    item: dict[str, Any] = {"name": path.name, "path": str(path), "status": status}
    try:
        stat = path.stat()
        item.update(
            {
                "size": stat.st_size,
                "updatedAt": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "createdAt": datetime.fromtimestamp(stat.st_ctime, timezone.utc).isoformat(),
            }
        )
    except OSError:
        item.update({"size": 0, "updatedAt": "", "createdAt": ""})
    if reason:
        item["reason"] = reason
    return item


def gdt_is_internal_or_temp_file(path: Path) -> bool:
    name = path.name
    lowered = name.lower()
    return (
        name.startswith(".")
        or lowered.endswith(".tmp")
        or lowered.endswith(".temp")
        or lowered.endswith(".processing")
        or ".processing." in lowered
    )


def gdt_has_supported_exchange_extension(path: Path, *, profile: str = "permissive") -> bool:
    if path.suffix.lower() == ".gdt":
        return True
    return normalize_gdt_filename_profile(profile) == "gdt21" and bool(re.fullmatch(r"\.\d{3}", path.suffix))


def gdt_filename_binding_matches(
    path: Path,
    *,
    profile: str = "permissive",
    receiver_id: str = "",
    sender_id: str = "",
) -> bool:
    profile = normalize_gdt_filename_profile(profile)
    name = path.name
    upper_name = name.upper()
    receiver = str(receiver_id or "").strip().upper()
    sender = str(sender_id or "").strip().upper()
    if profile == "permissive":
        return path.suffix.lower() == ".gdt"
    if profile == "gdt35":
        if path.suffix.lower() != ".gdt":
            return False
        pattern = r"^([A-Z0-9]+)_([A-Z0-9]+)_([A-Z0-9]+)\.GDT$"
        match = re.match(pattern, upper_name)
        if not match:
            return False
        matched_receiver, matched_sender, _sequence = match.groups()
        if receiver and matched_receiver != receiver:
            return False
        if sender and matched_sender != sender:
            return False
        return True
    stem_upper = path.stem.upper()
    suffix_upper = path.suffix.upper()
    if suffix_upper == ".GDT":
        return (not receiver or stem_upper.startswith(receiver)) and (
            not sender or stem_upper.endswith(sender)
        )
    if re.fullmatch(r"\.\d{3}", suffix_upper):
        return (not receiver or stem_upper.startswith(receiver)) and (
            not sender or stem_upper.endswith(sender)
        )
    return False


def gdt_collision_safe_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    return path.with_name(f"{path.stem}-{timestamp}{path.suffix}")


def gdt_inbound_sort_key(path: Path) -> tuple[float, float, str]:
    try:
        stat = path.stat()
        return (float(stat.st_ctime), float(stat.st_mtime), path.name.lower())
    except OSError:
        return (float("inf"), float("inf"), path.name.lower())


def gdt_file_is_stable(
    path: Path,
    *,
    stable_seconds: float = 1.0,
    observations: dict[str, tuple[int, float]] | None = None,
) -> tuple[bool, str]:
    try:
        stat = path.stat()
    except OSError as exc:
        return False, f"stat failed: {exc}"
    if observations is not None:
        key = str(path)
        current = (int(stat.st_size), float(stat.st_mtime))
        previous = observations.get(key)
        observations[key] = current
        if previous != current:
            return False, "waiting for stable size and timestamp"
    age_seconds = max(0.0, time.time() - float(stat.st_mtime))
    if age_seconds < max(0.0, float(stable_seconds)):
        return False, "waiting for file age threshold"
    return True, ""


def discover_gdt_inbound_candidates(
    bridge_root: str | Path,
    *,
    filename: str = "",
    filename_profile: str = "permissive",
    receiver_id: str = "",
    sender_id: str = "",
    require_stable: bool = False,
    stable_seconds: float = 1.0,
    observations: dict[str, tuple[int, float]] | None = None,
) -> tuple[list[Path], list[dict[str, Any]], dict[str, Path]]:
    directories = ensure_gdt_bridge_dirs(bridge_root)
    inbound = directories["inbound"]
    skipped: list[dict[str, Any]] = []
    if filename:
        paths = [inbound / Path(filename).name]
    else:
        paths = [path for path in inbound.iterdir() if path.is_file()]
    candidates: list[Path] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            skipped.append(gdt_path_status(path, "skipped", "not found"))
            continue
        if gdt_is_internal_or_temp_file(path):
            skipped.append(gdt_path_status(path, "skipped", "temporary or internal file"))
            continue
        if not gdt_has_supported_exchange_extension(path, profile=filename_profile):
            skipped.append(gdt_path_status(path, "skipped", "unsupported extension"))
            continue
        if not gdt_filename_binding_matches(
            path,
            profile=filename_profile,
            receiver_id=receiver_id,
            sender_id=sender_id,
        ):
            skipped.append(gdt_path_status(path, "skipped", "filename binding mismatch"))
            continue
        if require_stable:
            stable, reason = gdt_file_is_stable(
                path,
                stable_seconds=stable_seconds,
                observations=observations,
            )
            if not stable:
                skipped.append(gdt_path_status(path, "skipped", reason))
                continue
        candidates.append(path)
    return sorted(candidates, key=gdt_inbound_sort_key), skipped, directories


def import_gdt_bridge_files(
    store: DemoStore,
    bridge_root: str | Path,
    *,
    filename: str = "",
    success_mode: str = "archive",
    filename_profile: str = "permissive",
    receiver_id: str = "",
    sender_id: str = "",
    require_stable: bool = False,
    stable_seconds: float = 1.0,
    observations: dict[str, tuple[int, float]] | None = None,
) -> dict[str, Any]:
    success_mode = normalize_gdt_bridge_success_mode(success_mode)
    filename_profile = normalize_gdt_filename_profile(filename_profile)
    candidates, skipped, directories = discover_gdt_inbound_candidates(
        bridge_root,
        filename=filename,
        filename_profile=filename_profile,
        receiver_id=receiver_id,
        sender_id=sender_id,
        require_stable=require_stable,
        stable_seconds=stable_seconds,
        observations=observations,
    )
    processing_dir = directories["processing"]
    imported: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for source_path in candidates:
        processing_path = gdt_collision_safe_path(processing_dir / source_path.name)
        try:
            source_path.replace(processing_path)
        except OSError as exc:
            skipped.append(gdt_path_status(source_path, "skipped", f"claim failed: {exc}"))
            continue
        try:
            raw_gdt_text = processing_path.read_bytes().decode("cp1252")
            item = store.record_gdt_result(
                {
                    "rawGdtText": raw_gdt_text,
                    "bridgeRoot": str(directories["root"]),
                    "sourceFile": source_path.name,
                    "sourcePath": str(source_path),
                }
            )
        except (SimulatorValidationError, UnicodeDecodeError, OSError) as exc:
            error_target = gdt_collision_safe_path(directories["error"] / source_path.name)
            try:
                if processing_path.exists():
                    processing_path.replace(error_target)
            except OSError:
                pass
            failures.append(
                {
                    "name": source_path.name,
                    "sourcePath": str(source_path),
                    "path": str(error_target),
                    "error": str(exc),
                }
            )
            continue
        disposition_error = ""
        target_path: Path | None = None
        try:
            if success_mode == "delete":
                processing_path.unlink()
                target_path = processing_path
                final_status = "deleted"
            else:
                target_path = gdt_collision_safe_path(directories["archive"] / source_path.name)
                processing_path.replace(target_path)
                final_status = "imported"
        except OSError as exc:
            final_status = "imported-warning"
            target_path = processing_path
            disposition_error = str(exc)
        imported_item = {
            "item": item,
            "name": source_path.name,
            "sourcePath": str(source_path),
            "path": "" if success_mode == "delete" and not disposition_error else str(target_path),
            "status": final_status,
            "successMode": success_mode,
        }
        if disposition_error:
            imported_item["dispositionError"] = disposition_error
        imported.append(imported_item)
    return {
        "imported": imported,
        "skipped": skipped,
        "failures": failures,
        "processedCount": len(imported) + len(failures),
        "successMode": success_mode,
        "filenameProfile": filename_profile,
        "receiverId": receiver_id,
        "senderId": sender_id,
    }


class OieResultListener:
    def __init__(self, store: DemoStore):
        self.store = store
        self.host = "0.0.0.0"
        self.port = 6665
        self.framing = True
        self._thread: threading.Thread | None = None
        self._socket: socket.socket | None = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        self.last_error = ""
        self.last_received_at = ""

    def status(self) -> dict[str, Any]:
        with self._lock:
            running = bool(self._thread and self._thread.is_alive())
            return {
                "running": running,
                "host": self.host,
                "port": self.port,
                "mllpFraming": self.framing,
                "lastError": self.last_error,
                "lastReceivedAt": self.last_received_at,
            }

    def start(self, *, host: str, port: int, framing: bool = True) -> dict[str, Any]:
        if not host:
            raise ValidationError("Listener host is required.")
        if not 1 <= int(port) <= 65535:
            raise ValidationError("Listener port must be between 1 and 65535.")
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        with self._lock:
            if self._thread and self._thread.is_alive():
                if self.host == host and self.port == int(port) and self.framing == framing:
                    server.close()
                    return self.status()
                server.close()
                raise ValidationError("Stop the current listener before changing configuration.")
            try:
                server.bind((host, int(port)))
                server.listen(5)
                server.settimeout(0.5)
            except OSError as exc:
                server.close()
                self.last_error = str(exc)
                raise ValidationError(f"Listener could not start: {exc}") from exc
            self.host = host
            self.port = int(port)
            self.framing = bool(framing)
            self.last_error = ""
            self._stop_event.clear()
            self._socket = server
            self._thread = threading.Thread(target=self._serve, name="oie-result-listener", daemon=True)
            self._thread.start()
        return self.status()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self._stop_event.set()
            if self._socket:
                try:
                    self._socket.close()
                except OSError:
                    pass
            thread = self._thread
        if thread:
            thread.join(timeout=2)
        return self.status()

    def _serve(self) -> None:
        with self._lock:
            server = self._socket
        if server is None:
            return
        try:
            while not self._stop_event.is_set():
                try:
                    connection, _address = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if not self._stop_event.is_set():
                        with self._lock:
                            self.last_error = "Listener socket closed unexpectedly."
                    break
                with connection:
                    self._handle_connection(connection)
        except OSError as exc:
            with self._lock:
                self.last_error = str(exc)
        finally:
            with self._lock:
                self._socket = None
            try:
                server.close()
            except OSError:
                pass

    def _handle_connection(self, connection: socket.socket) -> None:
        received = bytearray()
        connection.settimeout(5)
        try:
            while True:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                received.extend(chunk)
                if self.framing and b"\x1c\x0d" in received:
                    break
            payload = mllp_unframe(bytes(received)) if self.framing else bytes(received).decode("utf-8", errors="replace")
            ack, _item, _status = accept_oie_result_payload(self.store, payload)
            connection.sendall(mllp_frame(ack) if self.framing else ack.encode("utf-8"))
            with self._lock:
                self.last_received_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
                self.last_error = ""
        except Exception as exc:  # pragma: no cover - defensive listener boundary
            with self._lock:
                self.last_error = str(exc)


class GdtBridgeInboundWatcher:
    def __init__(
        self,
        store: DemoStore,
        bridge_root: str | Path,
        *,
        poll_seconds: float = 2.0,
        success_mode: str = "archive",
        filename_profile: str = "permissive",
        receiver_id: str = "",
        sender_id: str = "",
        stable_seconds: float = 1.0,
    ) -> None:
        self.store = store
        self.bridge_root = str(bridge_root)
        self.poll_seconds = max(0.25, float(poll_seconds))
        self.success_mode = normalize_gdt_bridge_success_mode(success_mode)
        self.filename_profile = normalize_gdt_filename_profile(filename_profile)
        self.receiver_id = str(receiver_id or "").strip()
        self.sender_id = str(sender_id or "").strip()
        self.stable_seconds = max(0.0, float(stable_seconds))
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._observations: dict[str, tuple[int, float]] = {}
        self._last_result: dict[str, Any] = {"imported": [], "skipped": [], "failures": [], "processedCount": 0}
        self._last_error = ""
        self._last_run_at = ""

    def status(self) -> dict[str, Any]:
        with self._lock:
            running = bool(self._thread and self._thread.is_alive())
            return {
                "running": running,
                "bridgeRoot": self.bridge_root,
                "pollSeconds": self.poll_seconds,
                "successMode": self.success_mode,
                "filenameProfile": self.filename_profile,
                "receiverId": self.receiver_id,
                "senderId": self.sender_id,
                "stableSeconds": self.stable_seconds,
                "lastResult": self._last_result,
                "lastError": self._last_error,
                "lastRunAt": self._last_run_at,
            }

    def configure(
        self,
        *,
        bridge_root: str | Path | None = None,
        success_mode: str | None = None,
        filename_profile: str | None = None,
        receiver_id: str | None = None,
        sender_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise ValidationError("Stop automatic GDT import before changing bridge watcher configuration.")
            if bridge_root is not None:
                self.bridge_root = str(bridge_root)
            if success_mode is not None:
                self.success_mode = normalize_gdt_bridge_success_mode(success_mode)
            if filename_profile is not None:
                self.filename_profile = normalize_gdt_filename_profile(filename_profile)
            if receiver_id is not None:
                self.receiver_id = str(receiver_id or "").strip()
            if sender_id is not None:
                self.sender_id = str(sender_id or "").strip()
            self._observations = {}
            self._last_error = ""
            return self.status()

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return self.status()
            ensure_gdt_bridge_dirs(self.bridge_root)
            self._stop_event.clear()
            self._last_error = ""
            self._thread = threading.Thread(target=self._serve, name="gdt-bridge-inbound-watcher", daemon=True)
            self._thread.start()
            return self.status()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self._stop_event.set()
            thread = self._thread
        if thread:
            thread.join(timeout=max(1.0, self.poll_seconds + 0.5))
        with self._lock:
            if self._thread is thread:
                self._thread = None
        return self.status()

    def _serve(self) -> None:
        while not self._stop_event.is_set():
            try:
                with self._lock:
                    bridge_root = self.bridge_root
                    success_mode = self.success_mode
                    filename_profile = self.filename_profile
                    receiver_id = self.receiver_id
                    sender_id = self.sender_id
                    stable_seconds = self.stable_seconds
                    observations = self._observations
                result = import_gdt_bridge_files(
                    self.store,
                    bridge_root,
                    success_mode=success_mode,
                    filename_profile=filename_profile,
                    receiver_id=receiver_id,
                    sender_id=sender_id,
                    require_stable=True,
                    stable_seconds=stable_seconds,
                    observations=observations,
                )
                with self._lock:
                    self._last_result = result
                    self._last_error = ""
                    self._last_run_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
            except Exception as exc:  # pragma: no cover - defensive watcher boundary
                with self._lock:
                    self._last_error = str(exc)
                    self._last_run_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
            self._stop_event.wait(self.poll_seconds)


def send_hl7_mllp_message(
    message: str,
    *,
    host: str,
    port: int,
    timeout_seconds: float,
    framing: bool = True,
) -> str:
    outgoing = mllp_frame(message) if framing else message.encode("utf-8")
    received = bytearray()
    with socket.create_connection((host, int(port)), timeout_seconds) as connection:
        connection.settimeout(timeout_seconds)
        connection.sendall(outgoing)
        while True:
            chunk = connection.recv(4096)
            if not chunk:
                break
            received.extend(chunk)
            if framing and b"\x1c\x0d" in received:
                break
    return mllp_unframe(bytes(received)) if framing else bytes(received).decode("utf-8", errors="replace")


def run_gdt_bridge_smoke(app: Flask, server: dict[str, Any]) -> list[dict[str, Any]]:
    steps = [run_lab_application_check(server)]
    application_step = smoke_step("application_endpoint", steps[0][0], steps[0][1], required=False)
    bridge_dirs = ensure_gdt_bridge_dirs(app.config["GDT_BRIDGE_PATH"])
    probe_path = bridge_dirs["root"] / ".lab-smoke-probe"
    try:
        probe_path.write_text("ok", encoding="utf-8")
        read_back = probe_path.read_text(encoding="utf-8")
        probe_path.unlink(missing_ok=True)
        folder_step = smoke_step(
            "folder_write_read",
            "Healthy" if read_back == "ok" else "Down",
            str(bridge_dirs["root"]),
        )
    except OSError as exc:
        folder_step = smoke_step("folder_write_read", "Down", str(exc))
    openemr_source = app.extensions.get("openemr_procedure_order_source")
    openemr_status = openemr_source.status() if openemr_source else {"configured": False}
    return [
        smoke_step("folder_structure", "Healthy", str(bridge_dirs["root"])),
        folder_step,
        smoke_step("bridge_folder_contract", "Healthy", "GDT bridge folders are writable."),
        smoke_step(
            "openemr_source_status",
            "Healthy" if openemr_status.get("configured") else "Unknown",
            json.dumps(openemr_status),
            required=False,
        ),
        application_step,
    ]


def run_gdt_folder_contract_smoke(app: Flask) -> dict[str, Any]:
    try:
        bridge_dirs = ensure_gdt_bridge_dirs(app.config["GDT_BRIDGE_PATH"])
        probe_path = bridge_dirs["root"] / ".lab-smoke-probe"
        probe_path.write_text("ok", encoding="utf-8")
        read_back = probe_path.read_text(encoding="utf-8")
        probe_path.unlink(missing_ok=True)
        if read_back != "ok":
            return smoke_step(
                "gdt_folder_contract",
                "Down",
                f"Read-back mismatch under {bridge_dirs['root']}.",
            )
        return smoke_step(
            "gdt_folder_contract",
            "Healthy",
            f"GDT bridge folders are writable at {bridge_dirs['root']}.",
        )
    except OSError as exc:
        return smoke_step("gdt_folder_contract", "Down", str(exc))


def run_openemr_gdt_backend_verify(app: Flask, server: dict[str, Any]) -> list[dict[str, Any]]:
    base_url = str(server.get("baseUrl") or "").rstrip("/")
    operation = server.get("operation") or {}
    backing_service = str(operation.get("backingService") or "").strip()
    smoke_base_url = base_url
    if operation.get("controlType") == "docker-compose":
        smoke_base_url = DOCKER_COMPOSE_APPLICATION_URLS.get(backing_service, base_url)
    steps = [run_http_smoke(smoke_base_url, "openemr_http")]
    openemr_source = app.extensions.get("openemr_procedure_order_source")
    if openemr_source is None:
        steps.extend(
            [
                smoke_step("openemr_db_connection", "Down", "OpenEMR procedure-order source is unavailable."),
                smoke_step("openemr_order_schema", "Unknown", "Skipped because source is unavailable."),
                smoke_step("openemr_ecg_orders", "Unknown", "Skipped because source is unavailable.", required=False),
            ]
        )
    else:
        verify_result = openemr_source.verify_order_query()
        connection = verify_result["connection"]
        schema = verify_result["schema"]
        orders = verify_result["orders"]
        steps.extend(
            [
                smoke_step("openemr_db_connection", connection["status"], connection["message"]),
                smoke_step("openemr_order_schema", schema["status"], schema["message"]),
                smoke_step(
                    "openemr_ecg_orders",
                    orders["status"],
                    orders["message"],
                    required=False,
                ),
            ]
        )
    steps.append(run_gdt_folder_contract_smoke(app))
    return steps


def run_lab_smoke_check(
    app: Flask,
    store: DemoStore,
    server: dict[str, Any],
    *,
    auth_manager: MedplumAuthManager | None = None,
) -> dict[str, Any]:
    profile = server["operation"].get("smokeProfile") or ""
    base_url = str(server.get("baseUrl") or "").rstrip("/")
    steps: list[dict[str, Any]]
    if profile == "medplum":
        metadata_url = f"{base_url}/metadata" if base_url else ""
        steps = [
            run_http_smoke(base_url, "http_reachability"),
            run_http_smoke(metadata_url, "fhir_metadata", required=True),
        ]
        if auth_manager is not None and auth_manager.is_configured() and base_url:
            try:
                auth_manager.get_access_token(base_url)
                steps.append(smoke_step("oauth_token", "Healthy", "Token acquired.", required=False))
            except (ValidationError, UpstreamFhirError) as exc:
                steps.append(smoke_step("oauth_token", "Down", describe_medplum_token_failure(exc), required=False))
        else:
            steps.append(smoke_step("oauth_token", "Unknown", MEDPLUM_AUTH_NOT_CONFIGURED_MESSAGE, required=False))
        if base_url:
            try:
                fetch_result = fetch_fhir_service_requests(
                    base_url,
                    "",
                    auth_manager=auth_manager if auth_manager and auth_manager.is_configured() else None,
                )
                steps.append(
                    smoke_step(
                        "service_request_fetch",
                        "Healthy" if fetch_result["resourceType"] == "Bundle" else "Degraded",
                        f"HTTP {fetch_result['status']}",
                        required=False,
                    )
                )
            except (ValidationError, UpstreamFhirError) as exc:
                steps.append(smoke_step("service_request_fetch", "Down", describe_medplum_service_request_failure(exc), required=False))
            try:
                diagnostic_result = fetch_fhir_diagnostic_report_bundle(
                    base_url,
                    "",
                    patient_reference="Patient/lab-smoke-probe",
                    auth_manager=auth_manager if auth_manager and auth_manager.is_configured() else None,
                )
                report_count = len(diagnostic_result["reports"])
                steps.append(
                    smoke_step(
                        "diagnostic_report_fetch",
                        "Healthy" if diagnostic_result["resourceType"] == "Bundle" else "Degraded",
                        f"HTTP {diagnostic_result['status']}; {report_count} report(s).",
                        required=False,
                    )
                )
            except (ValidationError, UpstreamFhirError) as exc:
                steps.append(smoke_step("diagnostic_report_fetch", "Down", describe_medplum_diagnostic_report_failure(exc), required=False))
        else:
            steps.append(smoke_step("service_request_fetch", "Unknown", "FHIR base URL is not configured.", required=False))
            steps.append(smoke_step("diagnostic_report_fetch", "Unknown", "FHIR base URL is not configured.", required=False))
    elif profile == "gdt-bridge":
        steps = run_gdt_bridge_smoke(app, server)
    elif profile == "dcm4chee":
        dcm4chee_profile = dcm4chee_profile_from_config(app.config)
        diagnostics = validate_dcm4chee_profile(dcm4chee_profile)
        dimse = dcm4chee_profile["dimse"]
        steps = [
            smoke_step(
                "connection_profile",
                diagnostics["status"],
                diagnostics["summary"],
            ),
            run_http_smoke(dcm4chee_profile["webUiUrl"], "dicom_archive_http"),
            run_tcp_smoke(dimse["host"], dimse["port"], "dicom_dimse", required=False),
        ]
    elif profile == "oie":
        check_config = server.get("checkConfig") or {}
        mllp_host = str(check_config.get("mllpHost") or "").strip()
        mllp_port = check_config.get("mllpPort")
        operation = server.get("operation") or {}
        backing_service = str(operation.get("backingService") or "").strip()
        smoke_base_url = base_url
        if operation.get("controlType") == "docker-compose":
            smoke_base_url = DOCKER_COMPOSE_APPLICATION_URLS.get(backing_service, base_url)
        if backing_service == "oie" and mllp_host in {"127.0.0.1", "localhost"}:
            mllp_host = "oie"
        steps = [
            run_http_smoke(smoke_base_url, "oie_http"),
            run_tcp_smoke(mllp_host, mllp_port, "mllp_endpoint", required=False),
        ]
    elif profile == "hl7tester":
        steps = [
            run_tcp_smoke(str(server.get("host") or ""), server.get("port"), "hl7_listener", required=False),
            smoke_step(
                "pdf_ed_tool",
                "Healthy",
                "tests/test_b64_pdf.py is available."
                if Path("tests/test_b64_pdf.py").exists()
                else "Tool not found.",
                required=False,
            ),
        ]
    elif profile == "gdt-hospital":
        steps = [
            smoke_step("gdt_order_store", "Healthy", f"{len(store.list_gdt_orders())} order(s)."),
            smoke_step("bridge_contract", "Healthy", app.config["GDT_BRIDGE_PATH"]),
        ]
    elif profile == "openemr":
        steps = run_openemr_gdt_backend_verify(app, server)
    else:
        steps = [smoke_step("adapter", "Unknown", "No smoke profile is configured.", required=False)]
    overall_status = smoke_status_from_steps(steps)
    return {
        "profile": profile,
        "status": overall_status,
        "steps": steps,
        "requiredFailures": [step for step in steps if step.get("required", True) and step["status"] == "Down"],
        "optionalFailures": [step for step in steps if not step.get("required", True) and step["status"] == "Down"],
    }


def run_lab_server_health_check(store: DemoStore, server_id: int) -> dict[str, Any]:
    server = store.get_lab_server(server_id)
    if not server["enabled"]:
        return store.update_lab_server_health(
            server_id,
            overall_status="Unknown",
            process_status="Unknown",
            application_status="Unknown",
            protocol_status="Unknown",
            recent_error="Server is disabled.",
        )
    application_status, application_error = run_lab_application_check(server)
    protocol_status, protocol_note = run_lab_protocol_check(server, application_status)
    process_status = "Unknown"
    operation = server.get("operation") or {}
    if application_status == "Healthy" and operation.get("controlType") == "docker-compose":
        process_status = "Healthy"
    elif operation.get("controlType") == "internal-tool":
        process_status = "Healthy"
    checks = {
        "process": process_status,
        "application": application_status,
        "protocol": protocol_status,
    }
    recent_error = application_error if application_status == "Down" else ""
    if not recent_error and protocol_status in {"Degraded", "Down"}:
        recent_error = protocol_note
    return store.update_lab_server_health(
        server_id,
        overall_status=derive_lab_overall_status(checks),
        process_status=checks["process"],
        application_status=checks["application"],
        protocol_status=checks["protocol"],
        recent_error=recent_error,
    )


def resolve_lab_operator() -> str:
    return (
        os.environ.get("USERNAME")
        or os.environ.get("USER")
        or os.environ.get("LOGNAME")
        or "local-user"
    ).strip() or "local-user"


def restart_progress_steps(result: str, error_text: str = "") -> list[dict[str, str]]:
    steps = ["stop", "start", "wait_for_port", "application_health", "smoke", "final_status"]
    if result == "success":
        return [{"step": step, "status": "completed"} for step in steps]
    return [
        {
            "step": step,
            "status": "failed" if step == "final_status" else "completed",
            **({"error": error_text} if step == "final_status" and error_text else {}),
        }
        for step in steps
    ]


def run_internal_lab_operation(
    server: dict[str, Any],
    action: str,
    *,
    app: Flask,
    store: DemoStore,
    lines: int = 200,
) -> dict[str, Any]:
    service_name = server["name"]
    if action not in {"status", "smoke", "logs"}:
        raise LabOperationError(f"{service_name} does not support {action}.")
    if service_name == "GDT Bridge":
        bridge_dirs = ensure_gdt_bridge_dirs(app.config["GDT_BRIDGE_PATH"])
        status = {
            "bridgePath": str(bridge_dirs["root"]),
            "folders": {name: str(path) for name, path in bridge_dirs.items() if name != "root"},
        }
    elif service_name == "HL7Tester":
        status = {
            "message": "HL7Tester is monitored as an external service in Healthcare Lab.",
            "host": server.get("host"),
            "port": server.get("port"),
        }
    elif service_name == "GDT Hospital":
        status = {
            "bridgeRoot": app.config["GDT_BRIDGE_PATH"],
            "message": "GDT workflow APIs live in ECG AP Simulator; Healthcare Lab monitors runtime health only.",
        }
    else:
        status = {"message": f"No internal operation adapter for {service_name}."}
    output = json.dumps(status, indent=2)
    if action == "logs":
        output = "\n".join(output.splitlines()[-max(1, lines):])
    return {"output": output, "returnCode": 0, "command": ["internal", service_name, action]}


def decorate_lab_operation_availability(app: Flask, server: dict[str, Any]) -> dict[str, Any]:
    item = {**server}
    operation = {**(server.get("operation") or {})}
    if operation.get("controlType") == "docker-compose":
        reason = DockerComposeLabOperationAdapter(app.config["LAB_DEPLOY_SCRIPT"]).unavailable_reason()
        if reason:
            actions = operation.get("supportedActions") or []
            unavailable_actions = [action for action in actions if action != "smoke"]
            operation["supportedActions"] = [action for action in actions if action == "smoke"]
            operation["unavailableActions"] = unavailable_actions
            operation["unavailableReason"] = reason
    item["operation"] = operation
    return item


def dashboard_group_item(app: Flask, store: DemoStore, service_id: str) -> dict[str, Any]:
    group, servers = dashboard_servers_for_group(store, service_id)
    primary = next((server for server in servers if server["name"] == group["primary"]), servers[0])
    decorated_primary = decorate_lab_operation_availability(app, primary)
    status = derive_dashboard_group_status(servers)
    supported = set(decorated_primary.get("operation", {}).get("supportedActions") or [])
    process_statuses = [server.get("checks", {}).get("process", "Unknown") for server in servers]
    application_statuses = [server.get("checks", {}).get("application", "Unknown") for server in servers]
    protocol_statuses = [server.get("checks", {}).get("protocol", "Unknown") for server in servers]
    return {
        "id": service_id,
        "label": group["label"],
        "protocol": group["protocol"],
        "backend": group["backend"],
        "status": status,
        "enabled": all(server.get("enabled") for server in servers),
        "lastCheckAt": max((server.get("lastCheckAt") or "" for server in servers), default=""),
        "checks": {
            "process": min(process_statuses, key=dashboard_health_rank) if process_statuses else "Unknown",
            "application": min(application_statuses, key=dashboard_health_rank) if application_statuses else "Unknown",
            "protocol": min(protocol_statuses, key=dashboard_health_rank) if protocol_statuses else "Unknown",
        },
        "capabilities": {
            "check": True,
            "enable": "start" in supported,
            "disable": "stop" in supported,
            "restart": "restart" in supported,
        },
        "restartPreview": {
            "risk": group["risk"],
            "summary": group["riskSummary"],
            "affectedServices": list(group["affectedServices"]),
        },
        "components": [
            {
                "name": server["name"],
                "status": server["overallStatus"],
                "role": "primary" if server["name"] == group["primary"] else "supporting",
            }
            for server in servers
        ],
    }


def run_dashboard_group_health_check(store: DemoStore, service_id: str) -> list[dict[str, Any]]:
    _group, servers = dashboard_servers_for_group(store, service_id)
    return [run_lab_server_health_check(store, int(server["id"])) for server in servers]


def dashboard_events(store: DemoStore, items: list[dict[str, Any]], resource_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for item in items:
        if item["lastCheckAt"]:
            events.append(
                {
                    "timestamp": item["lastCheckAt"],
                    "level": "info" if item["status"] == "Healthy" else "warn",
                    "serviceId": item["id"],
                    "message": f"{item['label']} health is {item['status']}.",
                }
            )
    for operation in store.list_lab_operations(limit=12):
        level = "info" if operation["result"] == "success" else "error"
        events.append(
            {
                "timestamp": operation["completedAt"] or operation["startedAt"],
                "level": level,
                "serviceId": "",
                "message": f"{operation['serviceName']} {operation['action']} {operation['result']}.",
            }
        )
    if resource_snapshot["status"] != "ok":
        events.append(
            {
                "timestamp": resource_snapshot["collectedAt"],
                "level": "warn",
                "serviceId": "",
                "message": f"Resource snapshot unavailable: {resource_snapshot['message']}",
            }
        )
    return sorted(events, key=lambda event: event["timestamp"], reverse=True)[:20]


def run_lab_operation(
    *,
    app: Flask,
    store: DemoStore,
    server_id: int,
    action: str,
    lines: int = 200,
) -> dict[str, Any]:
    server = store.get_lab_server(server_id)
    normalized_action = action.strip().lower()
    if normalized_action not in LAB_OPERATION_ACTIONS:
        raise SimulatorValidationError(f"Unsupported lab operation action: {normalized_action}.")
    operation = server["operation"]
    supported_actions = operation.get("supportedActions") or []
    if normalized_action not in supported_actions:
        raise SimulatorValidationError(f"{server['name']} does not support {normalized_action}.")
    started = time.monotonic()
    started_at = current_timestamp()
    output = ""
    command: list[str] = []
    result = "success"
    error_text = ""
    try:
        if normalized_action == "smoke":
            smoke_result = run_lab_smoke_check(
                app,
                store,
                server,
                auth_manager=MedplumAuthManager(
                    client_id=app.config["MEDPLUM_CLIENT_ID"],
                    client_secret=app.config["MEDPLUM_CLIENT_SECRET"],
                    scope=app.config["MEDPLUM_SCOPE"],
                    token_url=app.config["MEDPLUM_TOKEN_URL"],
                    refresh_grace_seconds=app.config["MEDPLUM_AUTH_GRACE_SECONDS"],
                ),
            )
            output = json.dumps(smoke_result, indent=2)
            command = ["smoke", smoke_result["profile"] or server["name"]]
            checks = {
                "process": store.get_lab_server(server_id)["checks"]["process"],
                "application": smoke_result["status"],
                "protocol": smoke_result["status"],
            }
            error_text = ""
            if smoke_result["requiredFailures"] or smoke_result["optionalFailures"]:
                first_failure = (smoke_result["requiredFailures"] + smoke_result["optionalFailures"])[0]
                error_text = str(first_failure.get("message", "Smoke check failed."))
            store.update_lab_server_health(
                server_id,
                overall_status=derive_lab_overall_status(checks),
                process_status=checks["process"],
                application_status=checks["application"],
                protocol_status=checks["protocol"],
                recent_error=error_text,
            )
        elif operation.get("controlType") == "docker-compose":
            adapter = DockerComposeLabOperationAdapter(app.config["LAB_DEPLOY_SCRIPT"])
            unavailable_reason = adapter.unavailable_reason()
            if unavailable_reason:
                raise LabOperationError(
                    f"Docker Compose operation '{normalized_action}' is unavailable: {unavailable_reason}"
                )
            adapter_result = adapter.run(
                normalized_action,
                operation.get("backingService") or server["name"],
                timeout_seconds=int(operation.get("timeoutSeconds") or 60),
                lines=lines,
            )
            output = adapter_result["output"]
            command = adapter_result["command"]
        else:
            adapter_result = run_internal_lab_operation(
                server,
                normalized_action,
                app=app,
                store=store,
                lines=lines,
            )
            output = adapter_result["output"]
            command = adapter_result["command"]
        if normalized_action in {"start", "stop", "restart"}:
            run_lab_server_health_check(store, server_id)
    except (LabOperationError, ValidationError, UpstreamFhirError) as exc:
        result = "failed"
        error_text = str(exc)
    completed_at = current_timestamp()
    duration_ms = int((time.monotonic() - started) * 1000)
    progress = (
        restart_progress_steps(result, error_text)
        if normalized_action == "restart"
        else [{"step": normalized_action, "status": "completed" if result == "success" else "failed"}]
    )
    history = store.record_lab_operation(
        server_id,
        service_name=server["name"],
        action=normalized_action,
        operator=resolve_lab_operator(),
        result=result,
        duration_ms=duration_ms,
        progress=progress,
        error_text=error_text,
        started_at=started_at,
        completed_at=completed_at,
    )
    response = {
        "server": decorate_lab_operation_availability(app, store.get_lab_server(server_id)),
        "operation": history,
        "output": output,
        "command": command,
    }
    if result != "success":
        raise LabOperationError(json.dumps(response))
    return response


def parse_app_port(value: str | None = None, default: int = 5000) -> int:
    raw_value = value if value is not None else os.environ.get("LAB_APP_PORT", "")
    raw = str(raw_value).strip() or str(default)
    try:
        port = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError("LAB_APP_PORT must be an integer between 1 and 65535.") from exc
    if not 1 <= port <= 65535:
        raise ValidationError("LAB_APP_PORT must be an integer between 1 and 65535.")
    return port


def parse_app_host(value: str | None = None, default: str = "127.0.0.1") -> str:
    host = str(value if value is not None else os.environ.get("LAB_APP_HOST", default)).strip()
    return host or default


def create_app(database_path: str | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "frontend" / "templates"),
        static_folder=str(Path(__file__).parent / "frontend" / "static"),
    )
    app.config["PROJECT_MODE"] = os.environ.get("PROJECT_MODE", "healthcare_lab")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.config["DATABASE_PATH"] = (
        database_path
        or os.environ.get("HEALTHCARE_LAB_DB")
        or os.environ.get("HL7_SIMULATOR_DB")
        or str(Path("instance") / "healthcare-lab.db")
    )
    app.config["GDT_BRIDGE_PATH"] = os.environ.get(
        "GDT_BRIDGE_PATH",
        str(Path(app.instance_path) / "gdt-bridge"),
    )
    app.config["GDT_BRIDGE_IMPORT_SUCCESS_MODE"] = normalize_gdt_bridge_success_mode(
        os.environ.get("GDT_BRIDGE_IMPORT_SUCCESS_MODE", "archive")
    )
    app.config["GDT_BRIDGE_FILENAME_PROFILE"] = normalize_gdt_filename_profile(
        os.environ.get("GDT_BRIDGE_FILENAME_PROFILE", "permissive")
    )
    app.config["GDT_BRIDGE_RECEIVER_ID"] = os.environ.get("GDT_BRIDGE_RECEIVER_ID", "").strip()
    app.config["GDT_BRIDGE_SENDER_ID"] = os.environ.get("GDT_BRIDGE_SENDER_ID", "").strip()
    app.config["GDT_BRIDGE_WATCH_POLL_SECONDS"] = float(os.environ.get("GDT_BRIDGE_WATCH_POLL_SECONDS", "2"))
    app.config["GDT_BRIDGE_STABLE_SECONDS"] = float(os.environ.get("GDT_BRIDGE_STABLE_SECONDS", "1"))
    app.config["OPENEMR_DB_HOST"] = os.environ.get("OPENEMR_DB_HOST", "")
    app.config["OPENEMR_DB_PORT"] = int(os.environ.get("OPENEMR_DB_PORT", "3306"))
    app.config["OPENEMR_DB_USER"] = os.environ.get("OPENEMR_DB_USER", "")
    app.config["OPENEMR_DB_PASSWORD"] = os.environ.get("OPENEMR_DB_PASSWORD", "")
    app.config["OPENEMR_DB_NAME"] = os.environ.get("OPENEMR_DB_NAME", "openemr")
    app.config["OPENEMR_GDT_PROCEDURE_CODES"] = parse_openemr_allowed_procedure_codes(
        os.environ.get(
            "OPENEMR_GDT_PROCEDURE_CODES",
            ",".join(OPENEMR_DEFAULT_ALLOWED_PROCEDURE_CODES),
        )
    )
    app.config["MEDPLUM_CLIENT_ID"] = os.environ.get("MEDPLUM_CLIENT_ID", "")
    app.config["MEDPLUM_CLIENT_SECRET"] = os.environ.get("MEDPLUM_CLIENT_SECRET", "")
    app.config["MEDPLUM_SCOPE"] = os.environ.get("MEDPLUM_SCOPE", "")
    app.config["MEDPLUM_TOKEN_URL"] = os.environ.get("MEDPLUM_TOKEN_URL", "")
    app.config["MEDPLUM_AUTH_GRACE_SECONDS"] = int(
        os.environ.get(
            "MEDPLUM_AUTH_GRACE_SECONDS",
            str(MEDPLUM_DEFAULT_AUTH_GRACE_SECONDS),
        )
    )
    app.config["OIE_MLLP_ORDER_HOST"] = os.environ.get("OIE_MLLP_ORDER_HOST", "localhost").strip() or "localhost"
    app.config["OIE_MLLP_ORDER_PORT"] = int(os.environ.get("OIE_MLLP_ORDER_PORT", "6663"))
    app.config["OIE_MLLP_RESULT_HOST"] = os.environ.get("OIE_MLLP_RESULT_HOST", "0.0.0.0").strip() or "0.0.0.0"
    app.config["OIE_MLLP_RESULT_PORT"] = int(os.environ.get("OIE_MLLP_RESULT_PORT", "6665"))
    app.config["DCM4CHEE_PROFILE_NAME"] = os.environ.get("DCM4CHEE_PROFILE_NAME", DCM4CHEE_PROFILE_NAME).strip()
    app.config["DCM4CHEE_DISPLAY_NAME"] = os.environ.get("DCM4CHEE_DISPLAY_NAME", "dcm4chee Local Archive").strip()
    app.config["DCM4CHEE_ENVIRONMENT_NAME"] = os.environ.get("DCM4CHEE_ENVIRONMENT_NAME", "local-docker").strip()
    app.config["DCM4CHEE_WEB_UI_URL"] = os.environ.get(
        "DCM4CHEE_WEB_UI_URL",
        "http://127.0.0.1:8082/dcm4chee-arc/ui2",
    ).strip()
    app.config["DCM4CHEE_DIMSE_HOST"] = os.environ.get("DCM4CHEE_DIMSE_HOST", "127.0.0.1").strip()
    app.config["DCM4CHEE_DIMSE_PORT"] = os.environ.get("DCM4CHEE_DIMSE_PORT", "11112").strip()
    app.config["DCM4CHEE_CALLED_AE_TITLE"] = os.environ.get("DCM4CHEE_CALLED_AE_TITLE", "DCM4CHEE").strip()
    app.config["DCM4CHEE_CALLING_AE_TITLE"] = os.environ.get("DCM4CHEE_CALLING_AE_TITLE", "HEALTHCARE_LAB").strip()
    app.config["DCM4CHEE_MWL_AE_TITLE"] = os.environ.get(
        "DCM4CHEE_MWL_AE_TITLE",
        app.config["DCM4CHEE_CALLED_AE_TITLE"] or "DCM4CHEE",
    ).strip()
    app.config["DCM4CHEE_DEFAULT_SCHEDULED_STATION_AE_TITLE"] = os.environ.get(
        "DCM4CHEE_DEFAULT_SCHEDULED_STATION_AE_TITLE",
        "ECG_AP",
    ).strip()
    app.config["DCM4CHEE_DICOMWEB_BASE_URL"] = os.environ.get(
        "DCM4CHEE_DICOMWEB_BASE_URL",
        f"http://127.0.0.1:8082/dcm4chee-arc/aets/{app.config['DCM4CHEE_CALLED_AE_TITLE'] or 'DCM4CHEE'}/rs",
    ).strip()
    app.config["DCM4CHEE_QIDO_RS_URL"] = os.environ.get("DCM4CHEE_QIDO_RS_URL", "").strip()
    app.config["DCM4CHEE_WADO_RS_URL"] = os.environ.get("DCM4CHEE_WADO_RS_URL", "").strip()
    app.config["DCM4CHEE_STOW_RS_URL"] = os.environ.get("DCM4CHEE_STOW_RS_URL", "").strip()
    app.config["DCM4CHEE_VIEWER_STUDY_URL_TEMPLATE"] = os.environ.get(
        "DCM4CHEE_VIEWER_STUDY_URL_TEMPLATE",
        "",
    ).strip()
    app.config["DCM4CHEE_UID_ROOT"] = os.environ.get(
        "DCM4CHEE_UID_ROOT",
        "1.2.826.0.1.3680043.10.543",
    ).strip()
    app.config["DCM4CHEE_AUTH_MODE"] = os.environ.get("DCM4CHEE_AUTH_MODE", "none").strip()
    app.config["DCM4CHEE_TLS_ENABLED"] = os.environ.get("DCM4CHEE_TLS_ENABLED", "").strip()
    app.config["DCM4CHEE_TLS_VERIFY"] = os.environ.get("DCM4CHEE_TLS_VERIFY", "").strip()
    app.config["DCM4CHEE_USERNAME"] = os.environ.get("DCM4CHEE_USERNAME", "").strip()
    app.config["DCM4CHEE_TOKEN_URL"] = os.environ.get("DCM4CHEE_TOKEN_URL", "").strip()
    app.config["DCM4CHEE_CERTIFICATE_PATH"] = os.environ.get("DCM4CHEE_CERTIFICATE_PATH", "").strip()
    app.config["DCM4CHEE_PRIVATE_KEY_PATH"] = os.environ.get("DCM4CHEE_PRIVATE_KEY_PATH", "").strip()
    app.config["LAB_DEPLOY_SCRIPT"] = os.environ.get(
        "LAB_DEPLOY_SCRIPT",
        str(Path(__file__).parent / "deploy" / "lab.ps1"),
    )
    Path(app.config["DATABASE_PATH"]).parent.mkdir(parents=True, exist_ok=True)
    validate_gdt_bridge_dirs(app.config["GDT_BRIDGE_PATH"])
    store = DemoStore(app.config["DATABASE_PATH"])
    gdt_bridge_watcher = GdtBridgeInboundWatcher(
        store,
        app.config["GDT_BRIDGE_PATH"],
        poll_seconds=app.config["GDT_BRIDGE_WATCH_POLL_SECONDS"],
        success_mode=app.config["GDT_BRIDGE_IMPORT_SUCCESS_MODE"],
        filename_profile=app.config["GDT_BRIDGE_FILENAME_PROFILE"],
        receiver_id=app.config["GDT_BRIDGE_RECEIVER_ID"],
        sender_id=app.config["GDT_BRIDGE_SENDER_ID"],
        stable_seconds=app.config["GDT_BRIDGE_STABLE_SECONDS"],
    )
    openemr_source = OpenEMRProcedureOrderSource(
        host=app.config["OPENEMR_DB_HOST"],
        port=app.config["OPENEMR_DB_PORT"],
        user=app.config["OPENEMR_DB_USER"],
        password=app.config["OPENEMR_DB_PASSWORD"],
        database=app.config["OPENEMR_DB_NAME"],
        allowed_procedure_codes=app.config["OPENEMR_GDT_PROCEDURE_CODES"],
    )
    app.extensions["demo_store"] = store
    app.extensions["openemr_procedure_order_source"] = openemr_source
    app.extensions["oie_result_listener"] = OieResultListener(store)
    app.extensions["gdt_bridge_watcher"] = gdt_bridge_watcher

    def get_auth_manager() -> MedplumAuthManager:
        return MedplumAuthManager(
            client_id=app.config["MEDPLUM_CLIENT_ID"],
            client_secret=app.config["MEDPLUM_CLIENT_SECRET"],
            scope=app.config["MEDPLUM_SCOPE"],
            token_url=app.config["MEDPLUM_TOKEN_URL"],
            refresh_grace_seconds=app.config["MEDPLUM_AUTH_GRACE_SECONDS"],
        )

    def get_openemr_source() -> OpenEMRProcedureOrderSource:
        return app.extensions["openemr_procedure_order_source"]

    def configured_medplum_base_url() -> str:
        medplum = next(
            (item for item in store.list_lab_servers() if item["name"] == "Medplum"),
            None,
        )
        return str((medplum or {}).get("baseUrl") or "").strip()

    def static_asset_version(filename: str) -> str:
        asset_path = Path(app.static_folder or "") / filename
        try:
            return str(asset_path.stat().st_mtime_ns)
        except OSError:
            return "0"

    @app.context_processor
    def inject_asset_helpers():
        return {"asset_version": static_asset_version}

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            project_mode=app.config["PROJECT_MODE"],
            oie_order_host=app.config["OIE_MLLP_ORDER_HOST"],
            oie_order_port=app.config["OIE_MLLP_ORDER_PORT"],
            oie_result_host=app.config["OIE_MLLP_RESULT_HOST"],
            oie_result_port=app.config["OIE_MLLP_RESULT_PORT"],
        )

    @app.get("/api/patients")
    def list_patients():
        return jsonify({"success": True, "items": store.list_patient_records()})

    @app.post("/api/patients")
    def create_patient():
        payload = request.get_json(silent=True) or {}
        try:
            item = store.create_patient_record(payload)
            if item["protocolVersion"] == "FHIR R4":
                fhir_record = store.create_patient_fhir_workflow_record(item)
                base_url = configured_medplum_base_url()
                if base_url:
                    sync_fhir_workflow_record_to_medplum(
                        store,
                        int(fhir_record["id"]),
                        base_url=base_url,
                        auth_manager=get_auth_manager(),
                    )
                else:
                    store.mark_fhir_sync_failure(
                        int(fhir_record["id"]),
                        error_text="Medplum FHIR base URL is required.",
                    )
                item = store.get_patient_record(int(item["id"]))
        except SimulatorValidationError as exc:
            return error_response(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    @app.post("/api/patients/<int:record_id>/fhir-sync")
    def sync_patient_fhir_record(record_id: int):
        try:
            item = store.get_patient_record(record_id)
        except KeyError:
            return error_response("Patient record was not found.", 404)
        if item["protocolVersion"] != "FHIR R4":
            return error_response("Patient record is not FHIR mode.", 400)
        fhir = item.get("fhir") or store.create_patient_fhir_workflow_record(item)
        base_url = configured_medplum_base_url()
        if not base_url:
            return error_response("Medplum FHIR base URL is required.", 400)
        try:
            sync_fhir_workflow_record_to_medplum(
                store,
                int(fhir.get("recordId") or fhir["id"]),
                base_url=base_url,
                auth_manager=get_auth_manager(),
            )
        except (ValidationError, SimulatorValidationError) as exc:
            return error_response(str(exc), 400)
        item = store.get_patient_record(record_id)
        fhir = item.get("fhir") or {}
        return jsonify({"success": (fhir.get("sync") or {}).get("status") == FHIR_SYNC_STATUS_SYNCED, "item": item})

    @app.get("/api/orders")
    def list_orders():
        return jsonify({"success": True, "items": store.list_order_records()})

    @app.post("/api/orders")
    def create_order():
        payload = request.get_json(silent=True) or {}
        try:
            mode = str(payload.get("mode") or "").strip().lower()
            if mode == "fhir":
                item = store.create_fhir_order_record(payload)
                service_request = store.create_order_service_request_fhir_workflow_record(item)
                base_url = configured_medplum_base_url()
                if base_url:
                    service_request = sync_fhir_workflow_record_to_medplum(
                        store,
                        int(service_request["id"]),
                        base_url=base_url,
                        auth_manager=get_auth_manager(),
                    )
                else:
                    service_request = store.mark_fhir_sync_failure(
                        int(service_request["id"]),
                        error_text="Medplum FHIR base URL is required.",
                    )
                service_request_reference = str((service_request.get("medplum") or {}).get("reference") or "")
                patient_reference = str(
                    ((service_request.get("resource") or {}).get("subject") or {}).get("reference") or ""
                )
                if (
                    (service_request.get("sync") or {}).get("status") == FHIR_SYNC_STATUS_SYNCED
                    and service_request_reference
                ):
                    task = store.create_order_task_fhir_workflow_record(
                        item,
                        patient_reference=patient_reference,
                        service_request_reference=service_request_reference,
                    )
                    if base_url:
                        sync_fhir_workflow_record_to_medplum(
                            store,
                            int(task["id"]),
                            base_url=base_url,
                            auth_manager=get_auth_manager(),
                        )
                item = store.get_order_record(int(item["id"]))
            elif mode == "dicom":
                item = store.create_dcm4chee_order_record(payload)
                profile = dcm4chee_profile_from_config(app.config)
                sync_order_to_dcm4chee_mwl(
                    store,
                    item,
                    profile,
                    uid_root=app.config["DCM4CHEE_UID_ROOT"],
                )
                item = store.get_order_record(int(item["id"]))
            else:
                item = store.create_order_record(payload)
        except KeyError:
            return error_response("Patient record was not found.", 404)
        except SimulatorValidationError as exc:
            return error_response(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    @app.get("/api/fhir/mappings")
    def list_fhir_mappings():
        return jsonify({"success": True, "items": store.list_fhir_resource_mappings()})

    @app.get("/api/fhir/records")
    def list_fhir_records():
        sync_status = str(request.args.get("syncStatus") or "").strip()
        return jsonify({"success": True, "items": store.list_fhir_workflow_records(sync_status)})

    @app.get("/api/fhir/inventory")
    def list_fhir_inventory():
        sync_status = str(request.args.get("syncStatus") or "").strip()
        resource_type = str(request.args.get("resourceType") or "").strip()
        if resource_type and resource_type not in MEDPLUM_INVENTORY_RESOURCE_TYPES:
            return error_response("FHIR resource type is not supported by Medplum inventory.", 400)
        records = [
            record
            for record in store.list_fhir_workflow_records(sync_status)
            if record["resourceType"] in MEDPLUM_INVENTORY_RESOURCE_TYPES
            and (not resource_type or record["resourceType"] == resource_type)
        ]
        items = [medplum_inventory_record(record) for record in records]
        patients = [
            {
                "id": item["id"],
                "localFhirRecordNumber": item["localFhirRecordNumber"],
                "localSourceId": item["localSourceId"],
                "identifier": item["identifier"],
                "medplum": item["medplum"],
                "sync": item["sync"],
                "reference": item["medplum"].get("reference") or "",
            }
            for item in items
            if item["resourceType"] == "Patient"
        ]
        return jsonify(
            {
                "success": True,
                "items": items,
                "patients": patients,
                "resourceTypes": list(MEDPLUM_INVENTORY_RESOURCE_TYPES),
            }
        )

    @app.get("/api/fhir/diagnostic-reports")
    def fetch_fhir_diagnostic_reports():
        patient_reference = str(
            request.args.get("patient")
            or request.args.get("patientReference")
            or ""
        ).strip()
        service_request_reference = str(
            request.args.get("serviceRequest")
            or request.args.get("serviceRequestReference")
            or ""
        ).strip()
        base_url = str(request.args.get("baseUrl") or configured_medplum_base_url()).strip()
        if not base_url:
            return error_response("Medplum FHIR base URL is required.", 400)
        try:
            result = fetch_fhir_diagnostic_report_bundle(
                base_url,
                "",
                patient_reference=patient_reference,
                service_request_reference=service_request_reference,
                auth_manager=get_auth_manager(),
            )
        except ValidationError as exc:
            return error_response(str(exc), 400)
        except UpstreamFhirError as exc:
            status_code = exc.http_status if exc.http_status in {401, 403} else 502
            return jsonify(
                {
                    "success": False,
                    "error": str(exc),
                    "statusCode": exc.http_status,
                    "operationOutcome": operation_outcome_from_payload(exc.response_payload),
                    "response": exc.response_payload,
                }
            ), status_code
        return jsonify(
            {
                "success": True,
                "source": "medplum-live",
                "patientReference": result["patientReference"],
                "serviceRequestReference": result["serviceRequestReference"],
                "strategy": result["strategy"],
                "fallbackReason": result["fallbackReason"],
                "empty": result["empty"],
                "requestUrl": result["requestUrl"],
                "bundle": result["body"],
                "bundles": result["bundles"],
                "reports": result["reports"],
            }
        )

    @app.get("/api/fhir/resource-preview")
    def fetch_fhir_resource_preview():
        reference = str(request.args.get("reference") or "").strip()
        base_url = str(request.args.get("baseUrl") or configured_medplum_base_url()).strip()
        if not base_url:
            return error_response("Medplum FHIR base URL is required.", 400)
        try:
            base = normalize_fhir_base_url(base_url)
            fetch_url = medplum_reference_resource_url(base, reference)
            status_code, live_resource = request_fhir_json(
                fetch_url,
                "",
                auth_manager=get_auth_manager(),
                base_url=base,
            )
        except ValidationError as exc:
            return error_response(str(exc), 400)
        except UpstreamFhirError as exc:
            status_code = exc.http_status if exc.http_status in {401, 403, 404} else 502
            return jsonify(
                {
                    "success": False,
                    "error": str(exc),
                    "statusCode": exc.http_status,
                    "operationOutcome": operation_outcome_from_payload(exc.response_payload),
                    "response": exc.response_payload,
                }
            ), status_code
        return jsonify(
            {
                "success": True,
                "source": "medplum-live",
                "reference": reference,
                "statusCode": status_code,
                "resource": live_resource,
            }
        )

    @app.post("/api/fhir/records")
    def create_fhir_record():
        payload = request.get_json(silent=True) or {}
        try:
            item = store.create_fhir_workflow_record(payload)
        except SimulatorValidationError as exc:
            return error_response(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    @app.get("/api/fhir/records/<int:record_id>")
    def get_fhir_record(record_id: int):
        try:
            item = store.get_fhir_workflow_record(record_id)
        except KeyError:
            return error_response("FHIR workflow record was not found.", 404)
        return jsonify({"success": True, "item": item})

    @app.get("/api/fhir/records/<int:record_id>/preview")
    def get_fhir_record_preview(record_id: int):
        try:
            item = store.get_fhir_workflow_record(record_id)
        except KeyError:
            return error_response("FHIR workflow record was not found.", 404)
        if item["resourceType"] not in MEDPLUM_INVENTORY_RESOURCE_TYPES:
            return error_response("FHIR resource type is not supported by Medplum inventory.", 400)

        sync_status = (item.get("sync") or {}).get("status")
        reference = str((item.get("medplum") or {}).get("reference") or "").strip()
        base_url = configured_medplum_base_url()
        fallback_resource = item.get("resource") or {}
        if sync_status == FHIR_SYNC_STATUS_SYNCED and reference:
            try:
                base = normalize_fhir_base_url(base_url)
                fetch_url = medplum_reference_resource_url(base, reference)
                status_code, live_resource = request_fhir_json(
                    fetch_url,
                    "",
                    auth_manager=get_auth_manager(),
                    base_url=base,
                )
                return jsonify(
                    {
                        "success": True,
                        "item": item,
                        "resource": live_resource,
                        "source": "medplum-live",
                        "live": {
                            "fetched": True,
                            "statusCode": status_code,
                            "reference": reference,
                            "error": "",
                        },
                    }
                )
            except (ValidationError, SimulatorValidationError, UpstreamFhirError) as exc:
                return jsonify(
                    {
                        "success": True,
                        "item": item,
                        "resource": fallback_resource,
                        "source": "local-submitted-fallback",
                        "live": {
                            "fetched": False,
                            "statusCode": http_status_from_upstream_error(str(exc)),
                            "reference": reference,
                            "error": str(exc),
                        },
                    }
                )

        return jsonify(
            {
                "success": True,
                "item": item,
                "resource": fallback_resource,
                "source": "local-submitted",
                "live": {
                    "fetched": False,
                    "statusCode": None,
                    "reference": reference,
                    "error": "",
                },
            }
        )

    @app.get("/api/fhir/records/<int:record_id>/attempts")
    def list_fhir_record_attempts(record_id: int):
        try:
            store.get_fhir_workflow_record(record_id)
        except KeyError:
            return error_response("FHIR workflow record was not found.", 404)
        return jsonify({"success": True, "items": store.list_fhir_sync_attempts(record_id)})

    @app.post("/api/fhir/records/<int:record_id>/sync")
    def sync_fhir_record(record_id: int):
        payload = request.get_json(silent=True) or {}
        base_url = str(payload.get("baseUrl") or configured_medplum_base_url()).strip()
        if not base_url:
            return error_response("Medplum FHIR base URL is required.", 400)
        try:
            item = sync_fhir_workflow_record_to_medplum(
                store,
                record_id,
                base_url=base_url,
                auth_manager=get_auth_manager(),
            )
        except KeyError:
            return error_response("FHIR workflow record was not found.", 404)
        except (ValidationError, SimulatorValidationError) as exc:
            return error_response(str(exc), 400)
        return jsonify({"success": item["sync"]["status"] == FHIR_SYNC_STATUS_SYNCED, "item": item})

    @app.get("/api/gdt/orders")
    def list_gdt_orders():
        return jsonify({"success": True, "items": store.list_gdt_order_records()})

    @app.get("/api/gdt/orders/<int:order_id>")
    def get_gdt_order(order_id: int):
        try:
            item = store.get_gdt_order_record(order_id)
        except KeyError:
            return error_response("GDT order was not found.", 404)
        return jsonify({"success": True, "item": item})

    @app.post("/api/gdt/orders")
    def create_gdt_order():
        payload = request.get_json(silent=True) or {}
        try:
            item = store.create_gdt_order_record(payload)
        except KeyError:
            return error_response("Patient record was not found.", 404)
        except SimulatorValidationError as exc:
            return error_response(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    def gdt_bridge_file_item(path: Path, status: str = "pending") -> dict[str, Any]:
        stat = path.stat()
        return {
            "name": path.name,
            "path": str(path),
            "status": status,
            "size": stat.st_size,
            "updatedAt": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        }

    def list_gdt_bridge_inbox_items() -> list[dict[str, Any]]:
        bridge_dirs = ensure_gdt_bridge_dirs(app.config["GDT_BRIDGE_PATH"])
        filename_profile = app.config["GDT_BRIDGE_FILENAME_PROFILE"]
        items = [
            gdt_bridge_file_item(path, "pending")
            for path in sorted(bridge_dirs["inbound"].iterdir())
            if (
                path.is_file()
                and not gdt_is_internal_or_temp_file(path)
                and gdt_has_supported_exchange_extension(path, profile=filename_profile)
                and gdt_filename_binding_matches(
                    path,
                    profile=filename_profile,
                    receiver_id=app.config["GDT_BRIDGE_RECEIVER_ID"],
                    sender_id=app.config["GDT_BRIDGE_SENDER_ID"],
                )
            )
        ]
        for status, folder_name in (("imported", "archive"), ("error", "error")):
            for path in sorted(bridge_dirs[folder_name].iterdir()):
                if (
                    path.is_file()
                    and not gdt_is_internal_or_temp_file(path)
                    and gdt_has_supported_exchange_extension(path, profile=filename_profile)
                ):
                    items.append(gdt_bridge_file_item(path, status))
        return items

    def gdt_bridge_config_payload() -> dict[str, Any]:
        bridge_dirs = ensure_gdt_bridge_dirs(app.config["GDT_BRIDGE_PATH"])
        watcher = app.extensions["gdt_bridge_watcher"]
        return {
            "bridgePath": str(bridge_dirs["root"]),
            "hostPath": os.environ.get("GDT_BRIDGE_HOST_PATH", ""),
            "outboxPath": str(bridge_dirs["outbox"]),
            "inboundPath": str(bridge_dirs["inbound"]),
            "archivePath": str(bridge_dirs["archive"]),
            "errorPath": str(bridge_dirs["error"]),
            "processingPath": str(bridge_dirs["processing"]),
            "successMode": app.config["GDT_BRIDGE_IMPORT_SUCCESS_MODE"],
            "filenameProfile": app.config["GDT_BRIDGE_FILENAME_PROFILE"],
            "receiverId": app.config["GDT_BRIDGE_RECEIVER_ID"],
            "senderId": app.config["GDT_BRIDGE_SENDER_ID"],
            "watcher": watcher.status(),
            "dockerHint": (
                "When running in Docker, set GDT_BRIDGE_HOST_PATH in .env and restart lab-app "
                "to map a Windows folder to /data/gdt-bridge."
            ),
        }

    @app.get("/api/gdt/bridge/config")
    def get_gdt_bridge_config():
        return jsonify({"success": True, "item": gdt_bridge_config_payload()})

    @app.put("/api/gdt/bridge/config")
    def update_gdt_bridge_config():
        payload = request.get_json(silent=True) or {}
        bridge_path = str(payload.get("bridgePath") or "").strip()
        if not bridge_path:
            return error_response("GDT shared folder path is required.", 400)
        watcher = app.extensions["gdt_bridge_watcher"]
        if watcher.status()["running"]:
            return error_response("Stop automatic GDT import before changing the shared folder path.", 409)
        if os.name != "nt" and re.match(r"^[A-Za-z]:[\\/]", bridge_path):
            return error_response(
                "Windows paths must be mounted into Docker first. Set GDT_BRIDGE_HOST_PATH in .env, "
                "restart lab-app, then use /data/gdt-bridge here.",
                400,
            )
        try:
            validate_gdt_bridge_dirs(bridge_path)
        except SimulatorValidationError as exc:
            return error_response(str(exc), 400)
        app.config["GDT_BRIDGE_PATH"] = bridge_path
        watcher.configure(bridge_root=bridge_path)
        return jsonify({"success": True, "item": gdt_bridge_config_payload()})

    @app.get("/api/gdt/workbench")
    def gdt_workbench():
        return jsonify(
            {
                "success": True,
                **store.list_gdt_workbench(bridge_inbox=list_gdt_bridge_inbox_items()),
            }
        )

    @app.post("/api/gdt/orders/<int:order_id>/write-6302")
    def write_gdt_order_6302(order_id: int):
        try:
            item = store.get_gdt_order_record(order_id)
        except KeyError:
            return error_response("GDT order was not found.", 404)
        bridge_dirs = ensure_gdt_bridge_dirs(app.config["GDT_BRIDGE_PATH"])
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        target = bridge_dirs["outbox"] / f"gdtin_{item['localGdtOrderNumber']}_{timestamp}.gdt"
        temp_path = target.with_suffix(".tmp")
        try:
            temp_path.write_bytes(item["rawGdtText"].encode("cp1252"))
            temp_path.replace(target)
            updated = store.record_gdt_order_export(
                order_id,
                export_path=str(target),
                status="exported",
            )
        except OSError as exc:
            updated = store.record_gdt_order_export(
                order_id,
                export_path=str(target),
                status="error",
                error_text=str(exc),
            )
            return jsonify({"success": False, "item": updated, "error": str(exc)}), 500
        return jsonify({"success": True, "item": updated, "path": str(target)})

    @app.get("/api/gdt/bridge/inbox")
    def list_gdt_bridge_inbox():
        return jsonify({"success": True, "items": list_gdt_bridge_inbox_items()})

    @app.post("/api/gdt/bridge/import")
    def import_gdt_bridge_file():
        payload = request.get_json(silent=True) or {}
        filename = Path(str(payload.get("filename") or payload.get("name") or "")).name
        if not gdt_has_supported_exchange_extension(Path(filename), profile=app.config["GDT_BRIDGE_FILENAME_PROFILE"]):
            return error_response("A supported GDT inbox filename is required.", 400)
        result = import_gdt_bridge_files(
            store,
            app.config["GDT_BRIDGE_PATH"],
            filename=filename,
            success_mode=app.config["GDT_BRIDGE_IMPORT_SUCCESS_MODE"],
            filename_profile=app.config["GDT_BRIDGE_FILENAME_PROFILE"],
            receiver_id=app.config["GDT_BRIDGE_RECEIVER_ID"],
            sender_id=app.config["GDT_BRIDGE_SENDER_ID"],
        )
        if result["imported"]:
            first = result["imported"][0]
            return jsonify({"success": True, "item": first["item"], "path": first["path"], "result": result}), 201
        if result["failures"]:
            first = result["failures"][0]
            return jsonify({"success": False, "error": first["error"], "path": first["path"], "result": result}), 400
        return error_response(result["skipped"][0].get("reason", "GDT inbox file was not found.") if result["skipped"] else "GDT inbox file was not found.", 404)

    @app.get("/api/gdt/bridge/watcher/status")
    def gdt_bridge_watcher_status():
        return jsonify({"success": True, "item": app.extensions["gdt_bridge_watcher"].status()})

    @app.post("/api/gdt/bridge/watcher/start")
    def start_gdt_bridge_watcher():
        try:
            item = app.extensions["gdt_bridge_watcher"].start()
        except (ValidationError, SimulatorValidationError) as exc:
            return error_response(str(exc), 400)
        return jsonify({"success": True, "item": item})

    @app.post("/api/gdt/bridge/watcher/stop")
    def stop_gdt_bridge_watcher():
        item = app.extensions["gdt_bridge_watcher"].stop()
        return jsonify({"success": True, "item": item})

    @app.post("/api/gdt/orders/<int:order_id>/demo-result")
    def create_gdt_demo_result(order_id: int):
        try:
            item = store.create_gdt_demo_result(order_id)
        except KeyError:
            return error_response("GDT order was not found.", 404)
        except SimulatorValidationError as exc:
            return error_response(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    @app.get("/api/gdt/messages")
    def list_gdt_messages():
        return jsonify({"success": True, "items": store.list_gdt_messages()})

    @app.get("/api/gdt/orders/<int:order_id>/events")
    def list_gdt_order_events(order_id: int):
        try:
            store.get_gdt_order_record(order_id)
        except KeyError:
            return error_response("GDT order was not found.", 404)
        return jsonify({"success": True, "items": store.list_gdt_events(order_id)})

    @app.post("/api/gdt/results")
    def import_gdt_result():
        payload = request.get_json(silent=True) or {}
        try:
            item = store.record_gdt_result(payload)
        except SimulatorValidationError as exc:
            return error_response(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    @app.get("/api/oie/local-adt-patients")
    def list_oie_local_adt_patients():
        return jsonify(
            {
                "success": True,
                "localOnly": True,
                "message": "Local ADT inventory only; messages are not transmitted to OIE.",
                "items": store.list_oie_local_adt_inventory(),
            }
        )

    @app.get("/api/oie/local-orders")
    def list_oie_local_orders():
        return jsonify(
            {
                "success": True,
                "localOnly": True,
                "message": "Local ORM inventory. Send Order transmits one selected order to the configured OIE MLLP endpoint.",
                "items": store.list_oie_local_order_inventory(),
            }
        )

    @app.get("/api/oie/workbench")
    def oie_workbench():
        return jsonify({"success": True, **store.list_oie_workbench()})

    @app.get("/api/oie/results")
    def oie_results():
        return jsonify({"success": True, "items": store.list_oie_results()})

    @app.post("/api/oie/results")
    def receive_oie_result():
        payload = request.get_data(as_text=True)
        if request.is_json:
            body = request.get_json(silent=True) or {}
            payload = str(body.get("payload") or "")
        if not payload.strip():
            return error_response("HL7 payload is required.", 400)
        ack, item, status_code = accept_oie_result_payload(store, payload)
        return jsonify({"success": status_code < 400, "item": item, "ack": ack}), status_code

    @app.get("/api/oie/result-listener/status")
    def oie_result_listener_status():
        listener: OieResultListener = app.extensions["oie_result_listener"]
        return jsonify({"success": True, "item": listener.status()})

    @app.post("/api/oie/result-listener/start")
    def start_oie_result_listener():
        listener: OieResultListener = app.extensions["oie_result_listener"]
        payload = request.get_json(silent=True) or {}
        host = str(payload.get("host", app.config["OIE_MLLP_RESULT_HOST"]) or "").strip()
        try:
            port = int(payload.get("port", app.config["OIE_MLLP_RESULT_PORT"]))
        except (TypeError, ValueError):
            return error_response("Listener port must be numeric.", 400)
        framing = bool(payload.get("mllpFraming", True))
        try:
            item = listener.start(host=host, port=port, framing=framing)
        except ValidationError as exc:
            return error_response(str(exc), 400)
        return jsonify({"success": True, "item": item})

    @app.post("/api/oie/result-listener/stop")
    def stop_oie_result_listener():
        listener: OieResultListener = app.extensions["oie_result_listener"]
        return jsonify({"success": True, "item": listener.stop()})

    @app.post("/api/oie/local-orders/<int:order_id>/send")
    def send_oie_local_order(order_id: int):
        payload = request.get_json(silent=True) or {}
        default_host = app.config["OIE_MLLP_ORDER_HOST"]
        default_port = app.config["OIE_MLLP_ORDER_PORT"]
        host = str(payload.get("host", default_host) or default_host).strip()
        try:
            port = int(payload.get("port", default_port) or default_port)
            timeout_seconds = float(payload.get("timeoutSeconds", 5) or 5)
        except (TypeError, ValueError):
            return error_response("OIE port and timeout must be numeric.", 400)
        framing = bool(payload.get("mllpFraming", True))
        if not host:
            return error_response("OIE host is required.", 400)
        if not 1 <= port <= 65535:
            return error_response("OIE port must be between 1 and 65535.", 400)
        if timeout_seconds <= 0:
            return error_response("OIE timeout must be positive.", 400)
        try:
            order = store.get_order_record(order_id)
        except KeyError:
            return error_response("Order record was not found.", 404)
        try:
            ack_payload = send_hl7_mllp_message(
                order["payload"],
                host=host,
                port=port,
                timeout_seconds=timeout_seconds,
                framing=framing,
            )
            ack = parse_hl7_ack(ack_payload)
            ack_code = ack["code"]
            if ack_code == "AA":
                order_status = ORDER_STATUS_ACCEPTED
            elif ack_code == "AR":
                order_status = ORDER_STATUS_REJECTED
            else:
                order_status = ORDER_STATUS_ERROR
            item = store.update_order_send_result(
                order_id,
                order_status=order_status,
                ack_code=ack_code,
                ack_control_id=ack["controlId"],
                ack_text=ack["text"],
                ack_payload=ack_payload,
            )
        except (OSError, socket.timeout, TimeoutError) as exc:
            item = store.update_order_send_result(
                order_id,
                order_status=ORDER_STATUS_TRANSPORT_ERROR,
                transport_error=str(exc),
            )
            return jsonify({"success": False, "item": item, "error": str(exc)}), 502
        return jsonify({"success": True, "item": item})

    @app.get("/api/lab/server-metadata")
    def lab_server_metadata():
        return jsonify(
            {
                "success": True,
                "serverTypes": list(LAB_SERVER_TYPES),
                "protocols": list(LAB_SERVER_PROTOCOLS),
                "healthStatuses": list(LAB_HEALTH_STATUSES),
            }
        )

    @app.get("/api/dcm4chee/profile")
    @app.get("/api/dcm4chee/profiles/<profile_name>")
    def get_dcm4chee_profile(profile_name: str | None = None):
        profile = dcm4chee_profile_from_config(app.config)
        if profile_name and profile_name != profile["profileName"]:
            return error_response("dcm4chee profile was not found.", 404)
        return jsonify(
            {
                "success": True,
                "item": profile,
                "diagnostics": validate_dcm4chee_profile(profile),
            }
        )

    @app.get("/api/dcm4chee/profile/diagnostics")
    def get_dcm4chee_profile_diagnostics():
        profile = dcm4chee_profile_from_config(app.config)
        return jsonify(
            {
                "success": True,
                "profileName": profile["profileName"],
                **validate_dcm4chee_profile(profile),
            }
        )

    @app.get("/api/dashboard/services")
    def dashboard_services():
        resource_snapshot = collect_dashboard_resource_snapshot()
        items = [
            dashboard_group_item(app, store, service_id)
            for service_id in LAB_DASHBOARD_SERVICE_GROUPS
        ]
        return jsonify(
            {
                "success": True,
                "items": items,
                "summary": dashboard_summary(items, resource_snapshot),
                "resources": resource_snapshot,
                "events": dashboard_events(store, items, resource_snapshot),
            }
        )

    @app.get("/api/dashboard/services/<service_id>/restart-preview")
    def dashboard_restart_preview(service_id: str):
        try:
            item = dashboard_group_item(app, store, service_id)
        except KeyError:
            return error_response("Dashboard service id is not supported.", 404)
        return jsonify({"success": True, "item": item["restartPreview"]})

    @app.post("/api/dashboard/services/check-all")
    def dashboard_check_all():
        results = []
        for service_id in LAB_DASHBOARD_SERVICE_GROUPS:
            try:
                checked = run_dashboard_group_health_check(store, service_id)
                results.append({"serviceId": service_id, "servers": checked})
            except (KeyError, SimulatorValidationError, LabOperationError) as exc:
                results.append({"serviceId": service_id, "error": str(exc)})
        resource_snapshot = collect_dashboard_resource_snapshot()
        items = [
            dashboard_group_item(app, store, service_id)
            for service_id in LAB_DASHBOARD_SERVICE_GROUPS
        ]
        return jsonify(
            {
                "success": True,
                "items": items,
                "results": results,
                "summary": dashboard_summary(items, resource_snapshot),
                "resources": resource_snapshot,
                "events": dashboard_events(store, items, resource_snapshot),
            }
        )

    @app.post("/api/dashboard/services/<service_id>/<action>")
    def dashboard_service_action(service_id: str, action: str):
        payload = request.get_json(silent=True) or {}
        try:
            group, servers = dashboard_servers_for_group(store, service_id)
            primary = next((server for server in servers if server["name"] == group["primary"]), servers[0])
            if action.strip().lower() == "check":
                checked = run_dashboard_group_health_check(store, service_id)
                return jsonify(
                    {
                        "success": True,
                        "service": dashboard_group_item(app, store, service_id),
                        "servers": checked,
                        "output": json.dumps(checked, indent=2),
                    }
                )
            operation_action = dashboard_action_for_group(group, action)
            result = run_lab_operation(
                app=app,
                store=store,
                server_id=int(primary["id"]),
                action=operation_action,
                lines=int(payload.get("lines", 200) or 200),
            )
        except KeyError:
            return error_response("Dashboard service id is not supported.", 404)
        except SimulatorValidationError as exc:
            return error_response(str(exc), 400)
        except LabOperationError as exc:
            try:
                body = json.loads(str(exc))
            except json.JSONDecodeError:
                body = {"operation": None, "output": "", "error": str(exc)}
            return jsonify({"success": False, **body}), 500
        return jsonify(
            {
                "success": True,
                "service": dashboard_group_item(app, store, service_id),
                "operation": result["operation"],
                "output": result["output"],
            }
        )

    @app.get("/api/lab/servers")
    def list_lab_servers():
        return jsonify(
            {
                "success": True,
                "items": [
                    decorate_lab_operation_availability(app, item)
                    for item in store.list_lab_servers()
                ],
            }
        )

    @app.post("/api/lab/servers")
    def create_lab_server():
        payload = request.get_json(silent=True) or {}
        try:
            item = store.create_lab_server(payload)
        except SimulatorValidationError as exc:
            return error_response(str(exc), 400)
        return jsonify({"success": True, "item": decorate_lab_operation_availability(app, item)}), 201

    @app.get("/api/lab/servers/<int:server_id>")
    def get_lab_server(server_id: int):
        try:
            item = store.get_lab_server(server_id)
        except KeyError:
            return error_response("Server was not found.", 404)
        return jsonify({"success": True, "item": decorate_lab_operation_availability(app, item)})

    @app.put("/api/lab/servers/<int:server_id>")
    def update_lab_server(server_id: int):
        payload = request.get_json(silent=True) or {}
        try:
            item = store.update_lab_server(server_id, payload)
        except KeyError:
            return error_response("Server was not found.", 404)
        except SimulatorValidationError as exc:
            return error_response(str(exc), 400)
        return jsonify({"success": True, "item": decorate_lab_operation_availability(app, item)})

    @app.post("/api/lab/servers/<int:server_id>/check")
    def check_lab_server(server_id: int):
        try:
            item = run_lab_server_health_check(store, server_id)
        except KeyError:
            return error_response("Server was not found.", 404)
        except SimulatorValidationError as exc:
            return error_response(str(exc), 400)
        return jsonify({"success": True, "item": decorate_lab_operation_availability(app, item)})

    @app.post("/api/lab/servers/check-all")
    def check_all_lab_servers():
        checked = []
        for item in store.list_lab_servers():
            if not item["enabled"]:
                checked.append(decorate_lab_operation_availability(app, item))
                continue
            checked.append(
                decorate_lab_operation_availability(
                    app,
                    run_lab_server_health_check(store, int(item["id"])),
                )
            )
        return jsonify({"success": True, "items": checked})

    @app.get("/api/lab/servers/<int:server_id>/operations")
    def lab_server_operation_history(server_id: int):
        try:
            store.get_lab_server(server_id)
        except KeyError:
            return error_response("Server was not found.", 404)
        limit = int(request.args.get("limit", 20))
        return jsonify(
            {
                "success": True,
                "items": store.list_lab_operations(server_id, limit=limit),
            }
        )

    def execute_lab_server_operation(server_id: int, action: str):
        payload = request.get_json(silent=True) or {}
        try:
            result = run_lab_operation(
                app=app,
                store=store,
                server_id=server_id,
                action=action,
                lines=int(payload.get("lines", 200) or 200),
            )
        except KeyError:
            return error_response("Server was not found.", 404)
        except SimulatorValidationError as exc:
            return error_response(str(exc), 400)
        except LabOperationError as exc:
            try:
                body = json.loads(str(exc))
            except json.JSONDecodeError:
                body = {"operation": None, "output": "", "error": str(exc)}
            return jsonify({"success": False, **body}), 500
        return jsonify({"success": True, **result})

    @app.post("/api/lab/servers/<int:server_id>/start")
    def start_lab_server(server_id: int):
        return execute_lab_server_operation(server_id, "start")

    @app.post("/api/lab/servers/<int:server_id>/status")
    def status_lab_server(server_id: int):
        return execute_lab_server_operation(server_id, "status")

    @app.post("/api/lab/servers/<int:server_id>/stop")
    def stop_lab_server(server_id: int):
        return execute_lab_server_operation(server_id, "stop")

    @app.post("/api/lab/servers/<int:server_id>/restart")
    def restart_lab_server(server_id: int):
        return execute_lab_server_operation(server_id, "restart")

    @app.post("/api/lab/servers/<int:server_id>/smoke")
    def smoke_lab_server(server_id: int):
        return execute_lab_server_operation(server_id, "smoke")

    @app.post("/api/lab/servers/<int:server_id>/logs")
    def logs_lab_server(server_id: int):
        return execute_lab_server_operation(server_id, "logs")

    @app.post("/api/lab/servers/smoke-all")
    def smoke_all_lab_servers():
        results = []
        for item in store.list_lab_servers():
            if not item["enabled"]:
                results.append(
                    {
                        "server": item,
                        "operation": store.record_lab_operation(
                            item["id"],
                            service_name=item["name"],
                            action="smoke",
                            operator=resolve_lab_operator(),
                            result="skipped",
                            progress=[{"step": "smoke", "status": "skipped"}],
                            error_text="Server is disabled.",
                        ),
                        "output": "",
                        "command": [],
                    }
                )
                continue
            try:
                results.append(
                    run_lab_operation(
                        app=app,
                        store=store,
                        server_id=int(item["id"]),
                        action="smoke",
                    )
                )
            except LabOperationError as exc:
                try:
                    results.append(json.loads(str(exc)))
                except json.JSONDecodeError:
                    results.append({"server": item, "operation": None, "error": str(exc)})
            except SimulatorValidationError as exc:
                results.append({"server": item, "operation": None, "error": str(exc)})
        return jsonify({"success": True, "items": results})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host=parse_app_host(), port=parse_app_port(), debug=False)



