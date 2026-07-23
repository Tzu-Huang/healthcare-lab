"""Typed integration settings contracts and closed profile registrations."""

from __future__ import annotations

import urllib.parse
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePath
from typing import Any, Mapping

MEDPLUM_PROFILE_TYPE = "medplum"
MEDPLUM_PROFILE_NAME = "local-medplum"
MEDPLUM_DEFAULT_WEB_UI_URL = "http://127.0.0.1:3000"
MEDPLUM_DEFAULT_TIMEOUT_SECONDS = 10
MEDPLUM_MAX_TIMEOUT_SECONDS = 300
MEDPLUM_FIELDS = frozenset(
    {
        "baseUrl",
        "webUiUrl",
        "clientId",
        "scope",
        "tokenUrl",
        "authGraceSeconds",
        "timeoutSeconds",
        "enabled",
    }
)
MEDPLUM_SECRET_FIELDS = frozenset({"clientSecret"})
GDT_BRIDGE_PROFILE_TYPE = "gdt-bridge"
GDT_BRIDGE_FIELDS = frozenset(
    {
        "enabled",
        "applicationPath",
        "receiverId",
        "senderId",
        "filenameProfile",
        "importSuccessMode",
        "pollSeconds",
        "stableSeconds",
    }
)
DCM4CHEE_PROFILE_TYPE = "dcm4chee"
DCM4CHEE_PROFILE_NAME = "local-dcm4chee"
DCM4CHEE_SCHEMA_VERSION = 1
DCM4CHEE_AUTH_MODES = frozenset({"none", "basic", "bearer", "oauth2", "mtls"})
DCM4CHEE_DEFAULT_UID_ROOT = "1.2.826.0.1.3680043.10.543"
DCM4CHEE_FIELDS = frozenset(
    {
        "enabled",
        "profileName",
        "displayName",
        "environmentName",
        "webUiUrl",
        "dimse",
        "mwl",
        "hl7",
        "dicomweb",
        "viewer",
        "uidRoot",
        "security",
    }
)
DCM4CHEE_SECRET_FIELDS = frozenset({"password", "token", "clientSecret"})

_DCM4CHEE_NESTED_FIELDS = {
    "dimse": frozenset({"host", "port", "calledAETitle", "callingAETitle"}),
    "mwl": frozenset({"aeTitle", "defaultScheduledStationAETitle"}),
    "hl7": frozenset(
        {
            "host",
            "port",
            "sendingApplication",
            "sendingFacility",
            "receivingApplication",
            "receivingFacility",
            "patientAssigningAuthority",
        }
    ),
    "dicomweb": frozenset({"baseUrl", "qidoRsUrl", "wadoRsUrl", "stowRsUrl"}),
    "viewer": frozenset({"studyUrlTemplate"}),
    "security": frozenset(
        {
            "authMode",
            "tlsEnabled",
            "tlsVerify",
            "username",
            "tokenUrl",
            "certificatePath",
            "privateKeyPath",
        }
    ),
}
_AE_TITLE_PATTERN = re.compile(r"^[\x20-\x7e]{1,16}$")
_HL7_IDENTITY_PATTERN = re.compile(r"^[^\x00-\x1f|^~\\&]{1,64}$")
_UID_ROOT_PATTERN = re.compile(r"^[0-9]+(?:\.[0-9]+)+$")


@dataclass(frozen=True)
class SettingsValidationIssue:
    field: str
    code: str
    reason: str


class TypedSettingsValidationError(ValueError):
    """Stable value-free settings validation failure."""

    def __init__(self, issues: list[SettingsValidationIssue]):
        self.issues = tuple(issues)
        super().__init__("Integration settings validation failed.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": "settings_validation_failed",
            "fields": [
                {"field": issue.field, "code": issue.code, "reason": issue.reason}
                for issue in self.issues
            ],
        }


class SecretAction(str, Enum):
    PRESERVE = "preserve"
    REPLACE = "replace"
    REMOVE = "remove"


