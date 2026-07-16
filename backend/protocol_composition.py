"""Composition helpers for the legacy protocol facade.

This module is an explicit composition layer: it may join concrete repositories,
workflow services, and templates while responsibility packages keep their declared
dependency direction.
"""

from __future__ import annotations

from collections.abc import Callable

from backend.domain.gdt_protocol import build_gdt_6302_request
from backend.repositories.fhir_ledger import FhirLedgerRepository
from backend.repositories.gdt_workflow import GdtWorkflowRepository
from backend.services.fhir_coordination import FhirOrderCoordinator, PatientFhirCoordinator
from backend.services.gdt_coordination import GdtWorkflowCoordinator
from backend.templates.fhir import build_service_request


def fhir_ledger(database, timestamp_factory: Callable[[], str]):
    return FhirLedgerRepository(
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
    repository = GdtWorkflowRepository(
        database.connect,
        database.lock,
        timestamp_factory=timestamp_factory,
        patient_loader=patient_repository.get_patient_record,
        patient_list_loader=patient_repository.list_patient_records,
        order_builder=build_gdt_6302_request,
    )
    return GdtWorkflowCoordinator(repository, requested_at_factory=requested_at_factory)


def build_service_request_resource(
    values, *, record_id, local_order_number, patient_reference,
):
    return build_service_request(
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
