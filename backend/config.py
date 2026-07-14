"""Environment parsing and application configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from backend.domain.errors import ValidationError
from backend.lab_store import (
    OPENEMR_DEFAULT_ALLOWED_PROCEDURE_CODES,
    parse_openemr_allowed_procedure_codes,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEDPLUM_DEFAULT_AUTH_GRACE_SECONDS = 300
DCM4CHEE_PROFILE_NAME = "local-dcm4chee"
DCM4CHEE_AUTH_MODES = ("none", "basic", "bearer", "oauth2", "mtls")
GDT_BRIDGE_SUCCESS_MODES = {"archive", "delete"}
GDT_FILENAME_PROFILES = {"permissive", "gdt21", "gdt35"}


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