@dataclass(frozen=True, repr=False)
class SecretMutation:
    action: SecretAction
    value: str = ""

    def __post_init__(self) -> None:
        if self.action is SecretAction.REPLACE and not self.value:
            raise ValueError("Replacement secret must be non-blank.")
        if self.action is not SecretAction.REPLACE and self.value:
            raise ValueError("Only replacement mutations carry a value.")

    def __repr__(self) -> str:
        return f"SecretMutation(action={self.action.value!r}, configured={bool(self.value)!r})"


def preserve_secret() -> SecretMutation:
    return SecretMutation(SecretAction.PRESERVE)


def replace_secret(value: Any) -> SecretMutation:
    text = "" if value is None else str(value)
    return preserve_secret() if not text.strip() else SecretMutation(SecretAction.REPLACE, text)


def remove_secret() -> SecretMutation:
    return SecretMutation(SecretAction.REMOVE)


@dataclass(frozen=True)
class TypedProfile:
    profile_type: str
    profile_name: str
    schema_version: int
    fields: dict[str, Any]


def _url_issue(field: str, value: Any, *, required: bool) -> SettingsValidationIssue | None:
    normalized = str(value or "").strip()
    if not normalized and not required:
        return None
    parsed = urllib.parse.urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return SettingsValidationIssue(
            field, "invalid_url", f"{field} must be an absolute HTTP or HTTPS URL."
        )
    return None


def _dcm4chee_issue(field: str, code: str, reason: str) -> SettingsValidationIssue:
    return SettingsValidationIssue(field, code, reason)


def _dcm4chee_required_text(
    payload: Mapping[str, Any],
    field: str,
    issues: list[SettingsValidationIssue],
    *,
    maximum: int = 128,
    issue_field: str | None = None,
) -> str:
    issue_field = issue_field or field
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        issues.append(
            _dcm4chee_issue(
                issue_field,
                "invalid_required_string",
                f"{issue_field} must be a non-empty string of at most {maximum} characters.",
            )
        )
        return ""
    return value.strip()


def _dcm4chee_port(
    payload: Mapping[str, Any],
    field: str,
    issues: list[SettingsValidationIssue],
    *,
    issue_field: str | None = None,
) -> int:
    issue_field = issue_field or field
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 65535:
        issues.append(
            _dcm4chee_issue(
                issue_field,
                "invalid_port",
                f"{issue_field} must be an integer between 1 and 65535.",
            )
        )
        return 0
    return value


def _mounted_reference(
    field: str, value: Any, issues: list[SettingsValidationIssue]
) -> str:
    if not isinstance(value, str):
        issues.append(
            _dcm4chee_issue(
                field, "invalid_mounted_reference", f"{field} must be an absolute path."
            )
        )
        return ""
    normalized = value.strip().replace("\\", "/")
    if not normalized:
        return ""
    is_absolute = normalized.startswith("/") or bool(re.match(r"^[A-Za-z]:/", normalized))
    if not is_absolute or ".." in PurePath(normalized).parts or "\x00" in normalized:
        issues.append(
            _dcm4chee_issue(
                field,
                "invalid_mounted_reference",
                f"{field} must be an absolute mounted path without parent traversal.",
            )
        )
    return normalized


