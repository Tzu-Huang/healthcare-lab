"""Patient workflow coordination independent of Flask request state."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol

from backend.domain.statuses import FHIR_SYNC_STATUS_SYNCED


class PatientRepositoryPort(Protocol):
    def list_patient_records(self, protocol_version: str = "") -> list[dict[str, Any]]: ...

    def create_patient_record(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def get_patient_record(self, record_id: int) -> dict[str, Any]: ...

    def create_patient_fhir_workflow_record(self, patient: dict[str, Any]) -> dict[str, Any]: ...

    def mark_fhir_sync_failure(self, record_id: int, *, error_text: str) -> dict[str, Any]: ...

    def create_dcm4chee_e2e_demo_fixture(
        self, profile: dict[str, Any], *, uid_root: str
    ) -> dict[str, Any]: ...


class PatientWorkflowService:
    def __init__(
        self,
        repository: PatientRepositoryPort,
        configuration: Mapping[str, Any],
        *,
        medplum_base_url: Callable[[], str],
        auth_manager: Callable[[], Any],
        fhir_sync: Callable[..., Any],
        dicom_patient_sync: Callable[..., Any],
        dcm_result_refresh: Callable[..., dict[str, Any]],
        dcm_profile: Callable[[Mapping[str, Any]], dict[str, Any]],
    ) -> None:
        self._repository = repository
        self._configuration = configuration
        self._medplum_base_url = medplum_base_url
        self._auth_manager = auth_manager
        self._fhir_sync = fhir_sync
        self._dicom_patient_sync = dicom_patient_sync
        self._dcm_result_refresh = dcm_result_refresh
        self._dcm_profile = dcm_profile

    def list(self, protocol_version: str = "") -> list[dict[str, Any]]:
        return self._repository.list_patient_records(protocol_version)

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        item = self._repository.create_patient_record(payload)
        if item["protocolVersion"] == "FHIR R4":
            record = self._repository.create_patient_fhir_workflow_record(item)
            base_url = self._medplum_base_url()
            if base_url:
                self._fhir_sync(
                    self._repository,
                    int(record["id"]),
                    base_url=base_url,
                    auth_manager=self._auth_manager(),
                )
            else:
                self._repository.mark_fhir_sync_failure(
                    int(record["id"]), error_text="Medplum FHIR base URL is required."
                )
            return self._repository.get_patient_record(int(item["id"]))
        if item["protocolVersion"] == "DICOM":
            self._dicom_patient_sync(
                self._repository, item, self._dcm_profile(self._configuration)
            )
            return self._repository.get_patient_record(int(item["id"]))
        return item

    def sync_fhir(self, record_id: int) -> tuple[bool, dict[str, Any]]:
        item = self._repository.get_patient_record(record_id)
        if item["protocolVersion"] != "FHIR R4":
            raise ValueError("Patient record is not FHIR mode.")
        record = item.get("fhir") or self._repository.create_patient_fhir_workflow_record(item)
        base_url = self._medplum_base_url()
        if not base_url:
            raise ValueError("Medplum FHIR base URL is required.")
        self._fhir_sync(
            self._repository,
            int(record.get("recordId") or record["id"]),
            base_url=base_url,
            auth_manager=self._auth_manager(),
        )
        item = self._repository.get_patient_record(record_id)
        status = ((item.get("fhir") or {}).get("sync") or {}).get("status")
        return status == FHIR_SYNC_STATUS_SYNCED, item

    def refresh_dcm4chee_results(self, record_id: int) -> dict[str, Any]:
        return self._dcm_result_refresh(
            self._repository, record_id, self._dcm_profile(self._configuration)
        )

    def create_dcm4chee_fixture(self) -> dict[str, Any]:
        return self._repository.create_dcm4chee_e2e_demo_fixture(
            self._dcm_profile(self._configuration),
            uid_root=str(self._configuration["DCM4CHEE_UID_ROOT"]),
        )
