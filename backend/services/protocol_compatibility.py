"""Stateless construction and pure compatibility helpers for legacy facades."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import Any

from backend.domain import fhir_ledger as fhir_domain
from backend.domain import fhir_order
from backend.domain.gdt_protocol import (
    attachment_payloads_from_result_fields,
    build_gdt_6302_request,
    first_gdt_field,
)
from backend.services.fhir_coordination import FhirOrderCoordinator, PatientFhirCoordinator
from backend.services.gdt_coordination import (
    GdtWorkflowCoordinator,
    artifact_status,
    normalize_gdt_order_payload,
    validate_gdt_patient_number,
    validate_gdt_test_code,
)

FHIR_RESOURCE_DEPENDENCY_ORDER = fhir_domain.FHIR_RESOURCE_DEPENDENCY_ORDER
FHIR_IDENTIFIER_SYSTEMS = fhir_domain.FHIR_IDENTIFIER_SYSTEMS
FHIR_RESOURCE_MAPPINGS = fhir_domain.FHIR_RESOURCE_MAPPINGS


def fhir_ledger(database, timestamp_factory: Callable[[], str]):
    repository_type = import_module("backend.repositories.fhir_ledger").FhirLedgerRepository
    return repository_type(
        database.connect, database.lock, timestamp_factory=timestamp_factory
    )


def patient_fhir_coordinator(database, patient_repository, timestamp_factory):
    return PatientFhirCoordinator(
        patient_repository, fhir_ledger(database, timestamp_factory)
    )


def fhir_order_coordinator(
    database, patient_repository, order_repository, *, timestamp_factory,
    storage_timestamp_factory,
) -> FhirOrderCoordinator:
    return FhirOrderCoordinator(
        patient_repository,
        order_repository,
        fhir_ledger(database, timestamp_factory),
        timestamp_factory=timestamp_factory,
        storage_timestamp_factory=storage_timestamp_factory,
        resource_builder=build_service_request_resource,
    )


def gdt_coordinator(
    database, patient_repository, *, timestamp_factory, requested_at_factory,
) -> GdtWorkflowCoordinator:
    repository_type = import_module("backend.repositories.gdt_workflow").GdtWorkflowRepository
    repository = repository_type(
        database.connect,
        database.lock,
        timestamp_factory=timestamp_factory,
        patient_loader=patient_repository.get_patient_record,
        patient_list_loader=patient_repository.list_patient_records,
        order_builder=build_gdt_6302_request,
    )
    return GdtWorkflowCoordinator(repository, requested_at_factory=requested_at_factory)


def fhir_order_values(payload: dict[str, Any]) -> dict[str, Any]:
    fhir = payload.get("fhir") if isinstance(payload.get("fhir"), dict) else payload
    return fhir if isinstance(fhir, dict) else {}


def validate_fhir_order_payload(payload, *, timestamp_factory, storage_timestamp_factory):
    return fhir_order.validate_payload(
        payload,
        timestamp_factory=timestamp_factory,
        storage_timestamp_factory=storage_timestamp_factory,
    )


def build_service_request_resource(values, *, record_id, local_order_number, patient_reference):
    return import_module("backend.templates.fhir").build_service_request(
        values,
        record_id=record_id,
        local_order_number=local_order_number,
        patient_reference=patient_reference,
    )


def create_patient_fhir_record(database, patient_repository, timestamp_factory, patient_record):
    return patient_fhir_coordinator(database, patient_repository, timestamp_factory).create_patient_fhir_workflow_record(patient_record)


def synced_fhir_patient_reference(database, patient_repository, order_repository, timestamp_factory, storage_timestamp_factory, patient_record_id):
    return fhir_order_coordinator(database, patient_repository, order_repository, timestamp_factory=timestamp_factory, storage_timestamp_factory=storage_timestamp_factory).synced_patient_reference(patient_record_id)


def create_fhir_order(database, patient_repository, order_repository, timestamp_factory, storage_timestamp_factory, payload):
    return fhir_order_coordinator(database, patient_repository, order_repository, timestamp_factory=timestamp_factory, storage_timestamp_factory=storage_timestamp_factory).create_fhir_order_record(payload)


def create_order_fhir_record(database, patient_repository, order_repository, timestamp_factory, storage_timestamp_factory, order):
    return fhir_order_coordinator(database, patient_repository, order_repository, timestamp_factory=timestamp_factory, storage_timestamp_factory=storage_timestamp_factory).create_order_service_request_fhir_workflow_record(order)


def create_fhir_record(database, timestamp_factory, payload):
    return fhir_ledger(database, timestamp_factory).create_fhir_workflow_record(payload)


def list_fhir_records(database, timestamp_factory, sync_status=""):
    return fhir_ledger(database, timestamp_factory).list_fhir_workflow_records(sync_status)


def get_fhir_record(database, timestamp_factory, record_id):
    return fhir_ledger(database, timestamp_factory).get_fhir_workflow_record(record_id)


def get_fhir_record_by_identifier(database, timestamp_factory, **identifier):
    return fhir_ledger(database, timestamp_factory).get_fhir_workflow_record_by_identifier(**identifier)


def mark_fhir_record_syncing(database, timestamp_factory, record_id):
    return fhir_ledger(database, timestamp_factory).mark_fhir_syncing(record_id)


def mark_fhir_record_success(database, timestamp_factory, record_id, **values):
    return fhir_ledger(database, timestamp_factory).mark_fhir_sync_success(record_id, **values)


def mark_fhir_record_failure(database, timestamp_factory, record_id, **values):
    return fhir_ledger(database, timestamp_factory).mark_fhir_sync_failure(record_id, **values)


def create_fhir_sync_attempt(database, timestamp_factory, record_id, **values):
    return fhir_ledger(database, timestamp_factory).record_fhir_sync_attempt(record_id, **values)


def list_fhir_record_attempts(database, timestamp_factory, record_id):
    return fhir_ledger(database, timestamp_factory).list_fhir_sync_attempts(record_id)


def order_fhir_records(database, timestamp_factory, record_ids):
    return fhir_ledger(database, timestamp_factory).ordered_fhir_workflow_records(record_ids)


def create_gdt_order(database, patient_repository, timestamp_factory, requested_at_factory, payload):
    return gdt_coordinator(database, patient_repository, timestamp_factory=timestamp_factory, requested_at_factory=requested_at_factory).create_gdt_order_record(payload)


def list_gdt_order_records(database, patient_repository, timestamp_factory, requested_at_factory):
    return gdt_coordinator(database, patient_repository, timestamp_factory=timestamp_factory, requested_at_factory=requested_at_factory).list_gdt_order_records()


def get_gdt_order(database, patient_repository, timestamp_factory, requested_at_factory, record_id):
    return gdt_coordinator(database, patient_repository, timestamp_factory=timestamp_factory, requested_at_factory=requested_at_factory).get_gdt_order_record(record_id)


def list_gdt_messages(database, patient_repository, timestamp_factory, requested_at_factory, order_record_id=None):
    return gdt_coordinator(database, patient_repository, timestamp_factory=timestamp_factory, requested_at_factory=requested_at_factory).list_gdt_messages(order_record_id)


def list_gdt_events(database, patient_repository, timestamp_factory, requested_at_factory, order_record_id=None):
    return gdt_coordinator(database, patient_repository, timestamp_factory=timestamp_factory, requested_at_factory=requested_at_factory).list_gdt_events(order_record_id)


def list_gdt_attachments(database, patient_repository, timestamp_factory, requested_at_factory, order_record_id=None):
    return gdt_coordinator(database, patient_repository, timestamp_factory=timestamp_factory, requested_at_factory=requested_at_factory).list_gdt_attachments(order_record_id)


def record_gdt_export(database, patient_repository, timestamp_factory, requested_at_factory, order_record_id, **values):
    return gdt_coordinator(database, patient_repository, timestamp_factory=timestamp_factory, requested_at_factory=requested_at_factory).record_gdt_order_export(order_record_id, **values)


def create_gdt_demo(database, patient_repository, timestamp_factory, requested_at_factory, order_record_id):
    return gdt_coordinator(database, patient_repository, timestamp_factory=timestamp_factory, requested_at_factory=requested_at_factory).create_gdt_demo_result(order_record_id)


def build_gdt_workbench(database, patient_repository, timestamp_factory, requested_at_factory, bridge_inbox=None):
    return gdt_coordinator(database, patient_repository, timestamp_factory=timestamp_factory, requested_at_factory=requested_at_factory).list_gdt_workbench(bridge_inbox=bridge_inbox)


def persist_gdt_result(database, patient_repository, timestamp_factory, requested_at_factory, payload):
    return gdt_coordinator(database, patient_repository, timestamp_factory=timestamp_factory, requested_at_factory=requested_at_factory).record_gdt_result(payload)


def list_gdt_inventory(database, patient_repository, timestamp_factory, requested_at_factory):
    return gdt_coordinator(database, patient_repository, timestamp_factory=timestamp_factory, requested_at_factory=requested_at_factory).list_gdt_orders()


def gdt_order_number(record_id: int) -> str:
    return f"GDT-ORD-{record_id:06d}"


def gdt_patient_number(patient_record_id: int) -> str:
    return f"GDT-PAT-{patient_record_id:06d}"


def gdt_birth_date(dob: str) -> str:
    return f"{dob[6:]}{dob[4:6]}{dob[:4]}"


def gdt_attachment_filename(url: str, path: str = "") -> str:
    source = path or url
    return source.rstrip("/").replace("\\", "/").split("/")[-1] if source else ""


def gdt_result_measurements(fields: dict[str, list[str]]) -> dict[str, str]:
    return {
        label: first_gdt_field(fields, code)
        for label, code in (("HR", "8401"), ("PR", "8402"), ("QRS", "8403"),
                            ("QT", "8404"), ("QTC", "8405"))
        if first_gdt_field(fields, code)
    }


json_value = fhir_domain.json_value
fhir_record_number = fhir_domain.record_number
fhir_clean_text = fhir_domain.clean_text
fhir_identifier_token = fhir_domain.identifier_token
fhir_mapping_for_resource_type = fhir_domain.mapping_for_resource_type
list_fhir_resource_mappings = fhir_domain.list_resource_mappings
fhir_identifier_value = fhir_domain.identifier_value
fhir_resource_with_identifier = fhir_domain.resource_with_identifier
normalize_fhir_record_payload = fhir_domain.normalize_record_payload
project_fhir_workflow_record = fhir_domain.project_workflow_record
project_fhir_sync_attempt = fhir_domain.project_sync_attempt
fhir_order_clean_text = fhir_order.clean_text
fhir_order_list = fhir_order.list_values
fhir_reference_item = fhir_order.reference_item
fhir_reference_list = fhir_order.reference_list
fhir_codeable_concept = fhir_order.codeable_concept
fhir_order_datetime = fhir_order.normalize_datetime
fhir_order_storage_timestamp = fhir_order.storage_timestamp
fhir_order_storage_priority = fhir_order.storage_priority
gdt_artifact_status = artifact_status
gdt_attachment_payloads = attachment_payloads_from_result_fields
normalize_gdt_payload = normalize_gdt_order_payload
validate_gdt_override = validate_gdt_patient_number
validate_gdt_code = validate_gdt_test_code


def is_url_reference(value: str) -> bool:
    return str(value or "").lower().startswith(("http://", "https://"))