def validate_dcm4chee_settings_profile(payload: Mapping[str, Any]) -> TypedProfile:
    """Validate and canonicalize the complete persisted dcm4chee public profile."""
    issues = [
        _dcm4chee_issue(field, "unknown_field", f"{field} is not supported.")
        for field in sorted(set(payload) - DCM4CHEE_FIELDS)
    ]
    issues.extend(
        _dcm4chee_issue(field, "required", f"{field} is required.")
        for field in sorted(DCM4CHEE_FIELDS - set(payload))
    )

    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        issues.append(
            _dcm4chee_issue("enabled", "invalid_boolean", "enabled must be a boolean.")
        )

    canonical: dict[str, Any] = {
        "enabled": enabled,
        "profileName": _dcm4chee_required_text(payload, "profileName", issues, maximum=64),
        "displayName": _dcm4chee_required_text(payload, "displayName", issues),
        "environmentName": _dcm4chee_required_text(
            payload, "environmentName", issues, maximum=64
        ),
    }
    web_ui_url = payload.get("webUiUrl")
    web_issue = _url_issue("webUiUrl", web_ui_url, required=True)
    if web_issue:
        issues.append(web_issue)
    canonical["webUiUrl"] = str(web_ui_url or "").strip().rstrip("/")

    nested: dict[str, Mapping[str, Any]] = {}
    for section, allowed in _DCM4CHEE_NESTED_FIELDS.items():
        value = payload.get(section)
        if not isinstance(value, Mapping):
            issues.append(
                _dcm4chee_issue(
                    section, "invalid_object", f"{section} must be an object."
                )
            )
            nested[section] = {}
            continue
        nested[section] = value
        issues.extend(
            _dcm4chee_issue(
                f"{section}.{field}",
                "unknown_field",
                f"{section}.{field} is not supported.",
            )
            for field in sorted(set(value) - allowed)
        )
        issues.extend(
            _dcm4chee_issue(
                f"{section}.{field}", "required", f"{section}.{field} is required."
            )
            for field in sorted(allowed - set(value))
        )

    dimse = nested["dimse"]
    dimse_values = {
        "host": _dcm4chee_required_text(
            dimse, "host", issues, maximum=253, issue_field="dimse.host"
        ),
        "port": _dcm4chee_port(dimse, "port", issues, issue_field="dimse.port"),
    }
    for field in ("calledAETitle", "callingAETitle"):
        value = dimse.get(field)
        normalized = value.strip() if isinstance(value, str) else ""
        if not _AE_TITLE_PATTERN.fullmatch(normalized) or "\\" in normalized:
            issues.append(
                _dcm4chee_issue(
                    f"dimse.{field}",
                    "invalid_ae_title",
                    f"dimse.{field} must be a printable DICOM AE title of at most 16 characters.",
                )
            )
        dimse_values[field] = normalized
    canonical["dimse"] = dimse_values

    mwl = nested["mwl"]
    mwl_values: dict[str, str] = {}
    for field in ("aeTitle", "defaultScheduledStationAETitle"):
        value = mwl.get(field)
        normalized = value.strip() if isinstance(value, str) else ""
        if not _AE_TITLE_PATTERN.fullmatch(normalized) or "\\" in normalized:
            issues.append(
                _dcm4chee_issue(
                    f"mwl.{field}",
                    "invalid_ae_title",
                    f"mwl.{field} must be a printable DICOM AE title of at most 16 characters.",
                )
            )
        mwl_values[field] = normalized
    canonical["mwl"] = mwl_values

    hl7 = nested["hl7"]
    hl7_values: dict[str, Any] = {
        "host": _dcm4chee_required_text(
            hl7, "host", issues, maximum=253, issue_field="hl7.host"
        ),
        "port": _dcm4chee_port(hl7, "port", issues, issue_field="hl7.port"),
    }
    for field in (
        "sendingApplication",
        "sendingFacility",
        "receivingApplication",
        "receivingFacility",
        "patientAssigningAuthority",
    ):
        value = hl7.get(field)
        normalized = value.strip() if isinstance(value, str) else ""
        if not _HL7_IDENTITY_PATTERN.fullmatch(normalized):
            issues.append(
                _dcm4chee_issue(
                    f"hl7.{field}",
                    "invalid_hl7_identity",
                    f"hl7.{field} must be a non-empty HL7 identity without encoding separators.",
                )
            )
        hl7_values[field] = normalized
    canonical["hl7"] = hl7_values

    dicomweb = nested["dicomweb"]
    dicomweb_values: dict[str, str] = {}
    for field in ("baseUrl", "qidoRsUrl", "wadoRsUrl", "stowRsUrl"):
        path = f"dicomweb.{field}"
        issue = _url_issue(path, dicomweb.get(field), required=True)
        if issue:
            issues.append(issue)
        dicomweb_values[field] = str(dicomweb.get(field) or "").strip().rstrip("/")
    canonical["dicomweb"] = dicomweb_values

    viewer = nested["viewer"]
    template = viewer.get("studyUrlTemplate")
    template_issue = _url_issue("viewer.studyUrlTemplate", template, required=True)
    if template_issue:
        issues.append(template_issue)
    elif "{studyInstanceUid}" not in str(template):
        issues.append(
            _dcm4chee_issue(
                "viewer.studyUrlTemplate",
                "missing_study_uid_placeholder",
                "viewer.studyUrlTemplate must contain {studyInstanceUid}.",
            )
        )
    canonical["viewer"] = {"studyUrlTemplate": str(template or "").strip()}

    uid_root = payload.get("uidRoot")
    normalized_uid = uid_root.strip().strip(".") if isinstance(uid_root, str) else ""
    valid_uid = bool(_UID_ROOT_PATTERN.fullmatch(normalized_uid)) and len(normalized_uid) <= 63
    if valid_uid:
        valid_uid = all(part == "0" or not part.startswith("0") for part in normalized_uid.split("."))
    if not valid_uid:
        issues.append(
            _dcm4chee_issue(
                "uidRoot", "invalid_uid_root", "uidRoot must be a valid DICOM UID root."
            )
        )
    canonical["uidRoot"] = normalized_uid

    security = nested["security"]
    auth_mode = security.get("authMode")
    if not isinstance(auth_mode, str) or auth_mode not in DCM4CHEE_AUTH_MODES:
        issues.append(
            _dcm4chee_issue(
                "security.authMode",
                "invalid_auth_mode",
                "security.authMode must be none, basic, bearer, oauth2, or mtls.",
            )
        )
        auth_mode = ""
    tls_enabled = security.get("tlsEnabled")
    tls_verify = security.get("tlsVerify")
    for field, value in (("tlsEnabled", tls_enabled), ("tlsVerify", tls_verify)):
        if not isinstance(value, bool):
            issues.append(
                _dcm4chee_issue(
                    f"security.{field}",
                    "invalid_boolean",
                    f"security.{field} must be a boolean.",
                )
            )
    username = security.get("username")
    if not isinstance(username, str):
        issues.append(
            _dcm4chee_issue(
                "security.username", "invalid_string", "security.username must be a string."
            )
        )
        username = ""
    username = username.strip()
    token_url = security.get("tokenUrl")
    token_issue = _url_issue("security.tokenUrl", token_url, required=auth_mode == "oauth2")
    if token_issue:
        issues.append(token_issue)
    certificate_path = _mounted_reference(
        "security.certificatePath", security.get("certificatePath"), issues
    )
    private_key_path = _mounted_reference(
        "security.privateKeyPath", security.get("privateKeyPath"), issues
    )
    if tls_verify is True and tls_enabled is not True:
        issues.append(
            _dcm4chee_issue(
                "security.tlsVerify",
                "requires_tls",
                "security.tlsVerify requires security.tlsEnabled.",
            )
        )
    if bool(certificate_path) != bool(private_key_path):
        issues.append(
            _dcm4chee_issue(
                "security.privateKeyPath",
                "certificate_key_pair_required",
                "Certificate and private-key references must be configured together.",
            )
        )
    if (certificate_path or private_key_path) and tls_enabled is not True:
        issues.append(
            _dcm4chee_issue(
                "security.certificatePath",
                "requires_tls",
                "Mounted certificate references require security.tlsEnabled.",
            )
        )
    if auth_mode in {"basic", "oauth2"} and not username:
        issues.append(
            _dcm4chee_issue(
                "security.username",
                "required_for_auth_mode",
                "security.username is required for the selected authentication mode.",
            )
        )
    if auth_mode == "mtls" and not (
        tls_enabled is True and certificate_path and private_key_path
    ):
        issues.append(
            _dcm4chee_issue(
                "security.authMode",
                "mtls_material_required",
                "mtls requires TLS and mounted certificate and private-key references.",
            )
        )
    canonical["security"] = {
        "authMode": auth_mode,
        "tlsEnabled": tls_enabled,
        "tlsVerify": tls_verify,
        "username": username,
        "tokenUrl": str(token_url or "").strip().rstrip("/"),
        "certificatePath": certificate_path,
        "privateKeyPath": private_key_path,
    }

    if issues:
        raise TypedSettingsValidationError(issues)
    return TypedProfile(
        profile_type=DCM4CHEE_PROFILE_TYPE,
        profile_name=DCM4CHEE_PROFILE_NAME,
        schema_version=DCM4CHEE_SCHEMA_VERSION,
        fields=canonical,
    )


