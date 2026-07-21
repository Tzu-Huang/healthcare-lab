"""Environment parsing and application configuration."""

from __future__ import annotations

import os
import urllib.parse
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from backend.domain.errors import ValidationError
from backend.domain.dicom import DCM4CHEE_AUTH_MODES
from backend.domain.openemr import (
    OPENEMR_DEFAULT_ALLOWED_PROCEDURE_CODES,
    parse_openemr_allowed_procedure_codes,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEDPLUM_DEFAULT_AUTH_GRACE_SECONDS = 300
DCM4CHEE_PROFILE_NAME = "local-dcm4chee"
GDT_BRIDGE_SUCCESS_MODES = {"archive", "delete"}
GDT_FILENAME_PROFILES = {"permissive", "gdt21", "gdt35"}
OIE_SETTINGS_PROFILE_NAME = "local-oie"
OIE_MANAGEMENT_API_BASE_URL = "http://oie:8080"
OIE_MANAGEMENT_API_USERNAME = "admin"
OIE_MANAGEMENT_API_PASSWORD = "Admin"
OIE_MANAGEMENT_API_TIMEOUT_SECONDS = 10
OIE_RESULT_LISTENER_HOST = "0.0.0.0"
OIE_RESULT_LISTENER_PORT = 6665

DEFAULT_LAB_SERVERS = (
    {
        "name": "OIE",
        "server_type": "HL7 Engine",
        "description": "Open Integration Engine / Mirth-style HL7 engine",
        "host": "127.0.0.1",
        "port": 18080,
        "base_url": "http://127.0.0.1:18080",
        "protocol": "MLLP",
        "check_config": {"mllpHost": "127.0.0.1", "mllpPort": 6661},
    },
    {
        "name": "Medplum",
        "server_type": "FHIR Server",
        "description": "FHIR R4 API server",
        "host": "127.0.0.1",
        "port": 8103,
        "base_url": "http://127.0.0.1:8103/fhir/R4",
        "protocol": "FHIR",
    },
    {
        "name": "OpenEMR",
        "server_type": "EMR",
        "description": "OpenEMR clinical system",
        "host": "127.0.0.1",
        "port": 8088,
        "base_url": "http://127.0.0.1:8088",
        "protocol": "HTTP",
    },
    {
        "name": "GDT Bridge",
        "server_type": "GDT Bridge",
        "description": "Shared-folder GDT exchange bridge",
        "host": "",
        "port": None,
        "base_url": "",
        "protocol": "GDT",
    },
    {
        "name": "dcm4chee",
        "server_type": "DICOM Archive",
        "description": "DICOM archive service",
        "host": "127.0.0.1",
        "port": 8082,
        "base_url": "http://127.0.0.1:8082/dcm4chee-arc/ui2",
        "protocol": "DICOM",
    },
    {
        "name": "HL7Tester",
        "server_type": "Test Tool",
        "description": "HL7 message generation and test tool",
        "host": "127.0.0.1",
        "port": 6671,
        "base_url": "",
        "protocol": "MLLP",
    },
    {
        "name": "GDT Hospital",
        "server_type": "Test Tool",
        "description": "GDT hospital-side simulator",
        "host": "",
        "port": None,
        "base_url": "",
        "protocol": "GDT",
    },
)

DEFAULT_LAB_OPERATION_METADATA = {
    "OIE": {
        "control_type": "docker-compose",
        "backing_service": "oie",
        "supported_actions": ["status", "start", "stop", "restart", "smoke", "logs"],
        "timeout_seconds": 120,
        "smoke_profile": "oie",
    },
    "Medplum": {
        "control_type": "docker-compose",
        "backing_service": "medplum",
        "supported_actions": ["status", "start", "stop", "restart", "smoke", "logs"],
        "timeout_seconds": 180,
        "smoke_profile": "medplum",
    },
    "OpenEMR": {
        "control_type": "docker-compose",
        "backing_service": "openemr",
        "supported_actions": ["status", "start", "stop", "restart", "smoke", "logs"],
        "timeout_seconds": 240,
        "smoke_profile": "openemr",
    },
    "GDT Bridge": {
        "control_type": "internal-tool",
        "backing_service": "lab-app",
        "supported_actions": ["status", "smoke", "logs"],
        "timeout_seconds": 60,
        "smoke_profile": "gdt-bridge",
    },
    "dcm4chee": {
        "control_type": "docker-compose",
        "backing_service": "dcm4chee",
        "supported_actions": ["status", "start", "stop", "restart", "smoke", "logs"],
        "timeout_seconds": 240,
        "smoke_profile": "dcm4chee",
    },
    "HL7Tester": {
        "control_type": "internal-tool",
        "backing_service": "lab-app",
        "supported_actions": ["status", "smoke", "logs"],
        "timeout_seconds": 60,
        "smoke_profile": "hl7tester",
    },
    "GDT Hospital": {
        "control_type": "internal-tool",
        "backing_service": "lab-app",
        "supported_actions": ["status", "smoke", "logs"],
        "timeout_seconds": 60,
        "smoke_profile": "gdt-hospital",
    },
}


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


def load_application_config(
    instance_path: str,
    database_path: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build Flask configuration without depending on Flask request state."""

    env = os.environ if environ is None else environ
    profile_name = env.get("DCM4CHEE_PROFILE_NAME", DCM4CHEE_PROFILE_NAME).strip()
    mwl_ae_title = env.get("DCM4CHEE_MWL_AE_TITLE", "WORKLIST").strip()
    config: dict[str, Any] = {
        "PROJECT_MODE": env.get("PROJECT_MODE", "healthcare_lab"),
        "DATABASE_PATH": (
            database_path
            or env.get("HEALTHCARE_LAB_DB")
            or env.get("HL7_SIMULATOR_DB")
            or str(Path("instance") / "healthcare-lab.db")
        ),
        "GDT_BRIDGE_PATH": env.get("GDT_BRIDGE_PATH", str(Path(instance_path) / "gdt-bridge")),
        "GDT_BRIDGE_IMPORT_SUCCESS_MODE": normalize_gdt_bridge_success_mode(
            env.get("GDT_BRIDGE_IMPORT_SUCCESS_MODE", "archive")
        ),
        "GDT_BRIDGE_FILENAME_PROFILE": normalize_gdt_filename_profile(
            env.get("GDT_BRIDGE_FILENAME_PROFILE", "permissive")
        ),
        "GDT_BRIDGE_RECEIVER_ID": env.get("GDT_BRIDGE_RECEIVER_ID", "").strip(),
        "GDT_BRIDGE_SENDER_ID": env.get("GDT_BRIDGE_SENDER_ID", "").strip(),
        "GDT_BRIDGE_WATCH_POLL_SECONDS": float(env.get("GDT_BRIDGE_WATCH_POLL_SECONDS", "2")),
        "GDT_BRIDGE_STABLE_SECONDS": float(env.get("GDT_BRIDGE_STABLE_SECONDS", "1")),
        "OPENEMR_DB_HOST": env.get("OPENEMR_DB_HOST", ""),
        "OPENEMR_DB_PORT": int(env.get("OPENEMR_DB_PORT", "3306")),
        "OPENEMR_DB_USER": env.get("OPENEMR_DB_USER", ""),
        "OPENEMR_DB_PASSWORD": env.get("OPENEMR_DB_PASSWORD", ""),
        "OPENEMR_DB_NAME": env.get("OPENEMR_DB_NAME", "openemr"),
        "OPENEMR_GDT_PROCEDURE_CODES": parse_openemr_allowed_procedure_codes(
            env.get("OPENEMR_GDT_PROCEDURE_CODES", ",".join(OPENEMR_DEFAULT_ALLOWED_PROCEDURE_CODES))
        ),
        "MEDPLUM_CLIENT_ID": env.get("MEDPLUM_CLIENT_ID", ""),
        "MEDPLUM_CLIENT_SECRET": env.get("MEDPLUM_CLIENT_SECRET", ""),
        "MEDPLUM_SCOPE": env.get("MEDPLUM_SCOPE", ""),
        "MEDPLUM_TOKEN_URL": env.get("MEDPLUM_TOKEN_URL", ""),
        "MEDPLUM_AUTH_GRACE_SECONDS": int(
            env.get("MEDPLUM_AUTH_GRACE_SECONDS", str(MEDPLUM_DEFAULT_AUTH_GRACE_SECONDS))
        ),
        "OIE_MLLP_ORDER_HOST": env.get("OIE_MLLP_ORDER_HOST", "localhost").strip() or "localhost",
        "OIE_MLLP_ORDER_PORT": int(env.get("OIE_MLLP_ORDER_PORT", "6600")),
        "OIE_MLLP_RESULT_HOST": env.get("OIE_MLLP_RESULT_HOST", "0.0.0.0").strip() or "0.0.0.0",
        "OIE_MLLP_RESULT_PORT": int(env.get("OIE_MLLP_RESULT_PORT", "6665")),
        "OIE_MANAGED_AP_HOST": env.get("OIE_MANAGED_AP_HOST", "hl7tester").strip() or "hl7tester",
        "DCM4CHEE_PROFILE_NAME": profile_name,
        "DCM4CHEE_DISPLAY_NAME": env.get("DCM4CHEE_DISPLAY_NAME", "dcm4chee Local Archive").strip(),
        "DCM4CHEE_ENVIRONMENT_NAME": env.get("DCM4CHEE_ENVIRONMENT_NAME", "local-docker").strip(),
        "DCM4CHEE_WEB_UI_URL": env.get(
            "DCM4CHEE_WEB_UI_URL", "http://127.0.0.1:8082/dcm4chee-arc/ui2"
        ).strip(),
        "DCM4CHEE_DIMSE_HOST": env.get("DCM4CHEE_DIMSE_HOST", "127.0.0.1").strip(),
        "DCM4CHEE_DIMSE_PORT": env.get("DCM4CHEE_DIMSE_PORT", "11112").strip(),
        "DCM4CHEE_CALLED_AE_TITLE": env.get("DCM4CHEE_CALLED_AE_TITLE", "DCM4CHEE").strip(),
        "DCM4CHEE_CALLING_AE_TITLE": env.get("DCM4CHEE_CALLING_AE_TITLE", "HEALTHCARE_LAB").strip(),
        "DCM4CHEE_MWL_AE_TITLE": mwl_ae_title,
        "DCM4CHEE_DEFAULT_SCHEDULED_STATION_AE_TITLE": env.get(
            "DCM4CHEE_DEFAULT_SCHEDULED_STATION_AE_TITLE", "ECG_AP"
        ).strip(),
        "DCM4CHEE_HL7_HOST": env.get("DCM4CHEE_HL7_HOST", "127.0.0.1").strip(),
        "DCM4CHEE_HL7_PORT": env.get("DCM4CHEE_HL7_PORT", "2575").strip(),
        "DCM4CHEE_HL7_SENDING_APPLICATION": env.get(
            "DCM4CHEE_HL7_SENDING_APPLICATION", "HEALTHCARE_LAB"
        ).strip(),
        "DCM4CHEE_HL7_SENDING_FACILITY": env.get("DCM4CHEE_HL7_SENDING_FACILITY", "LAB_APP").strip(),
        "DCM4CHEE_HL7_RECEIVING_APPLICATION": env.get(
            "DCM4CHEE_HL7_RECEIVING_APPLICATION", "DCM4CHEE"
        ).strip(),
        "DCM4CHEE_HL7_RECEIVING_FACILITY": env.get(
            "DCM4CHEE_HL7_RECEIVING_FACILITY", "DCM4CHEE"
        ).strip(),
        "DCM4CHEE_PATIENT_ASSIGNING_AUTHORITY": env.get(
            "DCM4CHEE_PATIENT_ASSIGNING_AUTHORITY", profile_name
        ).strip(),
        "DCM4CHEE_DICOMWEB_BASE_URL": env.get(
            "DCM4CHEE_DICOMWEB_BASE_URL",
            f"http://127.0.0.1:8082/dcm4chee-arc/aets/{mwl_ae_title or 'WORKLIST'}/rs",
        ).strip(),
        "DCM4CHEE_QIDO_RS_URL": env.get("DCM4CHEE_QIDO_RS_URL", "").strip(),
        "DCM4CHEE_WADO_RS_URL": env.get("DCM4CHEE_WADO_RS_URL", "").strip(),
        "DCM4CHEE_STOW_RS_URL": env.get("DCM4CHEE_STOW_RS_URL", "").strip(),
        "DCM4CHEE_VIEWER_STUDY_URL_TEMPLATE": env.get("DCM4CHEE_VIEWER_STUDY_URL_TEMPLATE", "").strip(),
        "DCM4CHEE_UID_ROOT": env.get("DCM4CHEE_UID_ROOT", "1.2.826.0.1.3680043.10.543").strip(),
        "DCM4CHEE_AUTH_MODE": env.get("DCM4CHEE_AUTH_MODE", "none").strip(),
        "DCM4CHEE_TLS_ENABLED": env.get("DCM4CHEE_TLS_ENABLED", "").strip(),
        "DCM4CHEE_TLS_VERIFY": env.get("DCM4CHEE_TLS_VERIFY", "").strip(),
        "DCM4CHEE_USERNAME": env.get("DCM4CHEE_USERNAME", "").strip(),
        "DCM4CHEE_TOKEN_URL": env.get("DCM4CHEE_TOKEN_URL", "").strip(),
        "DCM4CHEE_CERTIFICATE_PATH": env.get("DCM4CHEE_CERTIFICATE_PATH", "").strip(),
        "DCM4CHEE_PRIVATE_KEY_PATH": env.get("DCM4CHEE_PRIVATE_KEY_PATH", "").strip(),
        "LAB_DEPLOY_SCRIPT": env.get("LAB_DEPLOY_SCRIPT", str(PROJECT_ROOT / "deploy" / "lab.ps1")),
    }
    return config


def dcm4chee_archive_dicomweb_url_from_base(base_url: str, called_ae_title: str) -> str:
    base = str(base_url or "").strip().rstrip("/")
    ae_title = urllib.parse.quote(str(called_ae_title or "DCM4CHEE").strip() or "DCM4CHEE", safe="")
    if not base:
        return f"http://127.0.0.1:8082/dcm4chee-arc/aets/{ae_title}/rs"
    parsed = urllib.parse.urlparse(base)
    if not parsed.scheme or not parsed.netloc:
        return f"http://127.0.0.1:8082/dcm4chee-arc/aets/{ae_title}/rs"
    path_parts = [part for part in parsed.path.split("/") if part]
    if "aets" in path_parts:
        index = path_parts.index("aets")
        if len(path_parts) > index + 1:
            path_parts[index + 1] = ae_title
    archive_path = "/" + "/".join(path_parts)
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, archive_path, "", "", "")).rstrip("/")


def dcm4chee_profile_from_config(config: dict[str, Any]) -> dict[str, Any]:
    profile_name = str(config.get("DCM4CHEE_PROFILE_NAME", DCM4CHEE_PROFILE_NAME) or "").strip()
    called_ae_title = str(config.get("DCM4CHEE_CALLED_AE_TITLE", "DCM4CHEE") or "").strip()
    mwl_ae_title = str(config.get("DCM4CHEE_MWL_AE_TITLE", "WORKLIST") or "").strip()
    dicomweb_base_url = str(
        config.get(
            "DCM4CHEE_DICOMWEB_BASE_URL",
            f"http://127.0.0.1:8082/dcm4chee-arc/aets/{mwl_ae_title or 'WORKLIST'}/rs",
        )
        or ""
    ).strip().rstrip("/")
    web_ui_url = str(
        config.get("DCM4CHEE_WEB_UI_URL", "http://127.0.0.1:8082/dcm4chee-arc/ui2") or ""
    ).strip().rstrip("/")
    archive_dicomweb_base_url = dcm4chee_archive_dicomweb_url_from_base(dicomweb_base_url, called_ae_title)
    qido_url = str(config.get("DCM4CHEE_QIDO_RS_URL") or archive_dicomweb_base_url).strip().rstrip("/")
    wado_url = str(config.get("DCM4CHEE_WADO_RS_URL") or archive_dicomweb_base_url).strip().rstrip("/")
    stow_url = str(config.get("DCM4CHEE_STOW_RS_URL") or archive_dicomweb_base_url).strip().rstrip("/")
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
            "aeTitle": mwl_ae_title,
            "defaultScheduledStationAETitle": str(
                config.get("DCM4CHEE_DEFAULT_SCHEDULED_STATION_AE_TITLE", "ECG_AP") or ""
            ).strip(),
        },
        "hl7": {
            "host": str(config.get("DCM4CHEE_HL7_HOST", "127.0.0.1") or "").strip(),
            "port": coerce_config_int(config.get("DCM4CHEE_HL7_PORT"), default=2575),
            "sendingApplication": str(
                config.get("DCM4CHEE_HL7_SENDING_APPLICATION", "HEALTHCARE_LAB") or ""
            ).strip(),
            "sendingFacility": str(config.get("DCM4CHEE_HL7_SENDING_FACILITY", "LAB_APP") or "").strip(),
            "receivingApplication": str(
                config.get("DCM4CHEE_HL7_RECEIVING_APPLICATION", "DCM4CHEE") or ""
            ).strip(),
            "receivingFacility": str(
                config.get("DCM4CHEE_HL7_RECEIVING_FACILITY", "DCM4CHEE") or ""
            ).strip(),
            "patientAssigningAuthority": str(
                config.get("DCM4CHEE_PATIENT_ASSIGNING_AUTHORITY", profile_name) or ""
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
