"""Explicit construction of Healthcare Lab persistence and coordination owners."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from pathlib import Path

from backend.domain import dicom as dicom_domain
from backend.domain import order as order_domain
from backend.domain import patient as patient_domain
from backend.domain.dicom import DCM4CHEE_DEFAULT_UID_ROOT
from backend.config import (
    DEFAULT_LAB_OPERATION_METADATA,
    DEFAULT_LAB_SERVERS,
    OIE_MANAGEMENT_API_BASE_URL,
    OIE_MANAGEMENT_API_PASSWORD,
    OIE_MANAGEMENT_API_TIMEOUT_SECONDS,
    OIE_MANAGEMENT_API_USERNAME,
    OIE_MANAGED_CHANNEL_DEFAULTS,
    OIE_RESULT_LISTENER_HOST,
    OIE_RESULT_LISTENER_PORT,
    OIE_SETTINGS_PROFILE_NAME,
)
from backend.domain.gdt_protocol import render_gdt_message
from backend.domain.order import DEFAULT_TEXT as ORDER_DEFAULT_TEXT, ORDER_PROTOCOL_VERSION
from backend.domain.patient import PATIENT_MODES
from backend.domain.statuses import DCM4CHEE_MWL_OPERATION_CREATE
from backend.domain.timestamps import hl7_timestamp, now_iso
from backend.repositories.database import SQLiteDatabase
from backend.repositories.dcm4chee_mwl import Dcm4cheeMwlRepository, backfill_dcm4chee_mwl_mappings
from backend.repositories.dcm4chee_patient_sync import Dcm4cheePatientSyncRepository
from backend.repositories.dcm4chee_results import Dcm4cheeResultRepository
from backend.repositories.enrichment import OrderEnrichmentLoader, PatientEnrichmentLoader
from backend.repositories.fhir_ledger import FhirLedgerRepository
from backend.repositories.gdt_workflow import GdtWorkflowRepository
from backend.repositories.identifiers import PatientIdentifierRepository
from backend.repositories.integration_settings import IntegrationSettingsRepository
from backend.repositories.lab import LabRepository
from backend.repositories.maintenance import seed_lab_servers, seed_oie_settings_profile, seed_patient_mrn_sequence
from backend.repositories.oie import OieRepository
from backend.repositories.oie_settings import OieSettingsRepository, serialize_oie_settings_profile, validate_oie_settings_payload
from backend.repositories.orders import OrderRepository
from backend.repositories.patients import PatientRepository
from backend.repositories.schema import APPLICATION_MIGRATIONS, ensure_application_schema
from backend.services.dcm4chee_coordination import Dcm4cheeMwlAttemptCoordinator, Dcm4cheeWorkflowCoordinator
from backend.services.fhir_coordination import FhirOrderCoordinator, PatientFhirCoordinator
from backend.services.gdt_coordination import GdtWorkflowCoordinator, build_gdt_order_request
from backend.services.integration_settings import IntegrationSettingsService
from backend.services.protocol_compatibility import project_fhir_workflow_record
from backend.templates import dicom as dicom_templates
from backend.templates import order as order_templates
from backend.templates import patient as patient_templates
from backend.templates.fhir import build_service_request


@dataclass(frozen=True)
class ApplicationDependencies:
    """Declared construction results; never passed to workflow consumers."""

    database: SQLiteDatabase
    integration_settings_repository: IntegrationSettingsRepository
    integration_settings_service: IntegrationSettingsService
    oie_settings_repository: OieSettingsRepository
    lab_repository: LabRepository
    oie_repository: OieRepository
    patient_repository: PatientRepository
    order_repository: OrderRepository
    dcm4chee_patient_sync_repository: Dcm4cheePatientSyncRepository
    dcm4chee_mwl_repository: Dcm4cheeMwlRepository
    dcm4chee_result_repository: Dcm4cheeResultRepository
    dcm4chee_mwl_attempt_coordinator: Dcm4cheeMwlAttemptCoordinator
    dcm4chee_workflow_coordinator: Dcm4cheeWorkflowCoordinator
    fhir_ledger: FhirLedgerRepository
    patient_fhir: PatientFhirCoordinator
    order_fhir: FhirOrderCoordinator
    gdt_repository: GdtWorkflowRepository
    gdt_workflow: GdtWorkflowCoordinator


def assemble_application_dependencies(
    path: str | Path,
    *,
    configuration: dict[str, object] | None = None,
) -> ApplicationDependencies:
    database = SQLiteDatabase(
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
                managed_channel_defaults=OIE_MANAGED_CHANNEL_DEFAULTS,
                timestamp_factory=now_iso,
            ),
        ),
    )
    database.initialize()

    oie_settings_repository = OieSettingsRepository(
        database.connect,
        database.lock,
        profile_name=OIE_SETTINGS_PROFILE_NAME,
        validator=validate_oie_settings_payload,
        serializer=serialize_oie_settings_profile,
        timestamp_factory=now_iso,
    )
    lab_repository = LabRepository(database.connect, database.lock, timestamp_factory=now_iso)
    integration_settings_repository = IntegrationSettingsRepository(
        database.connect,
        database.lock,
        timestamp_factory=now_iso,
    )
    integration_settings_service = IntegrationSettingsService(
        integration_settings_repository
    )
    bootstrap_configuration = dict(configuration or {})
    if "MEDPLUM_FHIR_BASE_URL" not in bootstrap_configuration:
        medplum = next(
            (
                item
                for item in lab_repository.list_servers()
                if item["name"] == "Medplum"
            ),
            None,
        )
        bootstrap_configuration["MEDPLUM_FHIR_BASE_URL"] = str(
            (medplum or {}).get("baseUrl") or "http://medplum:8103/fhir/R4"
        )
    integration_settings_service.bootstrap_medplum(bootstrap_configuration)
    oie_repository = OieRepository(
        database.connect,
        database.lock,
        timestamp_factory=now_iso,
        patient_protocol=PATIENT_MODES["hl7-v2"]["protocol"],
        order_protocol=ORDER_PROTOCOL_VERSION,
    )

    patient_repository: PatientRepository
    order_repository: OrderRepository
    dcm4chee_patient_sync_repository = Dcm4cheePatientSyncRepository(
        database.connect,
        database.lock,
        patient_loader=lambda record_id: patient_repository.get_patient_record(record_id),
        identifiers=dicom_domain.patient_identifiers,
        timestamp_factory=now_iso,
    )
    dcm4chee_mwl_repository = Dcm4cheeMwlRepository(
        database.connect,
        database.lock,
        order_loader=lambda record_id: order_repository.get_order_record(record_id),
        identifiers_from_payload=lambda order, profile, **kwargs: dicom_templates.identifiers_from_payload(
            order,
            profile,
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
    dcm4chee_result_repository = Dcm4cheeResultRepository(
        database.connect,
        database.lock,
        mwl_mapping_loader=dcm4chee_mwl_repository.list_dcm4chee_mwl_mappings_for_patient,
        profile_identity=dicom_domain.profile_identity,
        link_builder=dicom_domain.result_links,
        result_key_builder=dicom_domain.result_key,
        timestamp_factory=now_iso,
    )
    patient_enrichment_loader = PatientEnrichmentLoader(
        database.connect,
        fhir_projector=project_fhir_workflow_record,
        patient_sync_loader=dcm4chee_patient_sync_repository.load_latest_for_patients,
        result_loader=dcm4chee_result_repository.load_for_patients,
    )
    order_enrichment_loader = OrderEnrichmentLoader(
        database.connect,
        fhir_projector=project_fhir_workflow_record,
        mwl_loader=dcm4chee_mwl_repository.load_for_orders,
    )
    patient_repository = PatientRepository(
        database.connect,
        database.lock,
        identifier_repository=PatientIdentifierRepository(),
        validator=patient_domain.validate_payload,
        payload_builder=partial(patient_templates.build, gdt_renderer=render_gdt_message),
        timestamp_factory=now_iso,
        hl7_timestamp_factory=hl7_timestamp,
        enrichment_loader=patient_enrichment_loader,
    )
    order_repository = OrderRepository(
        database.connect,
        database.lock,
        validator=order_domain.validate_payload,
        payload_builder=order_templates.build_orm,
        timestamp_factory=now_iso,
        hl7_timestamp_factory=hl7_timestamp,
        enrichment_loader=order_enrichment_loader,
        dcm4chee_status_view=dicom_domain.mwl_status_view,
    )
    mwl_attempt_coordinator = Dcm4cheeMwlAttemptCoordinator(
        order_loader=order_repository.get_order_record,
        payload_builder=lambda order, profile, **kwargs: dicom_templates.build_mwl_payload(
            order,
            profile,
            uid_root=kwargs.get("uid_root", DCM4CHEE_DEFAULT_UID_ROOT),
            timestamp_factory=hl7_timestamp,
        ),
        attempt_creator=dcm4chee_mwl_repository.create_dcm4chee_mwl_attempt,
    )
    workflow_coordinator = Dcm4cheeWorkflowCoordinator(
        patient_create=patient_repository.create_patient_record,
        patient_get=patient_repository.get_patient_record,
        order_create=order_repository.create_dcm4chee_order_record,
        order_get=order_repository.get_order_record,
        patient_sync_get=dcm4chee_patient_sync_repository.get_dcm4chee_patient_sync_for_patient,
        mwl_get=dcm4chee_mwl_repository.get_dcm4chee_mwl_mapping_for_order,
        mwl_upsert=dcm4chee_mwl_repository.upsert_dcm4chee_mwl_mapping,
        result_list=dcm4chee_result_repository.list_dcm4chee_results_for_patient,
        result_begin=dcm4chee_result_repository.begin_dcm4chee_result_refresh,
        result_upsert=dcm4chee_result_repository.upsert_dcm4chee_result_record,
        result_complete=dcm4chee_result_repository.complete_dcm4chee_result_refresh,
        latest_simulated_generation=dcm4chee_result_repository.latest_simulated_dcm4chee_ap_return_generation,
        mwl_payload_builder=lambda order, profile, **kwargs: dicom_templates.build_mwl_payload(
            order,
            profile,
            uid_root=kwargs.get("uid_root", DCM4CHEE_DEFAULT_UID_ROOT),
            timestamp_factory=hl7_timestamp,
        ),
        timestamp_factory=now_iso,
    )
    fhir_ledger = FhirLedgerRepository(database.connect, database.lock, timestamp_factory=now_iso)
    patient_fhir = PatientFhirCoordinator(patient_repository, fhir_ledger)
    order_fhir = FhirOrderCoordinator(
        patient_repository,
        order_repository,
        fhir_ledger,
        timestamp_factory=now_iso,
        storage_timestamp_factory=hl7_timestamp,
        resource_builder=build_service_request,
    )
    gdt_repository = GdtWorkflowRepository(
        database.connect,
        database.lock,
        timestamp_factory=now_iso,
        patient_loader=patient_repository.get_patient_record,
        patient_list_loader=patient_repository.list_patient_records,
        order_builder=build_gdt_order_request,
    )
    return ApplicationDependencies(
        database=database,
        integration_settings_repository=integration_settings_repository,
        integration_settings_service=integration_settings_service,
        oie_settings_repository=oie_settings_repository,
        lab_repository=lab_repository,
        oie_repository=oie_repository,
        patient_repository=patient_repository,
        order_repository=order_repository,
        dcm4chee_patient_sync_repository=dcm4chee_patient_sync_repository,
        dcm4chee_mwl_repository=dcm4chee_mwl_repository,
        dcm4chee_result_repository=dcm4chee_result_repository,
        dcm4chee_mwl_attempt_coordinator=mwl_attempt_coordinator,
        dcm4chee_workflow_coordinator=workflow_coordinator,
        fhir_ledger=fhir_ledger,
        patient_fhir=patient_fhir,
        order_fhir=order_fhir,
        gdt_repository=gdt_repository,
        gdt_workflow=GdtWorkflowCoordinator(gdt_repository),
    )