def dcm4chee_bootstrap_candidate(configuration: Mapping[str, Any]) -> TypedProfile:
    """Build the one-time Docker-compatible candidate from legacy configuration."""
    profile_name = str(
        configuration.get("DCM4CHEE_PROFILE_NAME", DCM4CHEE_PROFILE_NAME) or ""
    ).strip()
    called_ae = str(configuration.get("DCM4CHEE_CALLED_AE_TITLE", "DCM4CHEE") or "").strip()
    mwl_ae = str(configuration.get("DCM4CHEE_MWL_AE_TITLE", "WORKLIST") or "").strip()
    web_ui_url = str(
        configuration.get(
            "DCM4CHEE_WEB_UI_URL", "http://127.0.0.1:8082/dcm4chee-arc/ui2"
        )
        or ""
    ).strip().rstrip("/")
    base_url = str(
        configuration.get(
            "DCM4CHEE_DICOMWEB_BASE_URL",
            f"http://dcm4chee:8080/dcm4chee-arc/aets/{mwl_ae or 'WORKLIST'}/rs",
        )
        or ""
    ).strip().rstrip("/")
    parsed = urllib.parse.urlparse(base_url)
    parts = [part for part in parsed.path.split("/") if part]
    if "aets" in parts and len(parts) > parts.index("aets") + 1:
        parts[parts.index("aets") + 1] = urllib.parse.quote(called_ae, safe="")
    archive_url = urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, "/" + "/".join(parts), "", "", "")
    ).rstrip("/")
    qido_url = str(configuration.get("DCM4CHEE_QIDO_RS_URL") or archive_url).strip()
    def legacy_int(name: str, default: int) -> Any:
        value = configuration.get(name, default)
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return value

    def legacy_bool(name: str, default: bool) -> Any:
        value = configuration.get(name, default)
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
        return value

    return validate_dcm4chee_settings_profile(
        {
            "enabled": configuration.get("DCM4CHEE_ENABLED", True),
            "profileName": profile_name,
            "displayName": configuration.get(
                "DCM4CHEE_DISPLAY_NAME", "dcm4chee Local Archive"
            ),
            "environmentName": configuration.get(
                "DCM4CHEE_ENVIRONMENT_NAME", "local-docker"
            ),
            "webUiUrl": web_ui_url,
            "dimse": {
                "host": configuration.get("DCM4CHEE_DIMSE_HOST", "dcm4chee"),
                "port": legacy_int("DCM4CHEE_DIMSE_PORT", 11112),
                "calledAETitle": called_ae,
                "callingAETitle": configuration.get(
                    "DCM4CHEE_CALLING_AE_TITLE", "HEALTHCARE_LAB"
                ),
            },
            "mwl": {
                "aeTitle": mwl_ae,
                "defaultScheduledStationAETitle": configuration.get(
                    "DCM4CHEE_DEFAULT_SCHEDULED_STATION_AE_TITLE", "ECG_AP"
                ),
            },
            "hl7": {
                "host": configuration.get("DCM4CHEE_HL7_HOST", "dcm4chee"),
                "port": legacy_int("DCM4CHEE_HL7_PORT", 2575),
                "sendingApplication": configuration.get(
                    "DCM4CHEE_HL7_SENDING_APPLICATION", "HEALTHCARE_LAB"
                ),
                "sendingFacility": configuration.get(
                    "DCM4CHEE_HL7_SENDING_FACILITY", "LAB_APP"
                ),
                "receivingApplication": configuration.get(
                    "DCM4CHEE_HL7_RECEIVING_APPLICATION", "DCM4CHEE"
                ),
                "receivingFacility": configuration.get(
                    "DCM4CHEE_HL7_RECEIVING_FACILITY", "DCM4CHEE"
                ),
                "patientAssigningAuthority": configuration.get(
                    "DCM4CHEE_PATIENT_ASSIGNING_AUTHORITY", profile_name
                ),
            },
            "dicomweb": {
                "baseUrl": base_url,
                "qidoRsUrl": qido_url,
                "wadoRsUrl": configuration.get("DCM4CHEE_WADO_RS_URL") or archive_url,
                "stowRsUrl": configuration.get("DCM4CHEE_STOW_RS_URL") or archive_url,
            },
            "viewer": {
                "studyUrlTemplate": configuration.get(
                    "DCM4CHEE_VIEWER_STUDY_URL_TEMPLATE"
                )
                or f"{web_ui_url}/#/study/{{studyInstanceUid}}"
            },
            "uidRoot": configuration.get(
                "DCM4CHEE_UID_ROOT", DCM4CHEE_DEFAULT_UID_ROOT
            ),
            "security": {
                "authMode": configuration.get("DCM4CHEE_AUTH_MODE", "none"),
                "tlsEnabled": legacy_bool("DCM4CHEE_TLS_ENABLED", False),
                "tlsVerify": legacy_bool("DCM4CHEE_TLS_VERIFY", False),
                "username": configuration.get("DCM4CHEE_USERNAME", ""),
                "tokenUrl": configuration.get("DCM4CHEE_TOKEN_URL", ""),
                "certificatePath": configuration.get("DCM4CHEE_CERTIFICATE_PATH", ""),
                "privateKeyPath": configuration.get("DCM4CHEE_PRIVATE_KEY_PATH", ""),
            },
        }
    )


