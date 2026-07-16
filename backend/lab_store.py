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
from backend.mappers.dicom import project_patient_sync, project_patient_sync_attempt
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
        return protocol_composition.create_patient_fhir_record(self.database, self.patient_repository, now_iso, patient_record)

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
        return protocol_compat.fhir_order_values(payload)

    @staticmethod
    def _clean_fhir_order_text(value: Any) -> str:
        return protocol_compat.fhir_order_clean_text(value)

    @staticmethod
    def _fhir_order_list(value: Any) -> list[str]:
        return protocol_compat.fhir_order_list(value)

    @staticmethod
    def _fhir_reference_item(value: str, field_name: str) -> dict[str, str]:
        return protocol_compat.fhir_reference_item(value, field_name)

    @classmethod
    def _fhir_reference_list(cls, value: Any, field_name: str) -> list[dict[str, str]]:
        return protocol_compat.fhir_reference_list(value, field_name)

    @classmethod
    def _fhir_codeable_concept(cls, *, text: Any = "", code: Any = "", system: Any = "", display: Any = "") -> dict[str, Any]:
        return protocol_compat.fhir_codeable_concept(text=text, code=code, system=system, display=display)

    @staticmethod
    def _fhir_order_datetime(value: Any, fallback: str = "") -> str:
        return protocol_compat.fhir_order_datetime(value, fallback)

    @staticmethod
    def _fhir_order_storage_timestamp(value: Any) -> str:
        return protocol_compat.fhir_order_storage_timestamp(value, hl7_timestamp)

    @staticmethod
    def _fhir_order_storage_priority(value: Any) -> str:
        return protocol_compat.fhir_order_storage_priority(value)

    @classmethod
    def _validate_fhir_order_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        return protocol_compat.validate_fhir_order_payload(payload, timestamp_factory=now_iso, storage_timestamp_factory=hl7_timestamp)


    @classmethod
    def _build_service_request_resource(cls, values: dict[str, Any], *, record_id: int, local_order_number: str, patient_reference: str) -> dict[str, Any]:
        return protocol_composition.build_service_request_resource(values, record_id=record_id, local_order_number=local_order_number, patient_reference=patient_reference)

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
        return protocol_composition.synced_fhir_patient_reference(self.database, self.patient_repository, self.order_repository, now_iso, hl7_timestamp, patient_record_id)

    def create_fhir_order_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        return protocol_composition.create_fhir_order(self.database, self.patient_repository, self.order_repository, now_iso, hl7_timestamp, payload)

    def create_order_service_request_fhir_workflow_record(self, order: dict[str, Any]) -> dict[str, Any]:
        return protocol_composition.create_order_fhir_record(self.database, self.patient_repository, self.order_repository, now_iso, hl7_timestamp, order)

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
        return protocol_compat.gdt_order_number(record_id)

    @staticmethod
    def _gdt_patient_context_number(patient_record_id: int) -> str:
        return protocol_compat.gdt_patient_number(patient_record_id)

    @staticmethod
    def _validate_gdt_patient_number(value: Any, field_name: str = "gdtPatientNumber") -> str:
        return protocol_compat.validate_gdt_override(value, field_name)


    @staticmethod
    def _gdt_attachment_filename(url: str, path: str = "") -> str:
        return protocol_compat.gdt_attachment_filename(url, path)

    @staticmethod
    def _is_url_reference(value: str) -> bool:
        return protocol_compat.is_url_reference(value)

    @staticmethod
    def _gdt_artifact_status(reference: str, bridge_root: str = "") -> tuple[str, dict[str, Any]]:
        return protocol_compat.gdt_artifact_status(reference, bridge_root)





    @staticmethod
    def _validate_gdt_8402_code(value: Any) -> str:
        return protocol_compat.validate_gdt_code(value)

    def _validate_gdt_order_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return protocol_compat.normalize_gdt_payload(payload, requested_at_factory=hl7_timestamp)

    @staticmethod
    def _gdt_birth_date(dob: str) -> str:
        return protocol_compat.gdt_birth_date(dob)


    def create_gdt_order_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        return protocol_composition.create_gdt_order(self.database, self.patient_repository, now_iso, hl7_timestamp, payload)

    def list_gdt_order_records(self) -> list[dict[str, Any]]:
        return protocol_composition.list_gdt_order_records(self.database, self.patient_repository, now_iso, hl7_timestamp)

    def get_gdt_order_record(self, record_id: int) -> dict[str, Any]:
        return protocol_composition.get_gdt_order(self.database, self.patient_repository, now_iso, hl7_timestamp, record_id)

    def list_gdt_messages(self, order_record_id: int | None = None) -> list[dict[str, Any]]:
        return protocol_composition.list_gdt_messages(self.database, self.patient_repository, now_iso, hl7_timestamp, order_record_id)

    def list_gdt_events(self, order_record_id: int | None = None) -> list[dict[str, Any]]:
        return protocol_composition.list_gdt_events(self.database, self.patient_repository, now_iso, hl7_timestamp, order_record_id)

    def list_gdt_attachments(self, order_record_id: int | None = None) -> list[dict[str, Any]]:
        return protocol_composition.list_gdt_attachments(self.database, self.patient_repository, now_iso, hl7_timestamp, order_record_id)

    def record_gdt_order_export(self, order_record_id: int, *, export_path: str, status: str, error_text: str = "") -> dict[str, Any]:
        return protocol_composition.record_gdt_export(self.database, self.patient_repository, now_iso, hl7_timestamp, order_record_id, export_path=export_path, status=status, error_text=error_text)

    def create_gdt_demo_result(self, order_record_id: int) -> dict[str, Any]:
        return protocol_composition.create_gdt_demo(self.database, self.patient_repository, now_iso, hl7_timestamp, order_record_id)

    def list_gdt_workbench(self, *, bridge_inbox: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return protocol_composition.build_gdt_workbench(self.database, self.patient_repository, now_iso, hl7_timestamp, bridge_inbox)

    @staticmethod
    def _attachment_payloads_from_result_fields(fields: dict[str, list[str]]) -> list[dict[str, str]]:
        return protocol_compat.gdt_attachment_payloads(fields)

    @staticmethod
    def _gdt_result_measurements(fields: dict[str, list[str]]) -> dict[str, str]:
        return protocol_compat.gdt_result_measurements(fields)

    def record_gdt_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        return protocol_composition.persist_gdt_result(self.database, self.patient_repository, now_iso, hl7_timestamp, payload)

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
        return protocol_compat.json_value(value, fallback)

    @staticmethod
    def _fhir_record_number(record_id: int) -> str:
        return protocol_compat.fhir_record_number(record_id)

    @staticmethod
    def _fhir_clean_text(value: Any, field_name: str, required: bool = False) -> str:
        return protocol_compat.fhir_clean_text(value, field_name, required)

    @staticmethod
    def _fhir_identifier_token(value: Any) -> str:
        return protocol_compat.fhir_identifier_token(value)

    @classmethod
    def fhir_mapping_for_resource_type(cls, resource_type: str) -> dict[str, Any]:
        return protocol_compat.fhir_mapping_for_resource_type(resource_type)

    @classmethod
    def list_fhir_resource_mappings(cls) -> list[dict[str, Any]]:
        return protocol_compat.list_fhir_resource_mappings()

    @classmethod
    def fhir_identifier_value(cls, resource_type: str, local_source_type: str, local_source_id: Any) -> str:
        return protocol_compat.fhir_identifier_value(resource_type, local_source_type, local_source_id)

    @classmethod
    def _fhir_resource_with_identifier(cls, resource: dict[str, Any], *, resource_type: str, identifier_system: str, identifier_value: str) -> dict[str, Any]:
        return protocol_compat.fhir_resource_with_identifier(resource, resource_type=resource_type, identifier_system=identifier_system, identifier_value=identifier_value)

    def _validate_fhir_record_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return protocol_compat.normalize_fhir_record_payload(payload)

    def create_fhir_workflow_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        return protocol_composition.create_fhir_record(self.database, now_iso, payload)

    def list_fhir_workflow_records(self, sync_status: str = "") -> list[dict[str, Any]]:
        return protocol_composition.list_fhir_records(self.database, now_iso, sync_status)

    def get_fhir_workflow_record(self, record_id: int) -> dict[str, Any]:
        return protocol_composition.get_fhir_record(self.database, now_iso, record_id)

    def get_fhir_workflow_record_by_identifier(self, *, resource_type: str, identifier_system: str, identifier_value: str) -> dict[str, Any]:
        return protocol_composition.get_fhir_record_by_identifier(self.database, now_iso, resource_type=resource_type, identifier_system=identifier_system, identifier_value=identifier_value)

    def mark_fhir_syncing(self, record_id: int) -> dict[str, Any]:
        return protocol_composition.mark_fhir_record_syncing(self.database, now_iso, record_id)

    def mark_fhir_sync_success(self, record_id: int, *, medplum_resource_id: str, medplum_resource_reference: str = "") -> dict[str, Any]:
        return protocol_composition.mark_fhir_record_success(self.database, now_iso, record_id, medplum_resource_id=medplum_resource_id, medplum_resource_reference=medplum_resource_reference)

    def mark_fhir_sync_failure(self, record_id: int, *, error_text: str, operation_outcome: dict[str, Any] | None = None) -> dict[str, Any]:
        return protocol_composition.mark_fhir_record_failure(self.database, now_iso, record_id, error_text=error_text, operation_outcome=operation_outcome)

    def record_fhir_sync_attempt(self, record_id: int, *, method: str, request_url: str, request_payload: dict[str, Any] | None = None, http_status: int | None = None, response_payload: dict[str, Any] | None = None, operation_outcome: dict[str, Any] | None = None, error_text: str = "") -> dict[str, Any]:
        return protocol_composition.create_fhir_sync_attempt(self.database, now_iso, record_id, method=method, request_url=request_url, request_payload=request_payload, http_status=http_status, response_payload=response_payload, operation_outcome=operation_outcome, error_text=error_text)

    def list_fhir_sync_attempts(self, record_id: int) -> list[dict[str, Any]]:
        return protocol_composition.list_fhir_record_attempts(self.database, now_iso, record_id)

    def ordered_fhir_workflow_records(self, record_ids: list[int]) -> list[dict[str, Any]]:
        return protocol_composition.order_fhir_records(self.database, now_iso, record_ids)

    def _fhir_workflow_record_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return protocol_compat.project_fhir_workflow_record(row)

    def _fhir_sync_attempt_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return protocol_compat.project_fhir_sync_attempt(row)






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
        return project_patient_sync(row)

    @staticmethod
    def _dcm4chee_patient_sync_attempt_dict(row: sqlite3.Row) -> dict[str, Any]:
        return project_patient_sync_attempt(row)


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
        return protocol_composition.list_gdt_inventory(self.database, self.patient_repository, now_iso, hl7_timestamp)
