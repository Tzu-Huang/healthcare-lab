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

from backend.gdt_adapter import (
    GDT_DEFAULT_CHARSET_MARKER,
    GDT_DEFAULT_ENCODING,
    GDT_ORDER_MESSAGE_TYPE,
    GDT_ORDER_TEST_CODE,
    GDT_ORDER_TEST_CODE_FIELD,
    GDT_RESULT_MESSAGE_TYPE,
    GDT_VERSION,
    GdtValidationError,
    attachment_payloads_from_result_fields,
    build_gdt_6302_request,
    first_gdt_field as adapter_first_gdt_field,
    parse_gdt_6310_result,
    parse_gdt_message as adapter_parse_gdt_message,
    render_gdt_message as adapter_render_gdt_message,
    render_gdt_record as adapter_render_gdt_record,
)
from backend.domain.errors import SimulatorValidationError
from backend.domain import patient as patient_domain
from backend.domain import order as order_domain
from backend.domain import dicom as dicom_domain
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
from backend.repositories.orders import OrderRepository
from backend.repositories.dcm4chee_patient_sync import (
    Dcm4cheePatientSyncRepository,
    project_patient_sync_attempt_dict,
    project_patient_sync_dict,
)
from backend.repositories.dcm4chee_mwl import (
    Dcm4cheeMwlRepository,
    backfill_dcm4chee_mwl_mappings,
    project_mwl_attempt,
    project_mwl_mapping,
)
from backend.repositories.dcm4chee_results import (
    Dcm4cheeResultRepository,
    project_result_record,
)
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
DCM4CHEE_ORDER_PROTOCOL_VERSION = "DICOM"
DCM4CHEE_ORDER_MESSAGE_TYPE = "MWL"
DCM4CHEE_MWL_NON_RETRYABLE_ERROR_TYPES = {"patient_missing", "patient_sync_failed", "profile_invalid"}
DCM4CHEE_RESULT_SOURCE_SIMULATED_AP = "simulated_ap_return"
DCM4CHEE_DEFAULT_UID_ROOT = "1.2.826.0.1.3680043.10.543"
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
FHIR_RESOURCE_DEPENDENCY_ORDER = {
    "Patient": 10,
    "ServiceRequest": 20,
    "Binary": 40,
    "Observation": 50,
    "DocumentReference": 60,
    "DiagnosticReport": 70,
    "Provenance": 80,
}
FHIR_IDENTIFIER_SYSTEMS = {
    "Patient": "https://healthcare-lab.local/fhir/identifier/patient",
    "ServiceRequest": "https://healthcare-lab.local/fhir/identifier/service-request",
    "Binary": "https://healthcare-lab.local/fhir/identifier/binary",
    "Observation": "https://healthcare-lab.local/fhir/identifier/observation",
    "DocumentReference": "https://healthcare-lab.local/fhir/identifier/document-reference",
    "DiagnosticReport": "https://healthcare-lab.local/fhir/identifier/diagnostic-report",
    "Provenance": "https://healthcare-lab.local/fhir/identifier/provenance",
}
FHIR_RESOURCE_MAPPINGS = {
    "Patient": {
        "local_source_type": "local_patient_records",
        "depends_on": (),
    },
    "ServiceRequest": {
        "local_source_type": "local_order_records",
        "depends_on": ("Patient",),
    },
    "Binary": {
        "local_source_type": "local_fhir_artifacts",
        "depends_on": (),
    },
    "Observation": {
        "local_source_type": "local_fhir_results",
        "depends_on": ("Patient", "ServiceRequest"),
    },
    "DocumentReference": {
        "local_source_type": "local_fhir_artifacts",
        "depends_on": ("Patient", "ServiceRequest", "Binary"),
    },
    "DiagnosticReport": {
        "local_source_type": "local_fhir_results",
        "depends_on": ("Patient", "ServiceRequest", "Observation", "DocumentReference"),
    },
    "Provenance": {
        "local_source_type": "local_fhir_provenance",
        "depends_on": (
            "Patient",
            "ServiceRequest",
            "Binary",
            "Observation",
            "DocumentReference",
            "DiagnosticReport",
        ),
    },
}

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


def _gdt_clean_value(value: Any) -> str:
    return str(value if value is not None else "").strip().replace("\r", " ").replace("\n", " ")


def _encode_gdt_text(value: str) -> bytes:
    try:
        return value.encode(GDT_DEFAULT_ENCODING)
    except UnicodeEncodeError as exc:
        raise SimulatorValidationError(
            "GDT 2.1 patient fields must use ANSI/ISO-8859-1 compatible characters."
        ) from exc


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


# Compatibility re-exports; direct composition imports the owning modules.
from backend.clients.openemr import OpenEMRProcedureOrderSource
from backend.domain.openemr import (
    map_openemr_procedure_order_to_gdt_order,
    normalize_openemr_dob,
    normalize_openemr_gender,
    openemr_provider_name,
    openemr_row_source_key,
)


