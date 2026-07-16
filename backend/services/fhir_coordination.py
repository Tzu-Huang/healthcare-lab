"""Narrow local FHIR Patient and Order persistence coordination."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol

from backend.domain.errors import SimulatorValidationError
from backend.domain.fhir_order import storage_priority, validate_payload
from backend.domain.statuses import FHIR_SYNC_STATUS_SYNCED
from backend.templates.fhir import build_service_request

FHIR_PROTOCOL_VERSION = "FHIR R4"


class PatientLoader(Protocol):
    def get_patient_record(self, record_id: int) -> dict[str, Any]: ...


class FhirLedgerWriter(Protocol):
    def create_fhir_workflow_record(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class FhirOrderWriter(Protocol):
    def create_fhir_order_record(
        self, values: dict[str, Any], *, patient_reference: str,
        resource_builder: Callable[..., dict[str, Any]],
        priority_projector: Callable[[Any], str],
    ) -> dict[str, Any]: ...


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def create_patient_ledger_record(
    patient_record: dict[str, Any], ledger: FhirLedgerWriter,
) -> dict[str, Any]:
    """Create the paired Patient ledger row without transport or broad-store access."""
    if patient_record.get("protocolVersion") != FHIR_PROTOCOL_VERSION:
        raise SimulatorValidationError("Patient record is not FHIR mode.")
    return ledger.create_fhir_workflow_record({
        "localSourceType": "local_patient_records",
        "localSourceId": str(patient_record["id"]),
        "resourceType": "Patient",
        "resource": _json_object(patient_record.get("payload")),
    })


def create_order_ledger_record(
    order: dict[str, Any], ledger: FhirLedgerWriter,
) -> dict[str, Any]:
    """Create the paired ServiceRequest ledger row after its local order exists."""
    if order.get("protocolVersion") != FHIR_PROTOCOL_VERSION:
        raise SimulatorValidationError("Order record is not FHIR mode.")
    return ledger.create_fhir_workflow_record({
        "localSourceType": "local_order_records",
        "localSourceId": str(order["id"]),
        "resourceType": "ServiceRequest",
        "resource": _json_object(order.get("payload")),
    })


class PatientFhirCoordinator:
    def __init__(self, patient_repository: PatientLoader, ledger: FhirLedgerWriter) -> None:
        self._patients = patient_repository
        self._ledger = ledger

    def create_patient_fhir_workflow_record(
        self, patient_record: dict[str, Any],
    ) -> dict[str, Any]:
        return create_patient_ledger_record(patient_record, self._ledger)

    def create_patient_fhir_workflow_record_by_id(self, record_id: int) -> dict[str, Any]:
        return self.create_patient_fhir_workflow_record(
            self._patients.get_patient_record(record_id)
        )


class FhirOrderCoordinator:
    def __init__(
        self, patient_repository: PatientLoader, order_repository: FhirOrderWriter,
        ledger: FhirLedgerWriter, *, timestamp_factory: Callable[[], str],
        storage_timestamp_factory: Callable[[], str],
        validator: Callable[..., dict[str, Any]] = validate_payload,
        resource_builder: Callable[..., dict[str, Any]] = build_service_request,
        priority_projector: Callable[[Any], str] = storage_priority,
    ) -> None:
        self._patients = patient_repository
        self._orders = order_repository
        self._ledger = ledger
        self._timestamp = timestamp_factory
        self._storage_timestamp = storage_timestamp_factory
        self._validate = validator
        self._build_resource = resource_builder
        self._project_priority = priority_projector

    def synced_patient_reference(self, patient_record_id: int) -> str:
        patient = self._patients.get_patient_record(patient_record_id)
        fhir = patient.get("fhir") or {}
        sync_status = (fhir.get("sync") or {}).get("status")
        reference = str((fhir.get("medplum") or {}).get("reference") or "").strip()
        if (
            patient.get("protocolVersion") != FHIR_PROTOCOL_VERSION
            or sync_status != FHIR_SYNC_STATUS_SYNCED
            or not reference.startswith("Patient/")
        ):
            raise SimulatorValidationError(
                "FHIR Order requires a selected Patient with synced Medplum Patient/<id> reference."
            )
        return reference

    def create_fhir_order_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = self._validate(
            payload, timestamp_factory=self._timestamp,
            storage_timestamp_factory=self._storage_timestamp,
        )
        patient_reference = self.synced_patient_reference(values["patient_record_id"])
        return self._orders.create_fhir_order_record(
            values, patient_reference=patient_reference,
            resource_builder=self._build_resource,
            priority_projector=self._project_priority,
        )

    def create_order_service_request_fhir_workflow_record(
        self, order: dict[str, Any],
    ) -> dict[str, Any]:
        return create_order_ledger_record(order, self._ledger)

    def create_local_order_and_ledger(
        self, payload: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Preserve local-first semantics: ledger failure never removes the local order."""
        order = self.create_fhir_order_record(payload)
        return order, self.create_order_service_request_fhir_workflow_record(order)