def validate_medplum_profile(payload: Mapping[str, Any]) -> TypedProfile:
    unknown = sorted(set(payload) - MEDPLUM_FIELDS)
    issues = [
        SettingsValidationIssue(field, "unknown_field", f"{field} is not supported.")
        for field in unknown
    ]
    missing = sorted(MEDPLUM_FIELDS - set(payload))
    issues.extend(
        SettingsValidationIssue(field, "required", f"{field} is required.")
        for field in missing
    )
    base_url_issue = _url_issue("baseUrl", payload.get("baseUrl"), required=True)
    web_ui_url_issue = _url_issue("webUiUrl", payload.get("webUiUrl"), required=True)
    token_url_issue = _url_issue("tokenUrl", payload.get("tokenUrl"), required=False)
    issues.extend(
        issue for issue in (base_url_issue, web_ui_url_issue, token_url_issue) if issue
    )

    raw_auth_grace = payload.get("authGraceSeconds")
    if (
        not isinstance(raw_auth_grace, int)
        or isinstance(raw_auth_grace, bool)
        or raw_auth_grace <= 0
    ):
        auth_grace = 0
        issues.append(
            SettingsValidationIssue(
                "authGraceSeconds",
                "invalid_positive_integer",
                "authGraceSeconds must be a positive integer.",
            )
        )
    else:
        auth_grace = raw_auth_grace
    raw_timeout = payload.get("timeoutSeconds")
    if (
        not isinstance(raw_timeout, int)
        or isinstance(raw_timeout, bool)
        or not 1 <= raw_timeout <= MEDPLUM_MAX_TIMEOUT_SECONDS
    ):
        timeout_seconds = 0
        issues.append(
            SettingsValidationIssue(
                "timeoutSeconds",
                "invalid_bounded_integer",
                (
                    "timeoutSeconds must be an integer between "
                    f"1 and {MEDPLUM_MAX_TIMEOUT_SECONDS}."
                ),
            )
        )
    else:
        timeout_seconds = raw_timeout
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        issues.append(
            SettingsValidationIssue("enabled", "invalid_boolean", "enabled must be a boolean.")
        )
    for field in ("clientId", "scope"):
        if field in payload and not isinstance(payload[field], str):
            issues.append(
                SettingsValidationIssue(field, "invalid_string", f"{field} must be a string.")
            )
    if issues:
        raise TypedSettingsValidationError(issues)
    return TypedProfile(
        profile_type=MEDPLUM_PROFILE_TYPE,
        profile_name=MEDPLUM_PROFILE_NAME,
        schema_version=1,
        fields={
            "baseUrl": str(payload["baseUrl"]).strip().rstrip("/"),
            "webUiUrl": str(payload["webUiUrl"]).strip().rstrip("/"),
            "clientId": str(payload["clientId"]).strip(),
            "scope": str(payload["scope"]).strip(),
            "tokenUrl": str(payload["tokenUrl"]).strip().rstrip("/"),
            "authGraceSeconds": auth_grace,
            "timeoutSeconds": timeout_seconds,
            "enabled": enabled,
        },
    )