class DemoStore:
    def __init__(self, path: str | Path):
        self.database = SQLiteDatabase(
            path,
            migrations=APPLICATION_MIGRATIONS,
            maintenance=(
                ensure_application_schema,
                lambda connection: backfill_dcm4chee_mwl_mappings(
                    connection,
                    order_default_text=ORDER_DEFAULT_TEXT,
                    create_operation=DCM4CHEE_MWL_OPERATION_CREATE,
                    identifier_projector=dicom_domain.historical_mwl_identifiers,
                ),
                seed_patient_mrn_sequence,
                lambda connection: seed_lab_servers(
                    connection,
                    defaults=DEFAULT_LAB_SERVERS,
                    operation_metadata=DEFAULT_LAB_OPERATION_METADATA,
                    timestamp_factory=now_iso,
                ),
                lambda connection: seed_oie_settings_profile(
                    connection,
                    profile_name=OIE_SETTINGS_PROFILE_NAME,
                    management_api_base_url=OIE_MANAGEMENT_API_BASE_URL,
                    management_api_username=OIE_MANAGEMENT_API_USERNAME,
                    management_api_password=OIE_MANAGEMENT_API_PASSWORD,
                    management_api_timeout_seconds=OIE_MANAGEMENT_API_TIMEOUT_SECONDS,
                    result_listener_host=OIE_RESULT_LISTENER_HOST,
                    result_listener_port=OIE_RESULT_LISTENER_PORT,
                    timestamp_factory=now_iso,
                ),
            ),
        )
        self.path = self.database.path
        self.lock = self.database.lock
        self.initialize()
        from backend.repositories.oie_settings import (
            OieSettingsRepository,
            serialize_oie_settings_profile,
            validate_oie_settings_payload,
        )

        self.oie_settings_repository = OieSettingsRepository(
            self.database.connect,
            self.database.lock,
            profile_name=OIE_SETTINGS_PROFILE_NAME,
            validator=validate_oie_settings_payload,
            serializer=serialize_oie_settings_profile,
            timestamp_factory=now_iso,
        )
        self.lab_repository = LabRepository(
            self.database.connect,
            self.database.lock,
            timestamp_factory=now_iso,
        )
        self.oie_repository = OieRepository(
            self.database.connect,
            self.database.lock,
            timestamp_factory=now_iso,
            patient_protocol=PATIENT_MODES["hl7-v2"]["protocol"],
            order_protocol=ORDER_PROTOCOL_VERSION,
        )
        self.dcm4chee_patient_sync_repository = Dcm4cheePatientSyncRepository(
            self.database.connect,
            self.database.lock,
            patient_loader=lambda record_id: self.patient_repository.get_patient_record(record_id),
            identifiers=dicom_domain.patient_identifiers,
            timestamp_factory=now_iso,
        )
        self.dcm4chee_mwl_repository = Dcm4cheeMwlRepository(
            self.database.connect,
            self.database.lock,
            order_loader=lambda record_id: self.order_repository.get_order_record(record_id),
            identifiers_from_payload=lambda order, profile, **kwargs: dicom_templates.identifiers_from_payload(
                order, profile,
                uid_root=kwargs.get("uid_root", DCM4CHEE_DEFAULT_UID_ROOT),
                payload=kwargs.get("payload"),
                timestamp_factory=hl7_timestamp,
            ),
            uid_normalizer=dicom_domain.normalize_uid_root,
            study_uid_builder=lambda uid_root, **kwargs: dicom_domain.study_instance_uid(
                uid_root, timestamp_factory=hl7_timestamp, **kwargs
            ),
            local_order_number=dicom_domain.local_order_number,
            accession_number=dicom_domain.accession_number,
            requested_procedure_id=dicom_domain.requested_procedure_id,
            scheduled_procedure_step_id=dicom_domain.scheduled_procedure_step_id,
            timestamp_factory=now_iso,
        )
        self.dcm4chee_result_repository = Dcm4cheeResultRepository(
            self.database.connect,
            self.database.lock,
            mwl_mapping_loader=self.dcm4chee_mwl_repository.list_dcm4chee_mwl_mappings_for_patient,
            profile_identity=dicom_domain.profile_identity,
            link_builder=dicom_domain.result_links,
            result_key_builder=dicom_domain.result_key,
            timestamp_factory=now_iso,
        )
        self.patient_enrichment_loader = PatientEnrichmentLoader(
            self.database.connect,
            fhir_projector=self._fhir_workflow_record_dict,
            patient_sync_loader=self.dcm4chee_patient_sync_repository.load_latest_for_patients,
            result_loader=self.dcm4chee_result_repository.load_for_patients,
        )
        self.order_enrichment_loader = OrderEnrichmentLoader(
            self.database.connect,
            fhir_projector=self._fhir_workflow_record_dict,
            mwl_loader=self.dcm4chee_mwl_repository.load_for_orders,
        )
        self.patient_repository = PatientRepository(
            self.database.connect,
            self.database.lock,
            identifier_repository=PatientIdentifierRepository(),
            validator=patient_domain.validate_payload,
            payload_builder=partial(
                patient_templates.build,
                gdt_renderer=render_gdt_message,
            ),
            timestamp_factory=now_iso,
            hl7_timestamp_factory=hl7_timestamp,
            enrichment_loader=self.patient_enrichment_loader,
        )
        self.order_repository = OrderRepository(
            self.database.connect,
            self.database.lock,
            validator=order_domain.validate_payload,
            payload_builder=order_templates.build_orm,
            timestamp_factory=now_iso,
            hl7_timestamp_factory=hl7_timestamp,
            enrichment_loader=self.order_enrichment_loader,
            dcm4chee_status_view=dicom_domain.mwl_status_view,
        )
        self.dcm4chee_mwl_attempt_coordinator = Dcm4cheeMwlAttemptCoordinator(
            order_loader=self.order_repository.get_order_record,
            payload_builder=lambda order, profile, **kwargs: dicom_templates.build_mwl_payload(
                order,
                profile,
                uid_root=kwargs.get("uid_root", DCM4CHEE_DEFAULT_UID_ROOT),
                timestamp_factory=hl7_timestamp,
            ),
            attempt_creator=self.dcm4chee_mwl_repository.create_dcm4chee_mwl_attempt,
        )
        self.dcm4chee_workflow_coordinator = Dcm4cheeWorkflowCoordinator(
            patient_create=self.patient_repository.create_patient_record,
            patient_get=self.patient_repository.get_patient_record,
            order_create=self.order_repository.create_dcm4chee_order_record,
            order_get=self.order_repository.get_order_record,
            patient_sync_get=self.dcm4chee_patient_sync_repository.get_dcm4chee_patient_sync_for_patient,
            mwl_get=self.dcm4chee_mwl_repository.get_dcm4chee_mwl_mapping_for_order,
            mwl_upsert=self.dcm4chee_mwl_repository.upsert_dcm4chee_mwl_mapping,
            result_list=self.dcm4chee_result_repository.list_dcm4chee_results_for_patient,
            result_begin=self.dcm4chee_result_repository.begin_dcm4chee_result_refresh,
            result_upsert=self.dcm4chee_result_repository.upsert_dcm4chee_result_record,
            result_complete=self.dcm4chee_result_repository.complete_dcm4chee_result_refresh,
            latest_simulated_generation=self.dcm4chee_result_repository.latest_simulated_dcm4chee_ap_return_generation,
            mwl_payload_builder=lambda order, profile, **kwargs: dicom_templates.build_mwl_payload(
                order, profile, uid_root=kwargs.get("uid_root", DCM4CHEE_DEFAULT_UID_ROOT),
                timestamp_factory=hl7_timestamp,
            ),
            timestamp_factory=now_iso,
        )

    @contextmanager
    def connect(self):
        with self.database.connect() as connection:
            yield connection

    def initialize(self) -> None:
        self.database.initialize()

    def get_oie_settings_profile(self) -> dict[str, Any]:
        return self.oie_settings_repository.get()

    def update_oie_settings_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.oie_settings_repository.update(payload)

















    def create_patient_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.patient_repository.create_patient_record(payload)

    def list_patient_records(self, protocol_version: str = "") -> list[dict[str, Any]]:
        return self.patient_repository.list_patient_records(protocol_version)

    def get_patient_record(self, record_id: int) -> dict[str, Any]:
        return self.patient_repository.get_patient_record(record_id)

    def create_patient_fhir_workflow_record(self, patient_record: dict[str, Any]) -> dict[str, Any]:
        if patient_record.get("protocolVersion") != "FHIR R4":
            raise SimulatorValidationError("Patient record is not FHIR mode.")
        resource = self._json_value(patient_record.get("payload"), {})
        return self.create_fhir_workflow_record(
            {
                "localSourceType": "local_patient_records",
                "localSourceId": str(patient_record["id"]),
                "resourceType": "Patient",
                "resource": resource,
            }
        )

    def list_oie_local_adt_inventory(self) -> list[dict[str, Any]]:
        return self.list_patient_records(PATIENT_MODES["hl7-v2"]["protocol"])

    @staticmethod
    def _order_record_number(record_id: int) -> str:
        return f"ORD-{record_id:06d}"

    @staticmethod
    def _order_visit_id(record_id: int) -> str:
        return f"VISIT-ORD-{record_id:06d}"

    @staticmethod
    def _order_account_number(record_id: int) -> str:
        return f"ACC-ORD-{record_id:06d}"

    @staticmethod
    def _normalize_requested_at(value: Any) -> str:
        return order_domain.normalize_requested_at(value, default_factory=hl7_timestamp)

    @staticmethod
    def _clean_order_text(value: Any, field_name: str, required: bool = False) -> str:
        return order_domain.clean_text(value, field_name, required)




    @staticmethod
    def _dcm4chee_local_order_number(record_id: int) -> str:
        return dicom_domain.local_order_number(record_id)

    @staticmethod
    def _dcm4chee_accession_number(record_id: int) -> str:
        return dicom_domain.accession_number(record_id)

    @staticmethod
    def _dcm4chee_requested_procedure_id(record_id: int) -> str:
        return dicom_domain.requested_procedure_id(record_id)

    @staticmethod
    def _dcm4chee_scheduled_procedure_step_id(record_id: int) -> str:
        return dicom_domain.scheduled_procedure_step_id(record_id)

    @staticmethod
    def normalize_dcm4chee_uid_root(value: Any) -> str:
        return dicom_domain.normalize_uid_root(value)

    @classmethod
    def dcm4chee_study_instance_uid(cls, uid_root: Any, *, order_record_id: int, timestamp: str = "") -> str:
        return dicom_domain.study_instance_uid(
            uid_root, order_record_id=order_record_id, timestamp=timestamp,
            timestamp_factory=hl7_timestamp,
        )

    @staticmethod
    def _dicom_json_element(vr: str, value: Any = None) -> dict[str, Any]:
        return dicom_templates._json_element(vr, value)

    @classmethod
    def build_dcm4chee_mwl_payload(
        cls, order: dict[str, Any], profile: dict[str, Any], *,
        uid_root: Any = DCM4CHEE_DEFAULT_UID_ROOT,
    ) -> dict[str, Any]:
        return dicom_templates.build_mwl_payload(
            order, profile, uid_root=uid_root, timestamp_factory=hl7_timestamp
        )

    @classmethod
    def dcm4chee_patient_identifiers(cls, patient: dict[str, Any], profile: dict[str, Any]) -> dict[str, str]:
        return dicom_domain.patient_identifiers(patient, profile)

    @classmethod
    def build_dcm4chee_patient_adt_payload(
        cls, patient: dict[str, Any], profile: dict[str, Any], *,
        event_type: str = "A04", timestamp: str = "",
    ) -> str:
        return dicom_templates.build_patient_adt_payload(
            patient, profile, event_type=event_type, timestamp=timestamp,
            timestamp_factory=hl7_timestamp,
        )

    def upsert_dcm4chee_patient_sync(
        self, patient_record_id: int, profile: dict[str, Any], *,
        sync_status: str = DCM4CHEE_PATIENT_SYNC_STATUS_PENDING, increment_retry: bool = False,
    ) -> dict[str, Any]:
        return self.dcm4chee_patient_sync_repository.upsert_dcm4chee_patient_sync(
            patient_record_id, profile, sync_status=sync_status, increment_retry=increment_retry
        )

    def get_dcm4chee_patient_sync(self, sync_id: int) -> dict[str, Any]:
        return self.dcm4chee_patient_sync_repository.get_dcm4chee_patient_sync(sync_id)

    def get_dcm4chee_patient_sync_for_patient(
        self, patient_record_id: int, profile: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return self.dcm4chee_patient_sync_repository.get_dcm4chee_patient_sync_for_patient(patient_record_id, profile)

    def create_dcm4chee_patient_sync_attempt(self, *args, **kwargs) -> dict[str, Any]:
        return self.dcm4chee_patient_sync_repository.create_dcm4chee_patient_sync_attempt(*args, **kwargs)

    def update_dcm4chee_patient_sync_attempt_result(self, *args, **kwargs) -> dict[str, Any]:
        return self.dcm4chee_patient_sync_repository.update_dcm4chee_patient_sync_attempt_result(*args, **kwargs)

    def update_dcm4chee_patient_sync_from_attempt(self, *args, **kwargs) -> dict[str, Any]:
        return self.dcm4chee_patient_sync_repository.update_dcm4chee_patient_sync_from_attempt(*args, **kwargs)

    def get_dcm4chee_patient_sync_attempt(self, attempt_id: int) -> dict[str, Any]:
        return self.dcm4chee_patient_sync_repository.get_dcm4chee_patient_sync_attempt(attempt_id)

    def list_dcm4chee_patient_sync_attempts(self, patient_record_id: int | None = None) -> list[dict[str, Any]]:
        return self.dcm4chee_patient_sync_repository.list_dcm4chee_patient_sync_attempts(patient_record_id)





    @staticmethod
    def _fhir_order_values(payload: dict[str, Any]) -> dict[str, Any]:
        fhir = payload.get("fhir") if isinstance(payload.get("fhir"), dict) else payload
        return fhir if isinstance(fhir, dict) else {}

    @staticmethod
    def _clean_fhir_order_text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _fhir_order_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list | tuple):
            raw_items = value
        else:
            raw_items = str(value).replace(",", "\n").splitlines()
        return [str(item or "").strip() for item in raw_items if str(item or "").strip()]

    @staticmethod
    def _fhir_reference_item(value: str, field_name: str) -> dict[str, str]:
        text = value.strip()
        if not text:
            return {}
        if "/" not in text:
            raise SimulatorValidationError(f"FHIR Order {field_name} must be a FHIR reference like Resource/id.")
        return {"reference": text}

    @classmethod
    def _fhir_reference_list(cls, value: Any, field_name: str) -> list[dict[str, str]]:
        return [
            reference
            for reference in (
                cls._fhir_reference_item(item, field_name)
                for item in cls._fhir_order_list(value)
            )
            if reference
        ]

    @classmethod
    def _fhir_codeable_concept(
        cls,
        *,
        text: Any = "",
        code: Any = "",
        system: Any = "",
        display: Any = "",
    ) -> dict[str, Any]:
        concept: dict[str, Any] = {}
        text_value = cls._clean_fhir_order_text(text)
        code_value = cls._clean_fhir_order_text(code)
        system_value = cls._clean_fhir_order_text(system)
        display_value = cls._clean_fhir_order_text(display)
        if text_value:
            concept["text"] = text_value
        if code_value or system_value or display_value:
            coding: dict[str, str] = {}
            if system_value:
                coding["system"] = system_value
            if code_value:
                coding["code"] = code_value
            if display_value:
                coding["display"] = display_value
            concept["coding"] = [coding]
            if not concept.get("text"):
                concept["text"] = display_value or code_value
        return concept

    @staticmethod
    def _fhir_order_datetime(value: Any, fallback: str = "") -> str:
        text = str(value or "").strip()
        if not text:
            return fallback
        if "T" in text:
            match = re.match(
                r"^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::(\d{2})(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?$",
                text,
            )
            if not match:
                return text
            date_part, hour, minute, second, fraction, offset = match.groups()
            normalized = f"{date_part}T{hour}:{minute}:{second or '00'}{fraction or ''}"
            if offset:
                if offset != "Z" and ":" not in offset:
                    offset = f"{offset[:3]}:{offset[3:]}"
                return f"{normalized}{offset}"
            local_offset = datetime.now().astimezone().strftime("%z")
            return f"{normalized}{local_offset[:3]}:{local_offset[3:]}"
        digits = "".join(character for character in text if character.isdigit())
        if len(digits) == 8:
            return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
        if len(digits) >= 12:
            base = f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}T{digits[8:10]}:{digits[10:12]}"
            if len(digits) >= 14:
                base = f"{base}:{digits[12:14]}"
            else:
                base = f"{base}:00"
            local_offset = datetime.now().astimezone().strftime("%z")
            return f"{base}{local_offset[:3]}:{local_offset[3:]}"
        return text

    @staticmethod
    def _fhir_order_storage_timestamp(value: Any) -> str:
        text = str(value or "").strip()
        digits = "".join(character for character in text if character.isdigit())
        if len(digits) >= 14:
            return digits[:14]
        if len(digits) >= 12:
            return digits[:12]
        if len(digits) >= 8:
            return digits[:8]
        return hl7_timestamp()

    @staticmethod
    def _fhir_order_storage_priority(value: Any) -> str:
        normalized = str(value or FHIR_ORDER_DEFAULT_PRIORITY).strip().lower()
        return {
            "routine": "R",
            "stat": "S",
            "asap": "A",
            "urgent": "A",
        }.get(normalized, "R")

    @classmethod
    def _validate_fhir_order_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SimulatorValidationError("FHIR Order payload must be a JSON object.")
        try:
            patient_record_id = int(payload.get("patientRecordId"))
        except (TypeError, ValueError) as exc:
            raise SimulatorValidationError("FHIR Order patientRecordId is required.") from exc
        fhir = cls._fhir_order_values(payload)
        status = cls._clean_fhir_order_text(fhir.get("status") or FHIR_ORDER_DEFAULT_STATUS)
        intent = cls._clean_fhir_order_text(fhir.get("intent") or FHIR_ORDER_DEFAULT_INTENT)
        if not status:
            raise SimulatorValidationError("FHIR Order status is required.")
        if not intent:
            raise SimulatorValidationError("FHIR Order intent is required.")
        priority = cls._clean_fhir_order_text(fhir.get("priority") or FHIR_ORDER_DEFAULT_PRIORITY)
        occurrence = cls._fhir_order_datetime(fhir.get("occurrenceDateTime") or payload.get("requestedAt"))
        authored_on = cls._fhir_order_datetime(fhir.get("authoredOn"), fallback=now_iso())
        requested_at = cls._fhir_order_storage_timestamp(occurrence or authored_on)
        order_code = cls._clean_fhir_order_text(
            fhir.get("codeCode") or fhir.get("code") or payload.get("orderCode") or ORDER_DEFAULT_CODE
        )
        order_text = cls._clean_fhir_order_text(
            fhir.get("codeDisplay") or payload.get("orderCodeText") or ORDER_DEFAULT_TEXT
        )
        return {
            "patient_record_id": patient_record_id,
            "status": status,
            "intent": intent,
            "priority": priority,
            "requested_at": requested_at,
            "ordering_provider": cls._clean_fhir_order_text(
                fhir.get("requester") or payload.get("orderingProvider") or ORDER_DEFAULT_PROVIDER
            ),
            "clinical_indication": cls._clean_fhir_order_text(
                fhir.get("reasonCodeText") or payload.get("clinicalIndication")
            ),
            "order_code": order_code or ORDER_DEFAULT_CODE,
            "order_code_text": order_text or ORDER_DEFAULT_TEXT,
            "alternate_code": cls._clean_fhir_order_text(
                fhir.get("alternateCode") or payload.get("alternateCode") or ORDER_DEFAULT_ALT_CODE
            ),
            "alternate_code_text": cls._clean_fhir_order_text(
                fhir.get("alternateCodeText") or payload.get("alternateCodeText") or ORDER_DEFAULT_ALT_TEXT
            ),
            "alternate_code_system": cls._clean_fhir_order_text(
                fhir.get("alternateCodeSystem") or payload.get("alternateCodeSystem") or ORDER_DEFAULT_ALT_SYSTEM
            ),
            "fhir": dict(fhir),
            "occurrence": occurrence,
            "authored_on": authored_on,
        }


    @classmethod
    def _build_service_request_resource(
        cls,
        values: dict[str, Any],
        *,
        record_id: int,
        local_order_number: str,
        patient_reference: str,
    ) -> dict[str, Any]:
        fhir = values.get("fhir") or {}
        resource: dict[str, Any] = {
            "resourceType": "ServiceRequest",
            "status": values["status"],
            "intent": values["intent"],
            "subject": {"reference": patient_reference},
        }
        explicit_id = cls._clean_fhir_order_text(fhir.get("id") or fhir.get("serviceRequestId"))
        if explicit_id:
            resource["id"] = explicit_id

        identifier_system = cls._clean_fhir_order_text(
            fhir.get("identifierSystem") or FHIR_IDENTIFIER_SYSTEMS["ServiceRequest"]
        )
        identifier_value = cls._clean_fhir_order_text(
            fhir.get("identifierValue") or cls.fhir_identifier_value(
                "ServiceRequest",
                "local_order_records",
                record_id,
            )
        )
        resource["identifier"] = [{"system": identifier_system, "value": identifier_value}]
        for item in cls._fhir_order_list(fhir.get("identifier")):
            if "|" in item:
                system, value = item.split("|", 1)
                resource["identifier"].append({"system": system.strip(), "value": value.strip()})
            else:
                resource["identifier"].append({"value": item})

        instantiates_canonical = cls._fhir_order_list(fhir.get("instantiatesCanonical"))
        if instantiates_canonical:
            resource["instantiatesCanonical"] = instantiates_canonical
        instantiates_uri = cls._fhir_order_list(fhir.get("instantiatesUri"))
        if instantiates_uri:
            resource["instantiatesUri"] = instantiates_uri
        for key, field_name in (
            ("basedOn", "basedOn"),
            ("replaces", "replaces"),
            ("reasonReference", "reasonReference"),
            ("insurance", "insurance"),
            ("supportingInfo", "supportingInfo"),
            ("specimen", "specimen"),
            ("relevantHistory", "relevantHistory"),
        ):
            references = cls._fhir_reference_list(fhir.get(key), field_name)
            if references:
                resource[key] = references

        requisition_system = cls._clean_fhir_order_text(fhir.get("requisitionSystem"))
        requisition_value = cls._clean_fhir_order_text(fhir.get("requisitionValue"))
        if requisition_system or requisition_value:
            resource["requisition"] = {
                key: value
                for key, value in {
                    "system": requisition_system,
                    "value": requisition_value or local_order_number,
                }.items()
                if value
            }

        category = cls._fhir_codeable_concept(text=fhir.get("category") or FHIR_ORDER_DEFAULT_CATEGORY)
        if category:
            resource["category"] = [category]
        if values["priority"]:
            resource["priority"] = values["priority"]
        if "doNotPerform" in fhir:
            resource["doNotPerform"] = bool(fhir.get("doNotPerform"))

        code = cls._fhir_codeable_concept(
            text=fhir.get("codeText") or values["order_code_text"],
            code=fhir.get("codeCode") or values["order_code"],
            system=fhir.get("codeSystem") or "urn:healthcare-lab:service-code",
            display=fhir.get("codeDisplay") or values["order_code_text"],
        )
        if values.get("alternate_code"):
            coding = code.setdefault("coding", [])
            coding.append(
                {
                    key: value
                    for key, value in {
                        "system": values.get("alternate_code_system"),
                        "code": values.get("alternate_code"),
                        "display": values.get("alternate_code_text"),
                    }.items()
                    if value
                }
            )
        resource["code"] = code

        order_detail = cls._fhir_codeable_concept(text=fhir.get("orderDetail"))
        if order_detail:
            resource["orderDetail"] = [order_detail]
        quantity_value = cls._clean_fhir_order_text(fhir.get("quantityValue"))
        quantity_unit = cls._clean_fhir_order_text(fhir.get("quantityUnit"))
        if quantity_value or quantity_unit:
            quantity: dict[str, Any] = {}
            if quantity_value:
                try:
                    quantity["value"] = float(quantity_value)
                except ValueError:
                    raise SimulatorValidationError("FHIR Order quantity value must be numeric.")
            if quantity_unit:
                quantity["unit"] = quantity_unit
            resource["quantityQuantity"] = quantity

        encounter = cls._clean_fhir_order_text(fhir.get("encounter"))
        if encounter:
            resource["encounter"] = cls._fhir_reference_item(encounter, "encounter")
        if values.get("occurrence"):
            resource["occurrenceDateTime"] = values["occurrence"]
        if "asNeededBoolean" in fhir:
            resource["asNeededBoolean"] = bool(fhir.get("asNeededBoolean"))
        as_needed = cls._fhir_codeable_concept(text=fhir.get("asNeededCodeText"))
        if as_needed:
            resource["asNeededCodeableConcept"] = as_needed
        if values.get("authored_on"):
            resource["authoredOn"] = values["authored_on"]

        requester = cls._clean_fhir_order_text(fhir.get("requester") or values["ordering_provider"])
        if requester:
            resource["requester"] = (
                cls._fhir_reference_item(requester, "requester")
                if "/" in requester
                else {"display": requester}
            )
        performer_type = cls._fhir_codeable_concept(text=fhir.get("performerType"))
        if performer_type:
            resource["performerType"] = performer_type
        performer = cls._fhir_reference_list(fhir.get("performer"), "performer")
        if performer:
            resource["performer"] = performer
        location_code = cls._fhir_codeable_concept(text=fhir.get("locationCode"))
        if location_code:
            resource["locationCode"] = [location_code]
        location_reference = cls._fhir_reference_list(fhir.get("locationReference"), "locationReference")
        if location_reference:
            resource["locationReference"] = location_reference
        reason_code = cls._fhir_codeable_concept(text=fhir.get("reasonCodeText") or values["clinical_indication"])
        if reason_code:
            resource["reasonCode"] = [reason_code]
        body_site = cls._fhir_codeable_concept(text=fhir.get("bodySite"))
        if body_site:
            resource["bodySite"] = [body_site]
        note = cls._clean_fhir_order_text(fhir.get("note"))
        if note:
            resource["note"] = [{"text": note}]
        patient_instruction = cls._clean_fhir_order_text(fhir.get("patientInstruction"))
        if patient_instruction:
            resource["patientInstruction"] = patient_instruction
        return resource

    def create_order_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.order_repository.create_order_record(payload)

    def create_dcm4chee_order_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.order_repository.create_dcm4chee_order_record(payload)

    @staticmethod
    def _dicom_first_value(payload: dict[str, Any], tag: str, default: str = "") -> str:
        return dicom_domain.dicom_first_value(payload, tag, default)

    @staticmethod
    def _dcm4chee_sps_payload(payload: dict[str, Any]) -> dict[str, Any]:
        return dicom_domain.sps_payload(payload)

    @classmethod
    def dcm4chee_identifiers_from_payload(
        cls, order: dict[str, Any], profile: dict[str, Any], *,
        uid_root: Any = DCM4CHEE_DEFAULT_UID_ROOT, payload: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        return dicom_templates.identifiers_from_payload(
            order, profile, uid_root=uid_root, payload=payload, timestamp_factory=hl7_timestamp
        )

    @classmethod
    def dcm4chee_identifiers_from_response_body(cls, response_body: str) -> dict[str, str]:
        return dicom_domain.identifiers_from_response_body(response_body)

    @classmethod
    def dcm4chee_datasets_from_response_body(cls, response_body: str) -> list[dict[str, Any]]:
        return dicom_domain.datasets_from_response_body(response_body)

    @classmethod
    def dcm4chee_identifiers_from_dataset(cls, dataset: dict[str, Any]) -> dict[str, str]:
        return dicom_domain.identifiers_from_dataset(dataset)

    @staticmethod
    def dcm4chee_mwl_verification_query_from_mapping(mapping: dict[str, Any]) -> dict[str, str]:
        return dicom_domain.verification_query_from_mapping(mapping)

    def upsert_dcm4chee_mwl_mapping(self, *args, **kwargs) -> dict[str, Any]:
        return self.dcm4chee_mwl_repository.upsert_dcm4chee_mwl_mapping(*args, **kwargs)

    def update_dcm4chee_mwl_mapping_from_attempt(self, *args, **kwargs):
        return self.dcm4chee_mwl_repository.update_dcm4chee_mwl_mapping_from_attempt(*args, **kwargs)

    def get_dcm4chee_mwl_mapping_for_order(self, *args, **kwargs):
        return self.dcm4chee_mwl_repository.get_dcm4chee_mwl_mapping_for_order(*args, **kwargs)

    def find_dcm4chee_mwl_mapping_for_reconciliation(self, *args, **kwargs):
        return self.dcm4chee_mwl_repository.find_dcm4chee_mwl_mapping_for_reconciliation(*args, **kwargs)

    @classmethod
    def dcm4chee_result_metadata_from_dataset(cls, dataset: dict[str, Any]) -> dict[str, str]:
        return dicom_domain.result_metadata_from_dataset(dataset)

    @staticmethod
    def _dicom_sequence_first(payload: dict[str, Any], tag: str) -> dict[str, Any]:
        return dicom_domain.sequence_first(payload, tag)

    @classmethod
    def _dicom_datetime(cls, payload: dict[str, Any], date_tag: str, time_tag: str) -> str:
        return dicom_domain.dicom_datetime(payload, date_tag, time_tag)

    @staticmethod
    def _dcm4chee_profile_identity(profile: dict[str, Any]) -> tuple[str, str, str]:
        return dicom_domain.profile_identity(profile)

    @staticmethod
    def _dcm4chee_result_key(**kwargs) -> str:
        return dicom_domain.result_key(**kwargs)

    @staticmethod
    def _dcm4chee_patient_matches(mapping: dict[str, Any], metadata: dict[str, str]) -> bool:
        return dicom_domain.patient_matches(mapping, metadata)

    def _dcm4chee_mappings_for_patient(self, patient_record_id: int) -> list[dict[str, Any]]:
        return self.dcm4chee_mwl_repository.list_dcm4chee_mwl_mappings_for_patient(patient_record_id)

    def list_dcm4chee_mwl_mappings_for_patient(self, *args, **kwargs):
        return self.dcm4chee_mwl_repository.list_dcm4chee_mwl_mappings_for_patient(*args, **kwargs)

    def reconcile_dcm4chee_result_metadata(self, *args, **kwargs) -> dict[str, Any]:
        return self.dcm4chee_result_repository.reconcile_dcm4chee_result_metadata(*args, **kwargs)

    @staticmethod
    def dcm4chee_result_links(profile: dict[str, Any], metadata: dict[str, str]) -> dict[str, str]:
        return dicom_domain.result_links(profile, metadata)

    def upsert_dcm4chee_result_record(self, *args, **kwargs):
        return self.dcm4chee_result_repository.upsert_dcm4chee_result_record(*args, **kwargs)

    @staticmethod
    def dcm4chee_e2e_demo_patient_payload() -> dict[str, Any]:
        return Dcm4cheeWorkflowCoordinator.dcm4chee_e2e_demo_patient_payload()

    @staticmethod
    def dcm4chee_e2e_demo_order_payload(patient_record_id: int) -> dict[str, Any]:
        return Dcm4cheeWorkflowCoordinator.dcm4chee_e2e_demo_order_payload(patient_record_id)

    def create_dcm4chee_e2e_demo_fixture(self, *args, **kwargs):
        return self.dcm4chee_workflow_coordinator.create_dcm4chee_e2e_demo_fixture(*args, **kwargs)

    def dcm4chee_e2e_evidence_for_order(self, *args, **kwargs):
        return self.dcm4chee_workflow_coordinator.dcm4chee_e2e_evidence_for_order(*args, **kwargs)

    def create_simulated_dcm4chee_ap_return(self, *args, **kwargs):
        return self.dcm4chee_workflow_coordinator.create_simulated_dcm4chee_ap_return(*args, **kwargs)

    def latest_simulated_dcm4chee_ap_return_generation(self, *args, **kwargs):
        return self.dcm4chee_result_repository.latest_simulated_dcm4chee_ap_return_generation(*args, **kwargs)

    def record_dcm4chee_result_refresh_diagnostic(self, *args, **kwargs):
        return self.dcm4chee_result_repository.record_dcm4chee_result_refresh_diagnostic(*args, **kwargs)

    def _record_dcm4chee_result_refresh_run(self, *args, **kwargs):
        return self.dcm4chee_result_repository._record_dcm4chee_result_refresh_run(*args, **kwargs)

    def _dcm4chee_result_refresh_run_id(self, *args, **kwargs):
        return self.dcm4chee_result_repository._dcm4chee_result_refresh_run_id(*args, **kwargs)

    def _dcm4chee_result_row_is_newer_than_generation(self, *args, **kwargs):
        return self.dcm4chee_result_repository._dcm4chee_result_row_is_newer_than_generation(*args, **kwargs)

    def begin_dcm4chee_result_refresh(self, *args, **kwargs):
        return self.dcm4chee_result_repository.begin_dcm4chee_result_refresh(*args, **kwargs)

    def complete_dcm4chee_result_refresh(self, *args, **kwargs):
        return self.dcm4chee_result_repository.complete_dcm4chee_result_refresh(*args, **kwargs)

    def get_dcm4chee_result_record(self, *args, **kwargs):
        return self.dcm4chee_result_repository.get_dcm4chee_result_record(*args, **kwargs)

    def list_dcm4chee_results_for_patient(self, *args, **kwargs):
        return self.dcm4chee_result_repository.list_dcm4chee_results_for_patient(*args, **kwargs)

    def create_dcm4chee_mwl_attempt(self, *args, **kwargs):
        return self.dcm4chee_mwl_attempt_coordinator.create_dcm4chee_mwl_attempt(*args, **kwargs)

    def create_dcm4chee_mwl_profile_failure_attempt(self, *args, **kwargs):
        return self.dcm4chee_mwl_repository.create_dcm4chee_mwl_profile_failure_attempt(*args, **kwargs)

    def update_dcm4chee_mwl_attempt_result(self, *args, **kwargs):
        return self.dcm4chee_mwl_repository.update_dcm4chee_mwl_attempt_result(*args, **kwargs)

    def get_dcm4chee_mwl_attempt(self, *args, **kwargs):
        return self.dcm4chee_mwl_repository.get_dcm4chee_mwl_attempt(*args, **kwargs)

    def list_dcm4chee_mwl_attempts(self, *args, **kwargs):
        return self.dcm4chee_mwl_repository.list_dcm4chee_mwl_attempts(*args, **kwargs)

    def create_dcm4chee_mwl_verification_attempt(self, *args, **kwargs):
        return self.dcm4chee_mwl_repository.create_dcm4chee_mwl_verification_attempt(*args, **kwargs)

    def update_dcm4chee_mwl_verification_result(self, *args, **kwargs):
        return self.dcm4chee_mwl_repository.update_dcm4chee_mwl_verification_result(*args, **kwargs)

    def _synced_patient_reference_for_fhir_order(self, patient_record_id: int) -> str:
        patient = self.get_patient_record(patient_record_id)
        fhir = patient.get("fhir") or {}
        sync_status = (fhir.get("sync") or {}).get("status")
        reference = str((fhir.get("medplum") or {}).get("reference") or "").strip()
        if (
            patient.get("protocolVersion") != "FHIR R4"
            or sync_status != FHIR_SYNC_STATUS_SYNCED
            or not reference.startswith("Patient/")
        ):
            raise SimulatorValidationError(
                "FHIR Order requires a selected Patient with synced Medplum Patient/<id> reference."
            )
        return reference

    def create_fhir_order_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = self._validate_fhir_order_payload(payload)
        patient_reference = self._synced_patient_reference_for_fhir_order(values["patient_record_id"])
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            patient_row = connection.execute(
                "SELECT * FROM local_patient_records WHERE id = ?",
                (values["patient_record_id"],),
            ).fetchone()
            if not patient_row:
                raise KeyError(values["patient_record_id"])
            cursor = connection.execute(
                """
                INSERT INTO local_order_records (
                    local_order_number, patient_record_id, protocol_version, message_type,
                    order_status, mrn, first_name, last_name, middle_name, dob, sex,
                    visit_id, patient_class, assigned_location, account_number,
                    placer_order_number, filler_order_number, priority, requested_at,
                    ordering_provider, clinical_indication, order_code, order_code_text,
                    alternate_code, alternate_code_text, alternate_code_system,
                    validation_status, validation_messages_json, payload_hl7,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "",
                    values["patient_record_id"],
                    FHIR_ORDER_PROTOCOL_VERSION,
                    FHIR_ORDER_MESSAGE_TYPE,
                    FHIR_ORDER_STATUS_CREATED,
                    patient_row["mrn"],
                    patient_row["first_name"],
                    patient_row["last_name"],
                    patient_row["middle_name"],
                    patient_row["dob"],
                    patient_row["sex"],
                    patient_row["visit_number"],
                    patient_row["patient_class"],
                    patient_row["assigned_location"],
                    patient_row["account_number"],
                    "",
                    "",
                    self._fhir_order_storage_priority(values["priority"]),
                    values["requested_at"],
                    values["ordering_provider"],
                    values["clinical_indication"],
                    values["order_code"],
                    values["order_code_text"],
                    values["alternate_code"],
                    values["alternate_code_text"],
                    values["alternate_code_system"],
                    "valid",
                    "[]",
                    "",
                    timestamp,
                    timestamp,
                ),
            )
            record_id = int(cursor.lastrowid)
            local_order_number = self._order_record_number(record_id)
            visit_id = patient_row["visit_number"] or self._order_visit_id(record_id)
            account_number = patient_row["account_number"] or self._order_account_number(record_id)
            resource = self._build_service_request_resource(
                values,
                record_id=record_id,
                local_order_number=local_order_number,
                patient_reference=patient_reference,
            )
            connection.execute(
                """
                UPDATE local_order_records
                SET local_order_number = ?, placer_order_number = ?, visit_id = ?,
                    account_number = ?, payload_hl7 = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    local_order_number,
                    local_order_number,
                    visit_id,
                    account_number,
                    json.dumps(resource, indent=2, sort_keys=True),
                    timestamp,
                    record_id,
                ),
            )
        return self.get_order_record(record_id)

    def create_order_service_request_fhir_workflow_record(self, order: dict[str, Any]) -> dict[str, Any]:
        if order.get("protocolVersion") != FHIR_ORDER_PROTOCOL_VERSION:
            raise SimulatorValidationError("Order record is not FHIR mode.")
        resource = self._json_value(order.get("payload"), {})
        return self.create_fhir_workflow_record(
            {
                "localSourceType": "local_order_records",
                "localSourceId": str(order["id"]),
                "resourceType": "ServiceRequest",
                "resource": resource,
            }
        )

    def list_order_records(self, protocol_version: str = "") -> list[dict[str, Any]]:
        return self.order_repository.list_order_records(protocol_version)

    def get_order_record(self, record_id: int) -> dict[str, Any]:
        return self.order_repository.get_order_record(record_id)

    def update_order_send_result(
        self,
        record_id: int,
        *,
        order_status: str,
        ack_code: str = "",
        ack_control_id: str = "",
        ack_text: str = "",
        ack_payload: str = "",
        transport_error: str = "",
    ) -> dict[str, Any]:
        return self.order_repository.update_order_send_result(
            record_id,
            order_status=order_status,
            ack_code=ack_code,
            ack_control_id=ack_control_id,
            ack_text=ack_text,
            ack_payload=ack_payload,
            transport_error=transport_error,
        )

    def list_oie_local_order_inventory(self) -> list[dict[str, Any]]:
        return self.list_order_records(ORDER_PROTOCOL_VERSION)

    @staticmethod
    def _gdt_order_record_number(record_id: int) -> str:
        return f"GDT-ORD-{record_id:06d}"

    @staticmethod
    def _gdt_patient_context_number(patient_record_id: int) -> str:
        return f"GDT-PAT-{patient_record_id:06d}"

    @staticmethod
    def _validate_gdt_patient_number(value: Any, field_name: str = "gdtPatientNumber") -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if len(text) > 64:
            raise SimulatorValidationError(f"{field_name} must be 64 characters or fewer.")
        if any(character in text for character in "\r\n"):
            raise SimulatorValidationError(f"{field_name} cannot contain line breaks.")
        _encode_gdt_text(text)
        return text

    @staticmethod
    def _gdt_patient_snapshot(patient_row: sqlite3.Row, gdt_patient_number: str) -> dict[str, Any]:
        return {
            "patientRecordId": patient_row["id"],
            "mrn": patient_row["mrn"],
            "gdtPatientNumber": gdt_patient_number,
            "firstName": patient_row["first_name"],
            "middleName": patient_row["middle_name"],
            "lastName": patient_row["last_name"],
            "dob": patient_row["dob"],
            "sex": patient_row["sex"],
            "visitNumber": patient_row["visit_number"],
        }

    @staticmethod
    def _gdt_attachment_filename(url: str, path: str = "") -> str:
        source = path or url
        return source.rstrip("/").replace("\\", "/").split("/")[-1] if source else ""

    @staticmethod
    def _is_url_reference(value: str) -> bool:
        return value.lower().startswith(("http://", "https://"))

    @staticmethod
    def _gdt_artifact_status(reference: str, bridge_root: str = "") -> tuple[str, dict[str, Any]]:
        normalized = str(reference or "").strip()
        if not normalized:
            return "missing-reference", {"warning": "Artifact reference is empty."}
        if DemoStore._is_url_reference(normalized):
            return "reference-only", {"kind": "url"}
        reference_path = Path(normalized)
        candidates = [reference_path]
        if bridge_root and not reference_path.is_absolute():
            root = Path(bridge_root)
            candidates.extend([root / normalized, root / "reports" / normalized])
        if any(candidate.exists() for candidate in candidates):
            return "available", {"kind": "path"}
        return "warning", {"warning": "Referenced artifact target was not found.", "reference": normalized}

    def _record_gdt_event(
        self,
        connection: sqlite3.Connection,
        *,
        event_type: str,
        timestamp: str,
        order_record_id: int | None = None,
        patient_context_id: int | None = None,
        message_record_id: int | None = None,
        attachment_record_id: int | None = None,
        actor: str = "",
        details: dict[str, Any] | None = None,
    ) -> int:
        cursor = connection.execute(
            """
            INSERT INTO local_gdt_workflow_events (
                order_record_id, patient_context_id, message_record_id,
                attachment_record_id, event_type, actor, details_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_record_id,
                patient_context_id,
                message_record_id,
                attachment_record_id,
                event_type,
                actor,
                json.dumps(details or {}, sort_keys=True),
                timestamp,
            ),
        )
        return int(cursor.lastrowid)

    def _ensure_gdt_patient_context(
        self,
        connection: sqlite3.Connection,
        patient_row: sqlite3.Row,
        *,
        override: str = "",
        timestamp: str,
    ) -> sqlite3.Row:
        context = connection.execute(
            """
            SELECT * FROM local_gdt_patient_contexts
            WHERE patient_record_id = ?
            """,
            (patient_row["id"],),
        ).fetchone()
        generated = self._gdt_patient_context_number(int(patient_row["id"]))
        override = self._validate_gdt_patient_number(override, "gdtPatientNumberOverride")
        effective = override or generated
        patient_snapshot_json = json.dumps(
            self._gdt_patient_snapshot(patient_row, effective),
            sort_keys=True,
        )
        if not context:
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO local_gdt_patient_contexts (
                        patient_record_id, generated_gdt_patient_number,
                        gdt_patient_number_override, effective_gdt_patient_number,
                        patient_snapshot_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        patient_row["id"],
                        generated,
                        override,
                        effective,
                        patient_snapshot_json,
                        timestamp,
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise SimulatorValidationError("GDT patient number must be unique.") from exc
            context_id = int(cursor.lastrowid)
            self._record_gdt_event(
                connection,
                event_type="patient-number-generated",
                patient_context_id=context_id,
                timestamp=timestamp,
                details={"generatedGdtPatientNumber": generated},
            )
            if override:
                self._record_gdt_event(
                    connection,
                    event_type="patient-number-overridden",
                    patient_context_id=context_id,
                    timestamp=timestamp,
                    details={
                        "generatedGdtPatientNumber": generated,
                        "effectiveGdtPatientNumber": effective,
                    },
                )
        elif override and override != context["gdt_patient_number_override"]:
            try:
                connection.execute(
                    """
                    UPDATE local_gdt_patient_contexts
                    SET gdt_patient_number_override = ?,
                        effective_gdt_patient_number = ?,
                        patient_snapshot_json = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (override, effective, patient_snapshot_json, timestamp, context["id"]),
                )
            except sqlite3.IntegrityError as exc:
                raise SimulatorValidationError("GDT patient number must be unique.") from exc
            self._record_gdt_event(
                connection,
                event_type="patient-number-overridden",
                patient_context_id=context["id"],
                timestamp=timestamp,
                details={
                    "previousGdtPatientNumber": context["effective_gdt_patient_number"],
                    "effectiveGdtPatientNumber": effective,
                },
            )
        else:
            effective = context["effective_gdt_patient_number"]
            patient_snapshot_json = json.dumps(
                self._gdt_patient_snapshot(patient_row, effective),
                sort_keys=True,
            )
            connection.execute(
                """
                UPDATE local_gdt_patient_contexts
                SET patient_snapshot_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (patient_snapshot_json, timestamp, context["id"]),
            )
        return connection.execute(
            """
            SELECT * FROM local_gdt_patient_contexts
            WHERE patient_record_id = ?
            """,
            (patient_row["id"],),
        ).fetchone()

    def _create_gdt_message_record(
        self,
        connection: sqlite3.Connection,
        *,
        order_record_id: int | None,
        patient_context_id: int | None,
        direction: str,
        raw_gdt_text: str,
        canonical: dict[str, Any],
        timestamp: str,
        match_status: str = "",
        error_text: str = "",
    ) -> int:
        parsed_fields = parse_gdt_message(raw_gdt_text)
        message_type = first_gdt_field(parsed_fields, "8000")
        cursor = connection.execute(
            """
            INSERT INTO local_gdt_message_records (
                order_record_id, patient_context_id, direction, message_type,
                raw_gdt_text, parsed_fields_json, canonical_json, parse_status,
                match_status, error_text, generated_at, received_at,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'accepted', ?, ?, ?, ?, ?, ?)
            """,
            (
                order_record_id,
                patient_context_id,
                direction,
                message_type,
                raw_gdt_text,
                json.dumps(parsed_fields, sort_keys=True),
                json.dumps(canonical, sort_keys=True),
                match_status,
                error_text,
                timestamp if direction == "outbound" else "",
                timestamp if direction == "inbound" else "",
                timestamp,
                timestamp,
            ),
        )
        return int(cursor.lastrowid)

    def _create_gdt_attachment_record(
        self,
        connection: sqlite3.Connection,
        *,
        order_record_id: int | None,
        message_record_id: int | None,
        role: str,
        timestamp: str,
        url: str = "",
        path: str = "",
        reference: str = "",
        content_type: str = "",
        description: str = "",
        source_file: str = "",
        status: str = "",
        details: dict[str, Any] | None = None,
        filename: str = "",
        checksum: str = "",
    ) -> int:
        normalized_role = self._clean_order_text(role, "attachment role") or "other"
        normalized_url = self._clean_order_text(url, "attachment url")
        normalized_path = self._clean_order_text(path, "attachment path")
        normalized_reference = self._clean_order_text(reference, "attachment reference") or normalized_url or normalized_path
        normalized_filename = self._clean_order_text(filename, "attachment filename") or self._gdt_attachment_filename(
            normalized_url,
            normalized_path or normalized_reference,
        )
        cursor = connection.execute(
            """
            INSERT INTO local_gdt_attachment_records (
                order_record_id, message_record_id, role, url, path, reference,
                content_type, description, source_file, status, details_json,
                filename, checksum, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_record_id,
                message_record_id,
                normalized_role,
                normalized_url,
                normalized_path,
                normalized_reference,
                self._clean_order_text(content_type, "attachment contentType"),
                self._clean_order_text(description, "attachment description"),
                self._clean_order_text(source_file, "attachment sourceFile"),
                self._clean_order_text(status, "attachment status"),
                json.dumps(details or {}, sort_keys=True),
                normalized_filename,
                self._clean_order_text(checksum, "attachment checksum"),
                timestamp,
                timestamp,
            ),
        )
        attachment_id = int(cursor.lastrowid)
        self._record_gdt_event(
            connection,
            event_type="attachment-registered",
            order_record_id=order_record_id,
            message_record_id=message_record_id,
            attachment_record_id=attachment_id,
            timestamp=timestamp,
            details={
                "role": normalized_role,
                "filename": normalized_filename,
                "status": self._clean_order_text(status, "attachment status"),
            },
        )
        return attachment_id

    @staticmethod
    def _validate_gdt_8402_code(value: Any) -> str:
        normalized = str(value or GDT_ORDER_TEST_CODE).strip().upper()
        if normalized != GDT_ORDER_TEST_CODE:
            raise SimulatorValidationError(
                f"GDT ECG order MVP only supports {GDT_ORDER_TEST_CODE_FIELD}={GDT_ORDER_TEST_CODE}."
            )
        prefix = normalized[:-2]
        suffix = normalized[-2:]
        if (
            not 1 <= len(normalized) <= 6
            or not prefix.isalpha()
            or not prefix.isupper()
            or len(prefix) > 4
            or not suffix.isdigit()
        ):
            raise SimulatorValidationError(
                "GDT 8402 test code must use up to four uppercase letters followed by two digits."
            )
        return normalized

    def _validate_gdt_order_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SimulatorValidationError("GDT order payload must be a JSON object.")
        try:
            patient_record_id = int(payload.get("patientRecordId"))
        except (TypeError, ValueError) as exc:
            raise SimulatorValidationError("GDT order patientRecordId is required.") from exc
        return {
            "patient_record_id": patient_record_id,
            "requested_at": self._normalize_requested_at(payload.get("requestedAt")),
            "ordering_provider": self._clean_order_text(payload.get("orderingProvider"), "orderingProvider"),
            "clinical_indication": self._clean_order_text(payload.get("clinicalIndication"), "clinicalIndication"),
            "attachment_url": self._clean_order_text(payload.get("attachmentUrl"), "attachmentUrl"),
            "gdt_patient_number_override": self._validate_gdt_patient_number(
                payload.get(
                    "gdtPatientNumberOverride",
                    payload.get("gdtPatientNumber", payload.get("patientNumberOverride", "")),
                ),
                "gdtPatientNumberOverride",
            ),
            "gdt_test_code": self._validate_gdt_8402_code(
                payload.get("gdtTestCode", payload.get("testCode", payload.get("examCode", GDT_ORDER_TEST_CODE)))
            ),
        }

    @staticmethod
    def _gdt_birth_date(dob: str) -> str:
        return f"{dob[6:]}{dob[4:6]}{dob[:4]}"

    @staticmethod
    def _build_gdt_order_payload(
        values: dict[str, Any],
        patient_row: sqlite3.Row,
        *,
        record_id: int,
    ) -> str:
        order_number = values.get("local_gdt_order_number") or DemoStore._gdt_order_record_number(record_id)
        try:
            return build_gdt_6302_request(
                {
                    "gdtPatientNumber": values["gdt_patient_number"],
                    "lastName": patient_row["last_name"],
                    "firstName": patient_row["first_name"],
                    "birthDate": DemoStore._gdt_birth_date(patient_row["dob"]),
                    "localGdtOrderNumber": order_number,
                    "sex": GDT_PATIENT_SEX_CODES.get(patient_row["sex"], ""),
                    "requestedAt": values.get("requested_at", ""),
                    "orderingProvider": values.get("ordering_provider", ""),
                    "clinicalIndication": values.get("clinical_indication", ""),
                    "patient": DemoStore._gdt_patient_snapshot(patient_row, values["gdt_patient_number"]),
                    "order": {"localGdtOrderNumber": order_number},
                    "testLabel": GDT_ORDER_TEST_LABEL,
                }
            ).raw_gdt_text
        except GdtValidationError as exc:
            raise SimulatorValidationError(str(exc)) from exc

    def create_gdt_order_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = self._validate_gdt_order_payload(payload)
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            patient_row = connection.execute(
                "SELECT * FROM local_patient_records WHERE id = ?",
                (values["patient_record_id"],),
            ).fetchone()
            if not patient_row:
                raise KeyError(values["patient_record_id"])
            patient_context = self._ensure_gdt_patient_context(
                connection,
                patient_row,
                override=values["gdt_patient_number_override"],
                timestamp=timestamp,
            )
            gdt_patient_number = patient_context["effective_gdt_patient_number"]
            patient_snapshot = self._gdt_patient_snapshot(patient_row, gdt_patient_number)
            order_snapshot = {
                "requestedAt": values["requested_at"],
                "orderingProvider": values["ordering_provider"],
                "clinicalIndication": values["clinical_indication"],
                "gdtTestField": GDT_ORDER_TEST_CODE_FIELD,
                "gdtTestCode": values["gdt_test_code"],
                "gdtTestLabel": GDT_ORDER_TEST_LABEL,
            }
            cursor = connection.execute(
                """
                INSERT INTO local_gdt_order_records (
                    local_gdt_order_number, patient_record_id, gdt_patient_context_id,
                    protocol_version, message_type, order_status, mrn,
                    gdt_patient_number, first_name, last_name, middle_name, dob,
                    sex, visit_number, gdt_test_code,
                    gdt_test_label, requested_at, ordering_provider,
                    clinical_indication, attachment_url, payload_gdt,
                    patient_snapshot_json, order_snapshot_json,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "",
                    values["patient_record_id"],
                    patient_context["id"],
                    GDT_ORDER_PROTOCOL_VERSION,
                    GDT_ORDER_MESSAGE_TYPE,
                    GDT_ORDER_STATUS_CREATED,
                    patient_row["mrn"],
                    gdt_patient_number,
                    patient_row["first_name"],
                    patient_row["last_name"],
                    patient_row["middle_name"],
                    patient_row["dob"],
                    patient_row["sex"],
                    patient_row["visit_number"],
                    values["gdt_test_code"],
                    GDT_ORDER_TEST_LABEL,
                    values["requested_at"],
                    values["ordering_provider"],
                    values["clinical_indication"],
                    values["attachment_url"],
                    "",
                    json.dumps(patient_snapshot, sort_keys=True),
                    json.dumps(order_snapshot, sort_keys=True),
                    timestamp,
                    timestamp,
                ),
            )
            record_id = int(cursor.lastrowid)
            local_gdt_order_number = self._gdt_order_record_number(record_id)
            order_snapshot = {**order_snapshot, "localGdtOrderNumber": local_gdt_order_number}
            try:
                adapter_result = build_gdt_6302_request(
                    {
                        "gdtPatientNumber": gdt_patient_number,
                        "lastName": patient_row["last_name"],
                        "firstName": patient_row["first_name"],
                        "birthDate": self._gdt_birth_date(patient_row["dob"]),
                        "localGdtOrderNumber": local_gdt_order_number,
                        "sex": GDT_PATIENT_SEX_CODES.get(patient_row["sex"], ""),
                        "requestedAt": values["requested_at"],
                        "orderingProvider": values["ordering_provider"],
                        "clinicalIndication": values["clinical_indication"],
                        "patient": patient_snapshot,
                        "order": order_snapshot,
                        "testLabel": GDT_ORDER_TEST_LABEL,
                    }
                )
            except GdtValidationError as exc:
                raise SimulatorValidationError(str(exc)) from exc
            payload_gdt = adapter_result.raw_gdt_text
            canonical = adapter_result.canonical
            message_record_id = self._create_gdt_message_record(
                connection,
                order_record_id=record_id,
                patient_context_id=patient_context["id"],
                direction="outbound",
                raw_gdt_text=payload_gdt,
                canonical=canonical,
                timestamp=timestamp,
            )
            connection.execute(
                """
                UPDATE local_gdt_order_records
                SET local_gdt_order_number = ?, payload_gdt = ?,
                    order_snapshot_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    local_gdt_order_number,
                    payload_gdt,
                    json.dumps(order_snapshot, sort_keys=True),
                    timestamp,
                    record_id,
                ),
            )
            self._record_gdt_event(
                connection,
                event_type="order-created",
                order_record_id=record_id,
                patient_context_id=patient_context["id"],
                timestamp=timestamp,
                details={"localGdtOrderNumber": local_gdt_order_number},
            )
            self._record_gdt_event(
                connection,
                event_type="message-generated",
                order_record_id=record_id,
                patient_context_id=patient_context["id"],
                message_record_id=message_record_id,
                timestamp=timestamp,
                details={"messageType": GDT_ORDER_MESSAGE_TYPE},
            )
            if values["attachment_url"]:
                self._create_gdt_attachment_record(
                    connection,
                    order_record_id=record_id,
                    message_record_id=message_record_id,
                    role="order-attachment",
                    url=values["attachment_url"],
                    timestamp=timestamp,
                )
        return self.get_gdt_order_record(record_id)

    def list_gdt_order_records(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM local_gdt_order_records
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
        return [self._gdt_order_record_dict(row) for row in rows]

    def get_gdt_order_record(self, record_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_gdt_order_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
        return self._gdt_order_record_dict(row)

    def list_gdt_messages(self, order_record_id: int | None = None) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if order_record_id is None:
                rows = connection.execute(
                    """
                    SELECT * FROM local_gdt_message_records
                    ORDER BY created_at DESC, id DESC
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM local_gdt_message_records
                    WHERE order_record_id = ?
                    ORDER BY created_at DESC, id DESC
                    """,
                    (order_record_id,),
                ).fetchall()
        return [self._gdt_message_record_dict(row) for row in rows]

    def list_gdt_events(self, order_record_id: int | None = None) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if order_record_id is None:
                rows = connection.execute(
                    """
                    SELECT * FROM local_gdt_workflow_events
                    ORDER BY created_at DESC, id DESC
                    """
                ).fetchall()
            else:
                order_row = connection.execute(
                    "SELECT gdt_patient_context_id FROM local_gdt_order_records WHERE id = ?",
                    (order_record_id,),
                ).fetchone()
                patient_context_id = order_row["gdt_patient_context_id"] if order_row else None
                rows = connection.execute(
                    """
                    SELECT * FROM local_gdt_workflow_events
                    WHERE order_record_id = ?
                       OR (
                         ? IS NOT NULL
                         AND patient_context_id = ?
                         AND order_record_id IS NULL
                       )
                    ORDER BY created_at ASC, id ASC
                    """,
                    (order_record_id, patient_context_id, patient_context_id),
                ).fetchall()
        return [self._gdt_event_record_dict(row) for row in rows]

    def list_gdt_attachments(self, order_record_id: int | None = None) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if order_record_id is None:
                rows = connection.execute(
                    """
                    SELECT * FROM local_gdt_attachment_records
                    ORDER BY created_at DESC, id DESC
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM local_gdt_attachment_records
                    WHERE order_record_id = ?
                    ORDER BY created_at ASC, id ASC
                    """,
                    (order_record_id,),
                ).fetchall()
        return [self._gdt_attachment_record_dict(row) for row in rows]

    def record_gdt_order_export(
        self,
        order_record_id: int,
        *,
        export_path: str,
        status: str,
        error_text: str = "",
    ) -> dict[str, Any]:
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_gdt_order_records WHERE id = ?",
                (order_record_id,),
            ).fetchone()
            if not row:
                raise KeyError(order_record_id)
            connection.execute(
                """
                UPDATE local_gdt_order_records
                SET export_path = ?, error_text = ?, updated_at = ?
                WHERE id = ?
                """,
                (export_path, error_text, timestamp, order_record_id),
            )
            self._record_gdt_event(
                connection,
                event_type="order-exported" if status == "exported" else "order-export-failed",
                order_record_id=order_record_id,
                patient_context_id=row["gdt_patient_context_id"],
                timestamp=timestamp,
                details={"status": status, "path": export_path, "error": error_text},
            )
        return self.get_gdt_order_record(order_record_id)

    def create_gdt_demo_result(self, order_record_id: int) -> dict[str, Any]:
        order = self.get_gdt_order_record(order_record_id)
        order_number = order["localGdtOrderNumber"]
        artifact_prefix = order_number.lower()
        raw_gdt_text = render_gdt_message(
            [
                ("8315", "HCLAB"),
                ("8316", "DEMOECG"),
                ("3000", order["gdtPatientNumber"]),
                ("3101", order["patientSnapshot"].get("lastName", "")),
                ("3102", order["patientSnapshot"].get("firstName", "")),
                ("6200", order_number),
                ("8402", GDT_ORDER_TEST_CODE),
                ("8410", "HR"),
                ("8420", "72"),
                ("8421", "bpm"),
                ("8410", "PR"),
                ("8420", "160"),
                ("8421", "ms"),
                ("8410", "QRS"),
                ("8420", "92"),
                ("8421", "ms"),
                ("8410", "QT"),
                ("8420", "390"),
                ("8421", "ms"),
                ("8410", "QTC"),
                ("8420", "427"),
                ("8421", "ms"),
                ("8418", "final"),
                ("6220", "Normal sinus rhythm. No acute ST-T changes."),
                ("6227", "Demo ECG generated by Healthcare Lab."),
                ("6228", "Measurements are deterministic for bridge validation."),
                ("6302", "report"),
                ("6303", "PDF"),
                ("6304", "ECG PDF report"),
                ("6305", f"reports/{artifact_prefix}-report.pdf"),
                ("6302", "dicom"),
                ("6303", "DICOM"),
                ("6304", "DICOM ECG object reference"),
                ("6305", f"reports/{artifact_prefix}.dcm"),
            ],
            set_type=GDT_RESULT_MESSAGE_TYPE,
        )
        return self.record_gdt_result({"rawGdtText": raw_gdt_text, "sourceFile": "demo-result"})

    def list_gdt_workbench(self, *, bridge_inbox: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        patients = self.list_patient_records()
        orders = self.list_gdt_order_records()
        messages = self.list_gdt_messages()
        inbound_results = [
            item for item in messages
            if item.get("direction") == "inbound" and item.get("messageType") == GDT_RESULT_MESSAGE_TYPE
        ]
        attachments = self.list_gdt_attachments()
        orders_by_patient: dict[int, list[dict[str, Any]]] = {}
        results_by_order: dict[int, list[dict[str, Any]]] = {}
        results_by_patient_context: dict[int, list[dict[str, Any]]] = {}
        attachments_by_message: dict[int, list[dict[str, Any]]] = {}
        for order in orders:
            orders_by_patient.setdefault(int(order["patientRecordId"]), []).append(order)
        for result in inbound_results:
            if result.get("orderRecordId"):
                results_by_order.setdefault(int(result["orderRecordId"]), []).append(result)
            if result.get("patientContextId"):
                results_by_patient_context.setdefault(int(result["patientContextId"]), []).append(result)
        for attachment in attachments:
            if attachment.get("messageRecordId"):
                attachments_by_message.setdefault(int(attachment["messageRecordId"]), []).append(attachment)
        for result in inbound_results:
            result["attachments"] = attachments_by_message.get(int(result["id"]), [])
        workbench_patients = []
        for patient in patients:
            patient_id = int(patient["id"])
            patient_orders = orders_by_patient.get(patient_id, [])
            if not patient_orders and patient.get("protocolVersion") != GDT_ORDER_PROTOCOL_VERSION:
                continue
            patient_context_ids = {
                int(order["gdtPatientContextId"])
                for order in patient_orders
                if order.get("gdtPatientContextId")
            }
            patient_results = [
                result
                for context_id in patient_context_ids
                for result in results_by_patient_context.get(context_id, [])
            ]
            item = {
                **patient,
                "orders": patient_orders,
                "results": patient_results,
                "orderCount": len(patient_orders),
                "resultCount": len(patient_results),
            }
            item["summary"] = {
                **item["summary"],
                "orderCount": len(patient_orders),
                "resultCount": len(patient_results),
            }
            workbench_patients.append(item)
        unmatched_results = [
            result for result in inbound_results
            if not result.get("orderRecordId") and not result.get("patientContextId")
        ]
        return {
            "patients": workbench_patients,
            "orders": orders,
            "results": inbound_results,
            "unmatchedResults": unmatched_results,
            "attachments": attachments,
            "bridgeInbox": bridge_inbox or [],
            "resultsByOrder": results_by_order,
        }

    @staticmethod
    def _attachment_payloads_from_result_fields(fields: dict[str, list[str]]) -> list[dict[str, str]]:
        return attachment_payloads_from_result_fields(fields)

    @staticmethod
    def _gdt_result_measurements(fields: dict[str, list[str]]) -> dict[str, str]:
        return {
            label: first_gdt_field(fields, code)
            for label, code in (
                ("HR", "8401"),
                ("PR", "8402"),
                ("QRS", "8403"),
                ("QT", "8404"),
                ("QTC", "8405"),
            )
            if first_gdt_field(fields, code)
        }

    def record_gdt_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SimulatorValidationError("GDT result payload must be a JSON object.")
        raw_gdt_text = str(
            payload.get("rawGdtText", payload.get("payload", payload.get("raw", ""))) or ""
        )
        source_file = str(payload.get("sourceFile") or payload.get("source_file") or "").strip()
        try:
            adapter_result = parse_gdt_6310_result(raw_gdt_text)
        except GdtValidationError as exc:
            raise SimulatorValidationError(str(exc)) from exc
        fields = adapter_result.parsed_fields
        timestamp = now_iso()
        order_identifiers = [
            value
            for code in ("6330", "6200", "8410")
            for value in fields.get(code, [])
            if value
        ]
        gdt_patient_number = first_gdt_field(fields, "3000")
        with self.lock, self.connect() as connection:
            order_row = None
            if order_identifiers:
                placeholders = ", ".join("?" for _ in order_identifiers)
                order_row = connection.execute(
                    f"""
                    SELECT * FROM local_gdt_order_records
                    WHERE local_gdt_order_number IN ({placeholders})
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    order_identifiers,
                ).fetchone()
            patient_context_id = order_row["gdt_patient_context_id"] if order_row else None
            if not patient_context_id and gdt_patient_number:
                context_row = connection.execute(
                    """
                    SELECT * FROM local_gdt_patient_contexts
                    WHERE effective_gdt_patient_number = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (gdt_patient_number,),
                ).fetchone()
                patient_context_id = context_row["id"] if context_row else None
            match_status = "order-matched" if order_row else "unmatched"
            canonical = adapter_result.canonical
            canonical["order"] = {
                **canonical.get("order", {}),
                "localGdtOrderNumber": order_row["local_gdt_order_number"] if order_row else "",
                "identifiers": order_identifiers,
            }
            canonical["correlation"] = {
                **canonical.get("correlation", {}),
                "matchStatus": match_status,
                "identifiers": order_identifiers,
            }
            message_record_id = self._create_gdt_message_record(
                connection,
                order_record_id=order_row["id"] if order_row else None,
                patient_context_id=patient_context_id,
                direction="inbound",
                raw_gdt_text=raw_gdt_text,
                canonical=canonical,
                timestamp=timestamp,
                match_status=match_status,
            )
            attachment_payloads = canonical["attachments"] + list(payload.get("attachments") or [])
            for attachment in attachment_payloads:
                if not isinstance(attachment, dict):
                    continue
                reference = str(attachment.get("reference") or "")
                path = str(attachment.get("path") or "")
                url = str(attachment.get("url") or "")
                artifact_status, artifact_details = self._gdt_artifact_status(
                    reference or path or url,
                    str(payload.get("bridgeRoot") or payload.get("bridge_root") or ""),
                )
                explicit_status = str(attachment.get("status") or "")
                details = attachment.get("details") if isinstance(attachment.get("details"), dict) else {}
                self._create_gdt_attachment_record(
                    connection,
                    order_record_id=order_row["id"] if order_row else None,
                    message_record_id=message_record_id,
                    role=str(attachment.get("role") or "result-artifact"),
                    url=url,
                    path=path,
                    reference=reference,
                    content_type=str(attachment.get("contentType") or attachment.get("content_type") or ""),
                    description=str(attachment.get("description") or ""),
                    source_file=str(attachment.get("sourceFile") or attachment.get("source_file") or source_file),
                    status=explicit_status or artifact_status,
                    details={**artifact_details, **details},
                    filename=str(attachment.get("filename") or ""),
                    checksum=str(attachment.get("checksum") or ""),
                    timestamp=timestamp,
                )
            self._record_gdt_event(
                connection,
                event_type="result-imported",
                order_record_id=order_row["id"] if order_row else None,
                patient_context_id=patient_context_id,
                message_record_id=message_record_id,
                timestamp=timestamp,
                details={"messageType": GDT_RESULT_MESSAGE_TYPE, "matchStatus": match_status},
            )
            self._record_gdt_event(
                connection,
                event_type="result-matched" if order_row else "result-unmatched",
                order_record_id=order_row["id"] if order_row else None,
                patient_context_id=patient_context_id,
                message_record_id=message_record_id,
                timestamp=timestamp,
                details={"identifiers": order_identifiers},
            )
            if order_row:
                connection.execute(
                    """
                    UPDATE local_gdt_order_records
                    SET order_status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (GDT_ORDER_STATUS_RESULT_RECEIVED, timestamp, order_row["id"]),
                )
                self._record_gdt_event(
                    connection,
                    event_type="status-changed",
                    order_record_id=order_row["id"],
                    patient_context_id=patient_context_id,
                    message_record_id=message_record_id,
                    timestamp=timestamp,
                    details={"status": GDT_ORDER_STATUS_RESULT_RECEIVED},
                )
        return self._gdt_message_record_dict_by_id(message_record_id)

    # Compatibility-only OIE result seams.
    def list_oie_workbench(self) -> dict[str, Any]:
        return compose_oie_workbench(
            self.list_oie_local_adt_inventory(),
            self.list_oie_local_order_inventory(),
            self.oie_repository.list_oie_results(),
        )

    def record_oie_result(self, payload_hl7: str, parsed: dict[str, str]) -> dict[str, Any]:
        return self.oie_repository.record_oie_result(payload_hl7, parsed)

    def record_oie_result_error(
        self, payload_hl7: str, message_type: str, error_text: str
    ) -> dict[str, Any]:
        return self.oie_repository.record_oie_result_error(payload_hl7, message_type, error_text)

    def list_oie_results(self) -> list[dict[str, Any]]:
        return self.oie_repository.list_oie_results()



    @staticmethod
    def _dcm4chee_result_record_dict(row: sqlite3.Row) -> dict[str, Any]:
        return project_result_record(row)

    @staticmethod
    def _dcm4chee_mwl_attempt_dict(row: sqlite3.Row) -> dict[str, Any]:
        return project_mwl_attempt(row)

    @staticmethod
    def _dcm4chee_mwl_mapping_dict(row: sqlite3.Row) -> dict[str, Any]:
        return project_mwl_mapping(row)

    @staticmethod
    def _dcm4chee_mwl_status_view(attempt: dict[str, Any] | None, mapping: dict[str, Any] | None) -> dict[str, Any]:
        return dicom_domain.mwl_status_view(attempt, mapping)

    @staticmethod
    def _dcm4chee_mwl_retryable(status: str, error_type: str = "") -> bool:
        return dicom_domain.mwl_retryable(status, error_type)

    @staticmethod
    def _dcm4chee_mwl_display_status(status: str, retryable: bool) -> tuple[str, str]:
        return dicom_domain.mwl_display_status(status, retryable)

    @staticmethod
    def _json_value(value: str, fallback: Any) -> Any:
        try:
            return json.loads(value or "")
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _fhir_record_number(record_id: int) -> str:
        return f"FHIR-{record_id:06d}"

    @staticmethod
    def _fhir_clean_text(value: Any, field_name: str, required: bool = False) -> str:
        text = str(value or "").strip()
        if required and not text:
            raise SimulatorValidationError(f"FHIR {field_name} is required.")
        return text

    @staticmethod
    def _fhir_identifier_token(value: Any) -> str:
        text = str(value if value is not None else "").strip().lower()
        cleaned = []
        previous_dash = False
        for character in text:
            if character.isalnum():
                cleaned.append(character)
                previous_dash = False
            elif not previous_dash:
                cleaned.append("-")
                previous_dash = True
        return "".join(cleaned).strip("-") or "record"

    @classmethod
    def fhir_mapping_for_resource_type(cls, resource_type: str) -> dict[str, Any]:
        normalized = cls._fhir_clean_text(resource_type, "resourceType", required=True)
        if normalized not in FHIR_SUPPORTED_RESOURCE_TYPES:
            raise SimulatorValidationError(
                f"FHIR resourceType must be one of: {', '.join(FHIR_SUPPORTED_RESOURCE_TYPES)}."
            )
        mapping = FHIR_RESOURCE_MAPPINGS[normalized]
        return {
            "resourceType": normalized,
            "localSourceType": mapping["local_source_type"],
            "identifierSystem": FHIR_IDENTIFIER_SYSTEMS[normalized],
            "identifierPath": "identifier",
            "dependsOn": list(mapping["depends_on"]),
            "dependencyOrder": FHIR_RESOURCE_DEPENDENCY_ORDER[normalized],
        }

    @classmethod
    def list_fhir_resource_mappings(cls) -> list[dict[str, Any]]:
        return [
            cls.fhir_mapping_for_resource_type(resource_type)
            for resource_type in FHIR_SUPPORTED_RESOURCE_TYPES
        ]

    @classmethod
    def fhir_identifier_value(
        cls,
        resource_type: str,
        local_source_type: str,
        local_source_id: Any,
    ) -> str:
        mapping = cls.fhir_mapping_for_resource_type(resource_type)
        source_type = cls._fhir_identifier_token(local_source_type or mapping["localSourceType"])
        source_id = cls._fhir_identifier_token(local_source_id)
        return f"{source_type}-{source_id}"

    @classmethod
    def _fhir_resource_with_identifier(
        cls,
        resource: dict[str, Any],
        *,
        resource_type: str,
        identifier_system: str,
        identifier_value: str,
    ) -> dict[str, Any]:
        if not isinstance(resource, dict):
            raise SimulatorValidationError("FHIR resource must be a JSON object.")
        normalized = dict(resource)
        normalized["resourceType"] = resource_type
        identifiers = normalized.get("identifier")
        if not isinstance(identifiers, list):
            identifiers = []
        else:
            identifiers = [item for item in identifiers if isinstance(item, dict)]
        if not any(
            item.get("system") == identifier_system and item.get("value") == identifier_value
            for item in identifiers
        ):
            identifiers.insert(0, {"system": identifier_system, "value": identifier_value})
        normalized["identifier"] = identifiers
        return normalized

    def _validate_fhir_record_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SimulatorValidationError("FHIR workflow payload must be a JSON object.")
        raw_resource = payload.get("resource") or payload.get("resourceJson") or {}
        if isinstance(raw_resource, str):
            try:
                raw_resource = json.loads(raw_resource)
            except json.JSONDecodeError as exc:
                raise SimulatorValidationError("FHIR resource JSON is invalid.") from exc
        if not isinstance(raw_resource, dict):
            raise SimulatorValidationError("FHIR resource must be a JSON object.")
        resource_type = self._fhir_clean_text(
            payload.get("resourceType") or raw_resource.get("resourceType"),
            "resourceType",
            required=True,
        )
        mapping = self.fhir_mapping_for_resource_type(resource_type)
        local_source_type = self._fhir_clean_text(
            payload.get("localSourceType") or mapping["localSourceType"],
            "localSourceType",
            required=True,
        )
        local_source_id = self._fhir_clean_text(
            payload.get("localSourceId"),
            "localSourceId",
            required=True,
        )
        identifier_system = self._fhir_clean_text(
            payload.get("identifierSystem") or mapping["identifierSystem"],
            "identifierSystem",
            required=True,
        )
        identifier_value = self._fhir_clean_text(
            payload.get("identifierValue")
            or self.fhir_identifier_value(resource_type, local_source_type, local_source_id),
            "identifierValue",
            required=True,
        )
        dependencies = payload.get("dependencies", payload.get("dependsOn", mapping["dependsOn"]))
        if not isinstance(dependencies, list | tuple):
            raise SimulatorValidationError("FHIR dependencies must be a list.")
        resource = self._fhir_resource_with_identifier(
            raw_resource,
            resource_type=resource_type,
            identifier_system=identifier_system,
            identifier_value=identifier_value,
        )
        return {
            "local_source_type": local_source_type,
            "local_source_id": local_source_id,
            "resource_type": resource_type,
            "identifier_system": identifier_system,
            "identifier_value": identifier_value,
            "resource_json": json.dumps(resource, sort_keys=True),
            "dependency_json": json.dumps(list(dependencies)),
        }

    def create_fhir_workflow_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = self._validate_fhir_record_payload(payload)
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            existing = connection.execute(
                """
                SELECT * FROM local_fhir_workflow_records
                WHERE resource_type = ? AND identifier_system = ? AND identifier_value = ?
                """,
                (
                    values["resource_type"],
                    values["identifier_system"],
                    values["identifier_value"],
                ),
            ).fetchone()
            if existing:
                payload_changed = (
                    existing["resource_json"] != values["resource_json"]
                    or existing["dependency_json"] != values["dependency_json"]
                )
                next_status = (
                    FHIR_SYNC_STATUS_PENDING
                    if payload_changed
                    else existing["sync_status"]
                )
                connection.execute(
                    """
                    UPDATE local_fhir_workflow_records
                    SET local_source_type = ?, local_source_id = ?, resource_json = ?,
                        dependency_json = ?, sync_status = ?, updated_at = ?,
                        sync_error = CASE WHEN ? THEN '' ELSE sync_error END,
                        operation_outcome_json = CASE WHEN ? THEN '{}' ELSE operation_outcome_json END,
                        sync_started_at = CASE WHEN ? THEN '' ELSE sync_started_at END
                    WHERE id = ?
                    """,
                    (
                        values["local_source_type"],
                        values["local_source_id"],
                        values["resource_json"],
                        values["dependency_json"],
                        next_status,
                        timestamp,
                        int(payload_changed),
                        int(payload_changed),
                        int(payload_changed),
                        existing["id"],
                    ),
                )
                record_id = int(existing["id"])
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO local_fhir_workflow_records (
                        local_fhir_record_number, local_source_type, local_source_id,
                        resource_type, identifier_system, identifier_value, resource_json,
                        dependency_json, sync_status, created_at, updated_at
                    )
                    VALUES ('', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        values["local_source_type"],
                        values["local_source_id"],
                        values["resource_type"],
                        values["identifier_system"],
                        values["identifier_value"],
                        values["resource_json"],
                        values["dependency_json"],
                        FHIR_SYNC_STATUS_PENDING,
                        timestamp,
                        timestamp,
                    ),
                )
                record_id = int(cursor.lastrowid)
                connection.execute(
                    """
                    UPDATE local_fhir_workflow_records
                    SET local_fhir_record_number = ?
                    WHERE id = ?
                    """,
                    (self._fhir_record_number(record_id), record_id),
                )
        return self.get_fhir_workflow_record(record_id)

    def list_fhir_workflow_records(self, sync_status: str = "") -> list[dict[str, Any]]:
        with self.connect() as connection:
            if sync_status:
                rows = connection.execute(
                    """
                    SELECT * FROM local_fhir_workflow_records
                    WHERE sync_status = ?
                    ORDER BY id DESC
                    """,
                    (sync_status,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM local_fhir_workflow_records
                    ORDER BY id DESC
                    """
                ).fetchall()
        return [self._fhir_workflow_record_dict(row) for row in rows]

    def get_fhir_workflow_record(self, record_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_fhir_workflow_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
        return self._fhir_workflow_record_dict(row)

    def get_fhir_workflow_record_by_identifier(
        self,
        *,
        resource_type: str,
        identifier_system: str,
        identifier_value: str,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM local_fhir_workflow_records
                WHERE resource_type = ? AND identifier_system = ? AND identifier_value = ?
                """,
                (resource_type, identifier_system, identifier_value),
            ).fetchone()
            if not row:
                raise KeyError(identifier_value)
        return self._fhir_workflow_record_dict(row)

    def mark_fhir_syncing(self, record_id: int) -> dict[str, Any]:
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            row = connection.execute(
                "SELECT id FROM local_fhir_workflow_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
            connection.execute(
                """
                UPDATE local_fhir_workflow_records
                SET sync_status = ?, sync_started_at = ?, sync_error = '',
                    operation_outcome_json = '{}', updated_at = ?
                WHERE id = ?
                """,
                (FHIR_SYNC_STATUS_SYNCING, timestamp, timestamp, record_id),
            )
        return self.get_fhir_workflow_record(record_id)

    def mark_fhir_sync_success(
        self,
        record_id: int,
        *,
        medplum_resource_id: str,
        medplum_resource_reference: str = "",
    ) -> dict[str, Any]:
        timestamp = now_iso()
        resource_id = self._fhir_clean_text(medplum_resource_id, "medplumResourceId", required=True)
        with self.lock, self.connect() as connection:
            row = connection.execute(
                "SELECT resource_type FROM local_fhir_workflow_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
            reference = (
                medplum_resource_reference.strip()
                if medplum_resource_reference
                else f"{row['resource_type']}/{resource_id}"
            )
            connection.execute(
                """
                UPDATE local_fhir_workflow_records
                SET medplum_resource_id = ?, medplum_resource_reference = ?,
                    sync_status = ?, sync_error = '', operation_outcome_json = '{}',
                    last_sync_at = ?, sync_started_at = '', updated_at = ?
                WHERE id = ?
                """,
                (
                    resource_id,
                    reference,
                    FHIR_SYNC_STATUS_SYNCED,
                    timestamp,
                    timestamp,
                    record_id,
                ),
            )
        return self.get_fhir_workflow_record(record_id)

    def mark_fhir_sync_failure(
        self,
        record_id: int,
        *,
        error_text: str,
        operation_outcome: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            row = connection.execute(
                "SELECT id FROM local_fhir_workflow_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
            connection.execute(
                """
                UPDATE local_fhir_workflow_records
                SET sync_status = ?, sync_error = ?, operation_outcome_json = ?,
                    sync_started_at = '', updated_at = ?
                WHERE id = ?
                """,
                (
                    FHIR_SYNC_STATUS_FAILED,
                    str(error_text or "").strip(),
                    json.dumps(operation_outcome or {}, sort_keys=True),
                    timestamp,
                    record_id,
                ),
            )
        return self.get_fhir_workflow_record(record_id)

    def record_fhir_sync_attempt(
        self,
        record_id: int,
        *,
        method: str,
        request_url: str,
        request_payload: dict[str, Any] | None = None,
        http_status: int | None = None,
        response_payload: dict[str, Any] | None = None,
        operation_outcome: dict[str, Any] | None = None,
        error_text: str = "",
    ) -> dict[str, Any]:
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            row = connection.execute(
                "SELECT id FROM local_fhir_workflow_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
            cursor = connection.execute(
                """
                INSERT INTO local_fhir_sync_attempts (
                    fhir_record_id, method, request_url, request_payload_json,
                    http_status, response_payload_json, operation_outcome_json,
                    error_text, attempted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    method.strip().upper(),
                    request_url.strip(),
                    json.dumps(request_payload or {}, sort_keys=True),
                    http_status,
                    json.dumps(response_payload or {}, sort_keys=True),
                    json.dumps(operation_outcome or {}, sort_keys=True),
                    str(error_text or "").strip(),
                    timestamp,
                ),
            )
            attempt_id = int(cursor.lastrowid)
            attempt_row = connection.execute(
                "SELECT * FROM local_fhir_sync_attempts WHERE id = ?",
                (attempt_id,),
            ).fetchone()
        return self._fhir_sync_attempt_dict(attempt_row)

    def list_fhir_sync_attempts(self, record_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM local_fhir_sync_attempts
                WHERE fhir_record_id = ?
                ORDER BY id DESC
                """,
                (record_id,),
            ).fetchall()
        return [self._fhir_sync_attempt_dict(row) for row in rows]

    def ordered_fhir_workflow_records(self, record_ids: list[int]) -> list[dict[str, Any]]:
        records = [self.get_fhir_workflow_record(record_id) for record_id in record_ids]
        return sorted(
            records,
            key=lambda item: (
                FHIR_RESOURCE_DEPENDENCY_ORDER.get(item["resourceType"], 999),
                int(item["id"]),
            ),
        )

    def _fhir_workflow_record_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        resource = self._json_value(row["resource_json"], {})
        operation_outcome = self._json_value(row["operation_outcome_json"], {})
        mapping = (
            self.fhir_mapping_for_resource_type(row["resource_type"])
            if row["resource_type"] in FHIR_SUPPORTED_RESOURCE_TYPES
            else None
        )
        return {
            "id": row["id"],
            "localFhirRecordNumber": row["local_fhir_record_number"],
            "localSourceType": row["local_source_type"],
            "localSourceId": row["local_source_id"],
            "resourceType": row["resource_type"],
            "identifier": {
                "system": row["identifier_system"],
                "value": row["identifier_value"],
            },
            "resource": resource,
            "dependencies": self._json_value(row["dependency_json"], []),
            "mapping": mapping,
            "medplum": {
                "id": row["medplum_resource_id"],
                "reference": row["medplum_resource_reference"],
            },
            "sync": {
                "status": row["sync_status"],
                "error": row["sync_error"],
                "operationOutcome": operation_outcome,
                "lastSyncAt": row["last_sync_at"],
                "syncStartedAt": row["sync_started_at"],
            },
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "localOnly": row["sync_status"] != FHIR_SYNC_STATUS_SYNCED,
        }

    def _fhir_sync_attempt_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "fhirRecordId": row["fhir_record_id"],
            "method": row["method"],
            "requestUrl": row["request_url"],
            "requestPayload": self._json_value(row["request_payload_json"], {}),
            "httpStatus": row["http_status"],
            "responsePayload": self._json_value(row["response_payload_json"], {}),
            "operationOutcome": self._json_value(row["operation_outcome_json"], {}),
            "error": row["error_text"],
            "attemptedAt": row["attempted_at"],
        }

    def _gdt_order_record_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        summary_name = " ".join(
            part for part in (row["first_name"], row["middle_name"], row["last_name"]) if part
        )
        attachments = self.list_gdt_attachments(row["id"])
        messages = self.list_gdt_messages(row["id"])
        events = self.list_gdt_events(row["id"])
        primary_attachment_url = row["attachment_url"] or next(
            (item["url"] for item in attachments if item["url"]),
            "",
        )
        return {
            "id": row["id"],
            "localGdtOrderNumber": row["local_gdt_order_number"],
            "patientRecordId": row["patient_record_id"],
            "gdtPatientContextId": row["gdt_patient_context_id"],
            "protocolVersion": row["protocol_version"],
            "messageType": row["message_type"],
            "status": row["order_status"],
            "gdtTestField": GDT_ORDER_TEST_CODE_FIELD,
            "gdtTestCode": row["gdt_test_code"],
            "gdtTestLabel": row["gdt_test_label"],
            "gdtPatientNumber": row["gdt_patient_number"],
            "requestedAt": row["requested_at"],
            "orderingProvider": row["ordering_provider"],
            "clinicalIndication": row["clinical_indication"],
            "attachmentUrl": primary_attachment_url,
            "attachments": attachments,
            "payload": row["payload_gdt"],
            "rawGdtText": row["payload_gdt"],
            "patientSnapshot": self._json_value(row["patient_snapshot_json"], {}),
            "orderSnapshot": self._json_value(row["order_snapshot_json"], {}),
            "messages": messages,
            "events": events,
            "exportPath": row["export_path"],
            "error": row["error_text"],
            "summary": {
                "mrn": row["mrn"],
                "gdtPatientNumber": row["gdt_patient_number"],
                "name": summary_name,
                "dob": row["dob"],
                "sex": row["sex"],
                "visitNumber": row["visit_number"],
                "testCode": row["gdt_test_code"],
                "testLabel": row["gdt_test_label"],
            },
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "localOnly": True,
        }

    def _gdt_message_record_dict_by_id(self, record_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_gdt_message_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
        return self._gdt_message_record_dict(row)

    def _gdt_message_record_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "orderRecordId": row["order_record_id"],
            "patientContextId": row["patient_context_id"],
            "direction": row["direction"],
            "messageType": row["message_type"],
            "rawGdtText": row["raw_gdt_text"],
            "parsedFields": self._json_value(row["parsed_fields_json"], {}),
            "canonical": self._json_value(row["canonical_json"], {}),
            "parseStatus": row["parse_status"],
            "matchStatus": row["match_status"],
            "error": row["error_text"],
            "generatedAt": row["generated_at"],
            "receivedAt": row["received_at"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    def _gdt_attachment_record_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "orderRecordId": row["order_record_id"],
            "messageRecordId": row["message_record_id"],
            "role": row["role"],
            "url": row["url"],
            "path": row["path"],
            "reference": row["reference"],
            "contentType": row["content_type"],
            "description": row["description"],
            "sourceFile": row["source_file"],
            "status": row["status"],
            "details": self._json_value(row["details_json"], {}),
            "filename": row["filename"],
            "checksum": row["checksum"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    def _gdt_event_record_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "orderRecordId": row["order_record_id"],
            "patientContextId": row["patient_context_id"],
            "messageRecordId": row["message_record_id"],
            "attachmentRecordId": row["attachment_record_id"],
            "eventType": row["event_type"],
            "actor": row["actor"],
            "details": self._json_value(row["details_json"], {}),
            "createdAt": row["created_at"],
        }

    @staticmethod
    def _result_record_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "messageControlId": row["message_control_id"],
            "messageType": row["message_type"],
            "patientMrn": row["patient_mrn"],
            "placerOrderNumber": row["placer_order_number"],
            "fillerOrderNumber": row["filler_order_number"],
            "matchedPatientRecordId": row["matched_patient_record_id"],
            "matchedOrderRecordId": row["matched_order_record_id"],
            "matchStatus": row["match_status"],
            "duplicateOfId": row["duplicate_of_id"],
            "parseStatus": row["parse_status"],
            "error": row["error_text"],
            "payload": row["payload_hl7"],
            "receivedAt": row["received_at"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }



    @staticmethod
    def _dcm4chee_patient_sync_dict(row: sqlite3.Row) -> dict[str, Any]:
        return project_patient_sync_dict(row)

    @staticmethod
    def _dcm4chee_patient_sync_attempt_dict(row: sqlite3.Row) -> dict[str, Any]:
        return project_patient_sync_attempt_dict(row)


    # Compatibility-only lab seams. New composition uses ``lab_repository`` directly.
    def list_lab_servers(self) -> list[dict[str, Any]]:
        return self.lab_repository.list_servers()

    def get_lab_server(self, server_id: int) -> dict[str, Any]:
        return self.lab_repository.get_server(server_id)

    def create_lab_server(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.lab_repository.create_server(payload)

    def update_lab_server(self, server_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self.lab_repository.update_server(server_id, payload)

    def update_lab_server_health(self, server_id: int, **values: Any) -> dict[str, Any]:
        return self.lab_repository.update_health(server_id, **values)

    def record_lab_operation(self, server_id: int | None, **values: Any) -> dict[str, Any]:
        return self.lab_repository.record_operation(server_id, **values)

    def get_lab_operation(self, operation_id: int) -> dict[str, Any]:
        return self.lab_repository.get_operation(operation_id)

    def list_lab_operations(
        self, server_id: int | None = None, *, limit: int = 20
    ) -> list[dict[str, Any]]:
        return self.lab_repository.list_operations(server_id, limit=limit)

    def list_gdt_orders(self) -> list[dict[str, Any]]:
        return [
            {
                "id": item["id"],
                "orderNumber": item["localGdtOrderNumber"],
                "status": item["status"],
                "updatedAt": item["updatedAt"],
            }
            for item in self.list_gdt_order_records()
        ]
