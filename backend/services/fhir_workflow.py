"""FHIR inventory, preview, and synchronization coordination."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from backend.domain.errors import SimulatorValidationError, UpstreamFhirError, ValidationError
from backend.domain.statuses import FHIR_SYNC_STATUS_SYNCED


class FhirRepositoryPort(Protocol):
    def list_fhir_resource_mappings(self) -> list[dict[str, Any]]: ...

    def list_fhir_workflow_records(self, sync_status: str = "") -> list[dict[str, Any]]: ...

    def create_fhir_workflow_record(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def get_fhir_workflow_record(self, record_id: int) -> dict[str, Any]: ...

    def list_fhir_sync_attempts(self, record_id: int) -> list[dict[str, Any]]: ...


class FhirWorkflowService:
    def __init__(
        self,
        repository: FhirRepositoryPort,
        *,
        inventory_types: tuple[str, ...],
        medplum_base_url: Callable[[], str],
        auth_manager: Callable[[], Any],
        inventory_mapper: Callable[[dict[str, Any]], dict[str, Any]],
        diagnostic_fetcher: Callable[..., dict[str, Any]],
        base_url_normalizer: Callable[[str], str],
        reference_url_builder: Callable[[str, str], str],
        json_request: Callable[..., tuple[int, dict[str, Any]]],
        operation_outcome: Callable[[dict[str, Any]], dict[str, Any]],
        upstream_status: Callable[[str], int | None],
        record_sync: Callable[..., dict[str, Any]],
    ) -> None:
        self._repository = repository
        self._inventory_types = inventory_types
        self._medplum_base_url = medplum_base_url
        self._auth_manager = auth_manager
        self._inventory_mapper = inventory_mapper
        self._diagnostic_fetcher = diagnostic_fetcher
        self._base_url_normalizer = base_url_normalizer
        self._reference_url_builder = reference_url_builder
        self._json_request = json_request
        self._operation_outcome = operation_outcome
        self._upstream_status = upstream_status
        self._record_sync = record_sync

    def operation_outcome(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._operation_outcome(payload)

    def mappings(self) -> list[dict[str, Any]]:
        return self._repository.list_fhir_resource_mappings()

    def records(self, sync_status: str = "") -> list[dict[str, Any]]:
        return [
            item
            for item in self._repository.list_fhir_workflow_records(sync_status)
            if item["resourceType"] != "Task"
        ]

    def inventory(self, sync_status: str = "", resource_type: str = "") -> dict[str, Any]:
        if resource_type and resource_type not in self._inventory_types:
            raise ValueError("FHIR resource type is not supported by Medplum inventory.")
        records = [
            item
            for item in self._repository.list_fhir_workflow_records(sync_status)
            if item["resourceType"] in self._inventory_types
            and (not resource_type or item["resourceType"] == resource_type)
        ]
        items = [self._inventory_mapper(item) for item in records]
        patients = [
            {
                "id": item["id"],
                "localFhirRecordNumber": item["localFhirRecordNumber"],
                "localSourceId": item["localSourceId"],
                "identifier": item["identifier"],
                "medplum": item["medplum"],
                "sync": item["sync"],
                "reference": item["medplum"].get("reference") or "",
            }
            for item in items
            if item["resourceType"] == "Patient"
        ]
        return {
            "items": items,
            "patients": patients,
            "resourceTypes": list(self._inventory_types),
        }

    def diagnostic_reports(
        self,
        *,
        patient_reference: str = "",
        service_request_reference: str = "",
        base_url: str = "",
    ) -> dict[str, Any]:
        resolved_base_url = str(base_url or self._medplum_base_url()).strip()
        if not resolved_base_url:
            raise ValueError("Medplum FHIR base URL is required.")
        return self._diagnostic_fetcher(
            resolved_base_url,
            "",
            patient_reference=patient_reference,
            service_request_reference=service_request_reference,
            auth_manager=self._auth_manager(),
        )

    def _fetch_live_reference(
        self, reference: str, base_url: str
    ) -> tuple[int, dict[str, Any]]:
        base = self._base_url_normalizer(base_url)
        return self._json_request(
            self._reference_url_builder(base, reference),
            "",
            auth_manager=self._auth_manager(),
            base_url=base,
        )

    def resource_preview(self, reference: str, base_url: str = "") -> dict[str, Any]:
        resolved_base_url = str(base_url or self._medplum_base_url()).strip()
        if not resolved_base_url:
            raise ValueError("Medplum FHIR base URL is required.")
        status_code, resource = self._fetch_live_reference(reference, resolved_base_url)
        return {
            "source": "medplum-live",
            "reference": reference,
            "statusCode": status_code,
            "resource": resource,
        }

    def create_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._repository.create_fhir_workflow_record(payload)

    def _raw_record(self, record_id: int) -> dict[str, Any]:
        return self._repository.get_fhir_workflow_record(record_id)

    def get_record(self, record_id: int) -> dict[str, Any]:
        item = self._raw_record(record_id)
        if item["resourceType"] == "Task":
            raise ValueError("FHIR Task workflow records are no longer supported.")
        return item

    def record_preview(self, record_id: int) -> dict[str, Any]:
        item = self._raw_record(record_id)
        if item["resourceType"] not in self._inventory_types:
            raise ValueError("FHIR resource type is not supported by Medplum inventory.")
        sync_status = (item.get("sync") or {}).get("status")
        reference = str((item.get("medplum") or {}).get("reference") or "").strip()
        fallback = item.get("resource") or {}
        if sync_status == FHIR_SYNC_STATUS_SYNCED and reference:
            try:
                status_code, resource = self._fetch_live_reference(
                    reference, self._medplum_base_url()
                )
                return {
                    "item": item,
                    "resource": resource,
                    "source": "medplum-live",
                    "live": {
                        "fetched": True,
                        "statusCode": status_code,
                        "reference": reference,
                        "error": "",
                    },
                }
            except (ValidationError, SimulatorValidationError, UpstreamFhirError) as exc:
                return {
                    "item": item,
                    "resource": fallback,
                    "source": "local-submitted-fallback",
                    "live": {
                        "fetched": False,
                        "statusCode": self._upstream_status(str(exc)),
                        "reference": reference,
                        "error": str(exc),
                    },
                }
        return {
            "item": item,
            "resource": fallback,
            "source": "local-submitted",
            "live": {
                "fetched": False,
                "statusCode": None,
                "reference": reference,
                "error": "",
            },
        }

    def attempts(self, record_id: int) -> list[dict[str, Any]]:
        self._raw_record(record_id)
        return self._repository.list_fhir_sync_attempts(record_id)

    def sync_record(
        self, record_id: int, base_url: str = ""
    ) -> tuple[bool, dict[str, Any]]:
        resolved_base_url = str(base_url or self._medplum_base_url()).strip()
        if not resolved_base_url:
            raise ValueError("Medplum FHIR base URL is required.")
        current = self._raw_record(record_id)
        if current["resourceType"] == "Task":
            raise ValueError("FHIR Task workflow records are no longer supported.")
        item = self._record_sync(
            self._repository,
            record_id,
            base_url=resolved_base_url,
            auth_manager=self._auth_manager(),
        )
        return item["sync"]["status"] == FHIR_SYNC_STATUS_SYNCED, item
