from __future__ import annotations

import base64
import json
import os
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
    DemoStore,
    LAB_OPERATION_ACTIONS,
    LAB_HEALTH_STATUSES,
    LAB_SERVER_PROTOCOLS,
    LAB_SERVER_TYPES,
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
    pass


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
            raise UpstreamFhirError(
                f"Medplum returned HTTP {exc.code}: {error_body}"
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


def run_tcp_smoke(host: str, port: Any, name: str, *, required: bool = True) -> dict[str, Any]:
    if not host or not port:
        return smoke_step(name, "Unknown", "Host or port is not configured.", required=required)
    try:
        with socket.create_connection((host, int(port)), 3):
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
        else:
            steps.append(smoke_step("service_request_fetch", "Unknown", "FHIR base URL is not configured.", required=False))
    elif profile == "gdt-bridge":
        steps = run_gdt_bridge_smoke(app, server)
    elif profile == "dcm4chee":
        steps = [run_http_smoke(base_url, "dicom_archive_http")]
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
    app.config["LAB_DEPLOY_SCRIPT"] = os.environ.get(
        "LAB_DEPLOY_SCRIPT",
        str(Path(__file__).parent / "deploy" / "lab.ps1"),
    )
    Path(app.config["DATABASE_PATH"]).parent.mkdir(parents=True, exist_ok=True)
    validate_gdt_bridge_dirs(app.config["GDT_BRIDGE_PATH"])
    store = DemoStore(app.config["DATABASE_PATH"])
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
        except SimulatorValidationError as exc:
            return error_response(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    @app.get("/api/orders")
    def list_orders():
        return jsonify({"success": True, "items": store.list_order_records()})

    @app.post("/api/orders")
    def create_order():
        payload = request.get_json(silent=True) or {}
        try:
            item = store.create_order_record(payload)
        except KeyError:
            return error_response("Patient record was not found.", 404)
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



