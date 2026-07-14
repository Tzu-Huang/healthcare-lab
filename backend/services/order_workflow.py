"""Order workflow coordination independent of Flask request state."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol

from backend.lab_store import DCM4CHEE_MWL_STATUS_CREATED, DCM4CHEE_MWL_VERIFICATION_VERIFIED


class OrderRepositoryPort(Protocol):
    def list_order_records(self) -> list[dict[str, Any]]: ...

    def get_order_record(self, order_id: int) -> dict[str, Any]: ...

    def create_order_record(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def create_fhir_order_record(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def create_dcm4chee_order_record(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def create_order_service_request_fhir_workflow_record(
        self, order: dict[str, Any]
    ) -> dict[str, Any]: ...

    def mark_fhir_sync_failure(self, record_id: int, *, error_text: str) -> dict[str, Any]: ...

    def list_dcm4chee_mwl_attempts(self, order_id: int) -> list[dict[str, Any]]: ...

    def dcm4chee_e2e_evidence_for_order(
        self, order_id: int, profile: dict[str, Any]
    ) -> dict[str, Any]: ...

    def create_simulated_dcm4chee_ap_return(
        self,
        order_id: int,
        profile: dict[str, Any],
        *,
        result_type: str,
        artifact_url: str,
        artifact_path: str,
    ) -> dict[str, Any]: ...

    def get_patient_record(self, record_id: int) -> dict[str, Any]: ...


class OrderWorkflowService:
    def __init__(
        self,
        repository: OrderRepositoryPort,
        configuration: Mapping[str, Any],
        *,
        medplum_base_url: Callable[[], str],
        auth_manager: Callable[[], Any],
        fhir_sync: Callable[..., Any],
        dcm_sync: Callable[..., Any],
        dcm_verify: Callable[..., dict[str, Any]],
        dcm_profile: Callable[[Mapping[str, Any]], dict[str, Any]],
    ) -> None:
        self._repository = repository
        self._configuration = configuration
        self._medplum_base_url = medplum_base_url
        self._auth_manager = auth_manager
        self._fhir_sync = fhir_sync
        self._dcm_sync = dcm_sync
        self._dcm_verify = dcm_verify
        self._dcm_profile = dcm_profile

    def list(self) -> list[dict[str, Any]]:
        return self._repository.list_order_records()

    def get(self, order_id: int) -> dict[str, Any]:
        return self._repository.get_order_record(order_id)

    def get_dicom(self, order_id: int) -> dict[str, Any]:
        item = self.get(order_id)
        if item["protocolVersion"] != "DICOM":
            raise ValueError("Order record is not DICOM MWL mode.")
        return item

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        mode = str(payload.get("mode") or "").strip().lower()
        if mode == "fhir":
            item = self._repository.create_fhir_order_record(payload)
            record = self._repository.create_order_service_request_fhir_workflow_record(item)
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
            return self._repository.get_order_record(int(item["id"]))
        if mode == "dicom":
            item = self._repository.create_dcm4chee_order_record(payload)
            self._dcm_sync(
                self._repository,
                item,
                self._dcm_profile(self._configuration),
                uid_root=self._configuration["DCM4CHEE_UID_ROOT"],
            )
            return self._repository.get_order_record(int(item["id"]))
        return self._repository.create_order_record(payload)

    def list_dcm4chee_attempts(self, order_id: int) -> list[dict[str, Any]]:
        self.get_dicom(order_id)
        return self._repository.list_dcm4chee_mwl_attempts(order_id)

    def sync_dcm4chee(self, order_id: int) -> dict[str, Any]:
        item = self.get_dicom(order_id)
        self._dcm_sync(
            self._repository,
            item,
            self._dcm_profile(self._configuration),
            uid_root=self._configuration["DCM4CHEE_UID_ROOT"],
        )
        item = self._repository.get_order_record(order_id)
        mwl = (item.get("dcm4chee") or {}).get("mwl") or {}
        return {
            "success": (mwl.get("mapping") or {}).get("status") == DCM4CHEE_MWL_STATUS_CREATED,
            "item": item,
            "mwl": mwl,
            "latestAttempt": mwl if mwl.get("id") else None,
        }

    def verify_dcm4chee(self, order_id: int) -> dict[str, Any]:
        item = self.get_dicom(order_id)
        result = self._dcm_verify(
            self._repository, item, self._dcm_profile(self._configuration)
        )
        item = self._repository.get_order_record(order_id)
        mwl = (item.get("dcm4chee") or {}).get("mwl") or {}
        verification = (mwl.get("mapping") or {}).get("verification") or mwl.get("verification") or {}
        return {
            "success": verification.get("status") == DCM4CHEE_MWL_VERIFICATION_VERIFIED,
            "item": item,
            "mwl": mwl,
            "verification": verification,
            "latestAttempt": result.get("attempt"),
        }

    def dcm4chee_evidence(self, order_id: int) -> dict[str, Any]:
        self.get_dicom(order_id)
        return self._repository.dcm4chee_e2e_evidence_for_order(
            order_id, self._dcm_profile(self._configuration)
        )

    def create_dcm4chee_simulated_return(
        self, order_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        item = self.get_dicom(order_id)
        result = self._repository.create_simulated_dcm4chee_ap_return(
            order_id,
            self._dcm_profile(self._configuration),
            result_type=str(payload.get("type") or "both"),
            artifact_url=str(payload.get("artifactUrl") or ""),
            artifact_path=str(payload.get("artifactPath") or ""),
        )
        patient = self._repository.get_patient_record(int(item["patientRecordId"]))
        return {"patient": patient, **result}
