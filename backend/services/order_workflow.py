"""Order workflow coordination independent of Flask request state."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol

from backend.clients import dcm4chee as dcm4chee_client
from backend.domain.errors import SimulatorValidationError
from backend.domain.statuses import (
    DCM4CHEE_MWL_STATUS_CREATED,
    DCM4CHEE_MWL_VERIFICATION_VERIFIED,
)


def _dicom_first_value(payload: dict[str, Any], tag: str, default: str = "") -> str:
    element = payload.get(tag) if isinstance(payload, dict) else None
    if not isinstance(element, dict):
        return default
    values = element.get("Value")
    if not isinstance(values, list) or not values:
        return default
    value = values[0]
    if isinstance(value, dict):
        return str(value.get("Alphabetic") or default).strip()
    return str(value or default).strip()


def dcm4chee_patient_payload_from_mwl_payload(payload: dict[str, Any]) -> dict[str, Any]:
    patient_payload = {
        tag: payload[tag]
        for tag in ("00100010", "00100020", "00100021", "00100030", "00100040")
        if tag in payload
    }
    if "00100020" not in patient_payload:
        raise SimulatorValidationError("dcm4chee Patient ID is required before MWL sync.")
    return patient_payload


def ensure_dcm4chee_patient_for_mwl_payload(
    profile: dict[str, Any], payload: dict[str, Any]
) -> dict[str, Any]:
    identifiers = {
        "patient_id": _dicom_first_value(payload, "00100020"),
        "issuer_of_patient_id": _dicom_first_value(payload, "00100021"),
    }
    if not identifiers["patient_id"]:
        raise SimulatorValidationError("dcm4chee Patient ID is required before MWL sync.")
    status, response_body, lookup_url = dcm4chee_client.request_dcm4chee_patient_search(
        profile,
        patient_id=identifiers["patient_id"],
        issuer_of_patient_id=identifiers["issuer_of_patient_id"],
    )
    if status == 200 and response_body.strip():
        return {"status": "found", "httpStatus": status, "url": lookup_url, **identifiers}
    patient_payload = dcm4chee_patient_payload_from_mwl_payload(payload)
    create_status, create_body, create_url = dcm4chee_client.request_dcm4chee_patient_create(
        profile, patient_payload
    )
    return {
        "status": "created",
        "httpStatus": create_status,
        "url": create_url,
        "responseBody": create_body,
        **identifiers,
    }


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
