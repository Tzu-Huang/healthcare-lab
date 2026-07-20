"""Application defaults and compatibility-free shared protocol helpers."""

from __future__ import annotations

import json
import re
import sqlite3
import urllib.parse
from contextlib import contextmanager
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any

from backend.domain.gdt_protocol import (
    GDT_DEFAULT_CHARSET_MARKER,
    GDT_DEFAULT_ENCODING,
    GDT_ORDER_MESSAGE_TYPE,
    GDT_ORDER_TEST_CODE,
    GDT_ORDER_TEST_CODE_FIELD,
    GDT_RESULT_MESSAGE_TYPE,
    GDT_VERSION,
    GdtValidationError,
    attachment_payloads_from_result_fields,
    first_gdt_field as adapter_first_gdt_field,
    parse_gdt_6310_result,
    parse_gdt_message as adapter_parse_gdt_message,
    render_gdt_message as adapter_render_gdt_message,
    render_gdt_record as adapter_render_gdt_record,
)
from backend.templates.gdt import build_gdt_6302_request
from backend.domain.errors import SimulatorValidationError
from backend.domain import patient as patient_domain
from backend.domain import order as order_domain
from backend.domain import dicom as dicom_domain
from backend.domain.dicom import (
    DCM4CHEE_DEFAULT_UID_ROOT,
    DCM4CHEE_MWL_NON_RETRYABLE_ERROR_TYPES,
    DCM4CHEE_ORDER_PROTOCOL_VERSION,
    DCM4CHEE_RESULT_SOURCE_SIMULATED_AP,
)
from backend.domain.fhir_ledger import (
    FHIR_IDENTIFIER_SYSTEMS,
    FHIR_RESOURCE_DEPENDENCY_ORDER,
    FHIR_RESOURCE_MAPPINGS,
)
from backend.domain.gdt import ensure_gdt_bridge_dirs
from backend.domain.openemr import (
    OPENEMR_DEFAULT_ALLOWED_PROCEDURE_CODES,
    parse_openemr_allowed_procedure_codes,
)
from backend.repositories.database import SQLiteDatabase
from backend.repositories.lab import LabRepository
from backend.repositories.oie import OieRepository
from backend.repositories.enrichment import PatientEnrichmentLoader, OrderEnrichmentLoader
from backend.repositories.identifiers import PatientIdentifierRepository
from backend.repositories.patients import PatientRepository
from backend.services import protocol_compatibility as protocol_compat
from backend import protocol_composition
from backend.repositories.orders import OrderRepository
from backend.repositories.dcm4chee_patient_sync import Dcm4cheePatientSyncRepository
from backend.mappers.dicom import (
    project_mwl_attempt,
    project_mwl_mapping,
    project_patient_sync,
    project_patient_sync_attempt,
    project_result_record,
)
from backend.repositories.dcm4chee_mwl import (
    Dcm4cheeMwlRepository,
    backfill_dcm4chee_mwl_mappings,
)
from backend.repositories.dcm4chee_results import Dcm4cheeResultRepository
from backend.templates import patient as patient_templates
from backend.templates import order as order_templates
from backend.templates import dicom as dicom_templates
from backend.repositories.oie_settings import (
    serialize_oie_settings_profile,
    validate_oie_settings_payload,
)
from backend.services.oie_workflow import compose_oie_workbench
from backend.services.dcm4chee_coordination import (
    Dcm4cheeMwlAttemptCoordinator,
    Dcm4cheeWorkflowCoordinator,
)
from backend.repositories.maintenance import (
    seed_lab_servers,
    seed_oie_settings_profile,
    seed_patient_mrn_sequence,
)
from backend.repositories.schema import APPLICATION_MIGRATIONS, ensure_application_schema
from backend.domain.lab import (
    LAB_HEALTH_STATUSES,
    LAB_OPERATION_ACTIONS,
    LAB_SERVER_PROTOCOLS,
    LAB_SERVER_TYPES,
)
from backend.domain.statuses import (
    DCM4CHEE_MWL_OPERATION_CREATE,
    DCM4CHEE_MWL_OPERATION_READBACK,
    DCM4CHEE_MWL_OPERATION_VERIFY,
    DCM4CHEE_MWL_STATUS_CREATED,
    DCM4CHEE_MWL_STATUS_FAILED,
    DCM4CHEE_MWL_STATUS_PATIENT_MISSING,
    DCM4CHEE_MWL_STATUS_PENDING,
    DCM4CHEE_MWL_VERIFICATION_AMBIGUOUS,
    DCM4CHEE_MWL_VERIFICATION_FAILED,
    DCM4CHEE_MWL_VERIFICATION_NOT_VERIFIED,
    DCM4CHEE_MWL_VERIFICATION_VERIFIED,
    DCM4CHEE_PATIENT_SYNC_OPERATION_ADT_CREATE,
    DCM4CHEE_PATIENT_SYNC_OPERATION_ADT_UPDATE,
    DCM4CHEE_PATIENT_SYNC_OPERATION_PREFLIGHT,
    DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
    DCM4CHEE_PATIENT_SYNC_STATUS_PENDING,
    DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED,
    DCM4CHEE_RESULT_STATUS_AMBIGUOUS,
    DCM4CHEE_RESULT_STATUS_DUPLICATE,
    DCM4CHEE_RESULT_STATUS_MATCHED,
    DCM4CHEE_RESULT_STATUS_MISSING_ACCESSION,
    DCM4CHEE_RESULT_STATUS_NO_RESULT,
    DCM4CHEE_RESULT_STATUS_QUERY_FAILED,
    DCM4CHEE_RESULT_STATUS_UNLINKED,
    DCM4CHEE_RESULT_STATUS_WRONG_PATIENT,
    FHIR_SYNC_STATUS_FAILED,
    FHIR_SYNC_STATUS_PENDING,
    FHIR_SYNC_STATUS_SYNCED,
    FHIR_SYNC_STATUS_SYNCING,
    ORDER_STATUS_ACCEPTED,
    ORDER_STATUS_ERROR,
    ORDER_STATUS_READY,
    ORDER_STATUS_REJECTED,
    ORDER_STATUS_TRANSPORT_ERROR,
)
from backend.domain.dicom import reconcile_result_metadata as apply_dcm4chee_reconciliation
from backend.repositories.gdt_bridge_health import validate_gdt_bridge_dirs

