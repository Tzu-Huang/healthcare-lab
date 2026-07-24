"""Closed ownership registry for supported deployment and runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass

DEPLOYMENT_ONLY = "deployment-only"
RUNTIME_PERSISTED = "runtime-persisted"
SECRET = "secret"
DERIVED_DEFAULT = "derived/default"
OWNERSHIP_CATEGORIES = frozenset(
    {DEPLOYMENT_ONLY, RUNTIME_PERSISTED, SECRET, DERIVED_DEFAULT}
)


@dataclass(frozen=True)
class ConfigurationOwnership:
    category: str
    owner: str
    activation: str
    bootstrap: str


def _entries(
    keys: str,
    category: str,
    owner: str,
    activation: str,
    bootstrap: str,
) -> dict[str, ConfigurationOwnership]:
    entry = ConfigurationOwnership(category, owner, activation, bootstrap)
    return {key: entry for key in keys.split()}


CONFIGURATION_OWNERSHIP: dict[str, ConfigurationOwnership] = {
    **_entries(
        """
        DCM4CHEE_DB_IMAGE DCM4CHEE_DB_NAME DCM4CHEE_DB_USER DCM4CHEE_DICOM_PORT
        DCM4CHEE_HL7_HOST_PORT DCM4CHEE_HTTP_PORT DCM4CHEE_IMAGE
        DCM4CHEE_LDAP_IMAGE DCM4CHEE_STORAGE_DIR
        GDT_BRIDGE_HOST_PATH LAB_APP_IMAGE LAB_APP_PORT MEDPLUM_ALLOWED_ORIGINS
        MEDPLUM_APP_BASE_URL MEDPLUM_APP_IMAGE MEDPLUM_APP_PORT MEDPLUM_BASE_URL
        MEDPLUM_IMAGE MEDPLUM_PORT MEDPLUM_POSTGRES_DB MEDPLUM_POSTGRES_IMAGE
        MEDPLUM_POSTGRES_USER MEDPLUM_PUBLIC_BASE_URL MEDPLUM_REDIS_IMAGE OIE_DATABASE
        OIE_HTTPS_PORT OIE_HTTP_PORT OIE_IMAGE OIE_AP_RESULT_INGRESS_HOST_PORT
        OIE_ORDER_INGRESS_HOST_PORT STORAGE_DIR
        """,
        DEPLOYMENT_ONLY,
        "Docker Compose",
        "container recreation",
        "never",
    ),
    **_entries(
        """
        DCM4CHEE_DB_PASSWORD DCM4CHEE_LDAP_ROOTPASS MEDPLUM_POSTGRES_PASSWORD
        MEDPLUM_RECAPTCHA_SECRET_KEY
        """,
        SECRET,
        "Docker Compose service",
        "container recreation",
        "never",
    ),
    **_entries(
        """
        MEDPLUM_CLIENT_SECRET OPENEMR_DB_PASSWORD
        """,
        SECRET,
        "typed integration settings",
        "next effective read",
        "seed missing profile once",
    ),
    **_entries(
        """
        DCM4CHEE_CLIENT_SECRET DCM4CHEE_PASSWORD DCM4CHEE_PRIVATE_KEY_PATH
        DCM4CHEE_TOKEN
        """,
        SECRET,
        "typed dcm4chee settings",
        "next effective read",
        "seed missing profile once",
    ),
    **_entries(
        """
        MEDPLUM_CLIENT_ID MEDPLUM_SCOPE MEDPLUM_TOKEN_URL MEDPLUM_AUTH_GRACE_SECONDS
        MEDPLUM_TIMEOUT_SECONDS MEDPLUM_WEB_UI_URL
        """,
        RUNTIME_PERSISTED,
        "typed Medplum settings",
        "next effective read",
        "seed missing profile once",
    ),
    **_entries(
        """
        OPENEMR_DB_HOST OPENEMR_DB_NAME OPENEMR_DB_PORT OPENEMR_DB_USER
        OPENEMR_GDT_PROCEDURE_CODES
        """,
        RUNTIME_PERSISTED,
        "typed OpenEMR settings",
        "next effective read",
        "seed missing profile once",
    ),
    **_entries(
        """
        GDT_BRIDGE_FILENAME_PROFILE GDT_BRIDGE_IMPORT_SUCCESS_MODE
        GDT_BRIDGE_RECEIVER_ID GDT_BRIDGE_SENDER_ID GDT_BRIDGE_STABLE_SECONDS
        GDT_BRIDGE_WATCH_POLL_SECONDS
        """,
        RUNTIME_PERSISTED,
        "typed GDT settings",
        "watcher restart",
        "seed missing profile once",
    ),
    **_entries(
        """
        DCM4CHEE_AUTH_MODE DCM4CHEE_CALLED_AE_TITLE DCM4CHEE_CALLING_AE_TITLE
        DCM4CHEE_CERTIFICATE_PATH DCM4CHEE_DEFAULT_SCHEDULED_STATION_AE_TITLE
        DCM4CHEE_DICOMWEB_BASE_URL DCM4CHEE_DIMSE_HOST DCM4CHEE_DIMSE_PORT
        DCM4CHEE_DISPLAY_NAME DCM4CHEE_ENVIRONMENT_NAME DCM4CHEE_HL7_HOST
        DCM4CHEE_HL7_PORT DCM4CHEE_HL7_RECEIVING_APPLICATION
        DCM4CHEE_HL7_RECEIVING_FACILITY DCM4CHEE_HL7_SENDING_APPLICATION
        DCM4CHEE_HL7_SENDING_FACILITY DCM4CHEE_MWL_AE_TITLE
        DCM4CHEE_PATIENT_ASSIGNING_AUTHORITY DCM4CHEE_PROFILE_NAME
        DCM4CHEE_QIDO_RS_URL DCM4CHEE_STOW_RS_URL DCM4CHEE_TLS_ENABLED
        DCM4CHEE_TLS_VERIFY DCM4CHEE_TOKEN_URL DCM4CHEE_UID_ROOT DCM4CHEE_USERNAME
        DCM4CHEE_VIEWER_STUDY_URL_TEMPLATE DCM4CHEE_WADO_RS_URL DCM4CHEE_WEB_UI_URL
        """,
        RUNTIME_PERSISTED,
        "typed dcm4chee settings",
        "next effective read",
        "seed missing profile once",
    ),
    **_entries(
        """
        HLAB_RESULT_LISTENER_HOST HLAB_RESULT_LISTENER_PORT OIE_MLLP_ORDER_HOST
        OIE_MLLP_ORDER_PORT
        """,
        RUNTIME_PERSISTED,
        "typed OIE settings",
        "listener retry or app restart",
        "existing OIE profile owns persistence",
    ),
    **_entries(
        """
        OIE_BOOTSTRAP_MODE OIE_BOOTSTRAP_RETRY_INTERVAL_SECONDS
        OIE_BOOTSTRAP_TIMEOUT_SECONDS
        """,
        DERIVED_DEFAULT,
        "lab-app startup policy",
        "app restart",
        "environment/default every process start",
    ),
    **_entries(
        """
        OIE_MLLP_RESULT_HOST OIE_MLLP_RESULT_PORT
        """,
        DERIVED_DEFAULT,
        "HLAB listener compatibility projection",
        "app restart",
        "derived from HLAB_RESULT_LISTENER_*",
    ),
    **_entries(
        """
        ECG_FILE_BASE_URL
        """,
        DERIVED_DEFAULT,
        "AP-facing result projection",
        "next effective read",
        "safe local default",
    ),
    **_entries(
        """
        MEDPLUM_RECAPTCHA_SITE_KEY
        """,
        DERIVED_DEFAULT,
        "Medplum deployment",
        "container recreation",
        "Compose safe local default",
    ),
    **_entries(
        """
        DCM4CHEE_LDAP_BASE_DN DCM4CHEE_LDAP_URL
        """,
        DERIVED_DEFAULT,
        "dcm4chee deployment topology",
        "container recreation",
        "Compose topology default",
    ),
}


def ownership_for(key: str) -> ConfigurationOwnership:
    """Return the single declared owner or fail closed for an unsupported key."""
    try:
        return CONFIGURATION_OWNERSHIP[key]
    except KeyError as exc:
        raise KeyError(f"Unsupported configuration key: {key}") from exc