PROFILE_VALIDATORS = {
    MEDPLUM_PROFILE_TYPE: validate_medplum_profile,
    DCM4CHEE_PROFILE_TYPE: validate_dcm4chee_settings_profile,
}
PROFILE_FIELDS = {
    MEDPLUM_PROFILE_TYPE: MEDPLUM_FIELDS,
    GDT_BRIDGE_PROFILE_TYPE: GDT_BRIDGE_FIELDS,
    DCM4CHEE_PROFILE_TYPE: DCM4CHEE_FIELDS,
}
PROFILE_SECRET_FIELDS = {
    MEDPLUM_PROFILE_TYPE: MEDPLUM_SECRET_FIELDS,
    GDT_BRIDGE_PROFILE_TYPE: frozenset(),
    DCM4CHEE_PROFILE_TYPE: DCM4CHEE_SECRET_FIELDS,
}


def validate_profile(profile_type: str, payload: Mapping[str, Any]) -> TypedProfile:
    if profile_type == GDT_BRIDGE_PROFILE_TYPE:
        # Lazy import keeps the feature profile dependent on the shared
        # validation primitives without creating an import cycle.
        from backend.domain.gdt_bridge_profile import validate_gdt_bridge_profile

        return validate_gdt_bridge_profile(payload)
    try:
        validator = PROFILE_VALIDATORS[profile_type]
    except KeyError as exc:
        raise TypedSettingsValidationError(
            [
                SettingsValidationIssue(
                    "profileType", "unknown_profile", "The profile type is not supported."
                )
            ]
        ) from exc
    return validator(payload)


def medplum_bootstrap_candidate(configuration: Mapping[str, Any]) -> TypedProfile:
    return validate_medplum_profile(
        {
            "baseUrl": configuration.get(
                "MEDPLUM_FHIR_BASE_URL", "http://medplum:8103/fhir/R4"
            ),
            "webUiUrl": configuration.get(
                "MEDPLUM_WEB_UI_URL", MEDPLUM_DEFAULT_WEB_UI_URL
            ),
            "clientId": configuration.get("MEDPLUM_CLIENT_ID", ""),
            "scope": configuration.get("MEDPLUM_SCOPE", ""),
            "tokenUrl": configuration.get("MEDPLUM_TOKEN_URL", ""),
            "authGraceSeconds": configuration.get("MEDPLUM_AUTH_GRACE_SECONDS", 300),
            "timeoutSeconds": configuration.get(
                "MEDPLUM_TIMEOUT_SECONDS", MEDPLUM_DEFAULT_TIMEOUT_SECONDS
            ),
            "enabled": True,
        }
    )