HL7_V2_VERSION = "2.5.1"
HL7_V2_CHARSET = "UNICODE UTF-8"
HL7_V2_MSH_SUFFIX = f"{HL7_V2_VERSION}||||||{HL7_V2_CHARSET}"
PATIENT_PROTOCOL_VERSION = HL7_V2_VERSION
PATIENT_MESSAGE_TYPE = "ADT^A04"
PATIENT_MODES = {
    "hl7-v2": {"protocol": "HL7 v2.5.1", "message_type": "ADT^A04"},
    "fhir": {"protocol": "FHIR R4", "message_type": "Patient"},
    "gdt": {"protocol": "GDT 2.1", "message_type": "6301"},
    "dicom": {"protocol": "DICOM", "message_type": "Patient Module"},
}
PATIENT_CLASS_DEFAULT = "O"
GDT_PATIENT_SEX_CODES = {"M": "1", "F": "2"}
ORDER_PROTOCOL_VERSION = HL7_V2_VERSION
ORDER_MESSAGE_TYPE = "ORM^O01"
ORDER_ALLOWED_PRIORITIES = ("R", "S", "A")
ORDER_DEFAULT_CODE = "ECG12"
ORDER_DEFAULT_TEXT = "12 Lead ECG"
ORDER_DEFAULT_ALT_CODE = "93000"
ORDER_DEFAULT_ALT_TEXT = "Electrocardiogram, routine ECG with at least 12 leads"
ORDER_DEFAULT_ALT_SYSTEM = "C4"
ORDER_DEFAULT_PROVIDER = "1001^WANG^AMY"
OIE_SETTINGS_PROFILE_NAME = "local-oie"
OIE_MANAGEMENT_API_BASE_URL = "http://oie:8080"
OIE_MANAGEMENT_API_USERNAME = "admin"
OIE_MANAGEMENT_API_PASSWORD = "Admin"
OIE_MANAGEMENT_API_TIMEOUT_SECONDS = 10
OIE_RESULT_LISTENER_HOST = "0.0.0.0"
OIE_RESULT_LISTENER_PORT = 6665
FHIR_ORDER_PROTOCOL_VERSION = "FHIR R4"
FHIR_ORDER_MESSAGE_TYPE = "ServiceRequest"
FHIR_ORDER_STATUS_CREATED = "Created"
FHIR_ORDER_DEFAULT_STATUS = "active"
FHIR_ORDER_DEFAULT_INTENT = "order"
FHIR_ORDER_DEFAULT_CATEGORY = "Procedure"
FHIR_ORDER_DEFAULT_PRIORITY = "routine"
GDT_ORDER_PROTOCOL_VERSION = "GDT 2.1"
GDT_ORDER_STATUS_CREATED = "Created"
GDT_ORDER_STATUS_ERROR = "Error"
GDT_ORDER_STATUS_RESULT_RECEIVED = "Result received"
GDT_ORDER_TEST_LABEL = "12-lead resting ECG"
FHIR_SYNC_STATUSES = (
    FHIR_SYNC_STATUS_PENDING,
    FHIR_SYNC_STATUS_SYNCING,
    FHIR_SYNC_STATUS_SYNCED,
    FHIR_SYNC_STATUS_FAILED,
)
FHIR_SUPPORTED_RESOURCE_TYPES = (
    "Patient",
    "ServiceRequest",
    "Binary",
    "Observation",
    "DocumentReference",
    "DiagnosticReport",
    "Provenance",
)

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


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def urllib_quote_safe(value: Any) -> str:
    return urllib.parse.quote(str(value or "").strip(), safe="")


def hl7_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _hl7_escape(value: Any) -> str:
    text = str(value if value is not None else "")
    return (
        text.replace("\\", "\\E\\")
        .replace("|", "\\F\\")
        .replace("^", "\\S\\")
        .replace("&", "\\T\\")
        .replace("~", "\\R\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\.br\\")
    )


def _hl7_escape_composite(value: Any) -> str:
    return "^".join(
        _hl7_escape(component)
        for component in str(value if value is not None else "").split("^")
    )


def render_gdt_record(code: str, value: Any) -> bytes:
    try:
        return adapter_render_gdt_record(code, value)
    except GdtValidationError as exc:
        raise SimulatorValidationError(str(exc)) from exc


def render_gdt_message(records: list[tuple[str, Any]], *, set_type: str) -> str:
    try:
        return adapter_render_gdt_message(records, set_type=set_type)
    except GdtValidationError as exc:
        raise SimulatorValidationError(str(exc)) from exc


def parse_gdt_message(payload: str) -> dict[str, list[str]]:
    try:
        return adapter_parse_gdt_message(payload)
    except GdtValidationError as exc:
        raise SimulatorValidationError(str(exc)) from exc


def first_gdt_field(fields: dict[str, list[str]], code: str) -> str:
    return adapter_first_gdt_field(fields, code)
