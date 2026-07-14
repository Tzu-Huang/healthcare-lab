"""Patient workflow coordination independent of Flask request state."""

from __future__ import annotations

import socket
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from backend.clients.oie import send_hl7_mllp_message
from backend.domain.statuses import (
    DCM4CHEE_PATIENT_SYNC_OPERATION_ADT_CREATE,
    DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
    DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED,
    FHIR_SYNC_STATUS_SYNCED,
)
from backend.services.oie_workflow import parse_hl7_ack


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


def sync_patient_to_dcm4chee(
    store: PatientRepositoryPort,
    patient: dict[str, Any],
    profile: dict[str, Any],
    *,
    operation_type: str = DCM4CHEE_PATIENT_SYNC_OPERATION_ADT_CREATE,
    timeout_seconds: float = 10,
    sender: Callable[..., str] = send_hl7_mllp_message,
) -> dict[str, Any]:
    hl7 = profile.get("hl7") if isinstance(profile.get("hl7"), dict) else {}
    host = str(hl7.get("host") or "").strip()
    port = int(hl7.get("port") or 0)
    request_url = f"mllp://{host}:{port}" if host and port else ""
    event_type = "A08" if operation_type == "adt-update" else "A04"
    payload = store.build_dcm4chee_patient_adt_payload(patient, profile, event_type=event_type)
    sync = store.upsert_dcm4chee_patient_sync(
        int(patient["id"]),
        profile,
        sync_status=DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
        increment_retry=store.get_dcm4chee_patient_sync_for_patient(int(patient["id"]), profile) is not None,
    )
    attempt = store.create_dcm4chee_patient_sync_attempt(
        int(patient["id"]),
        profile,
        patient_sync_id=int(sync["id"]),
        operation_type=operation_type,
        request_url=request_url,
        request_payload=payload,
    )
    try:
        response_payload = sender(
            payload,
            host=host,
            port=port,
            timeout_seconds=timeout_seconds,
            framing=True,
        )
    except (OSError, socket.timeout, TimeoutError) as exc:
        updated_attempt = store.update_dcm4chee_patient_sync_attempt_result(
            int(attempt["id"]),
            attempt_status=DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
            error_type="dcm4chee_hl7_unreachable",
            error_text=str(exc),
        )
        return store.update_dcm4chee_patient_sync_from_attempt(
            int(sync["id"]),
            updated_attempt,
            sync_status=DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
        )

    ack = parse_hl7_ack(response_payload)
    accepted = ack.get("code") == "AA"
    error_type = "" if accepted else "dcm4chee_hl7_rejected"
    error_text = "" if accepted else (ack.get("text") or f"dcm4chee returned HL7 ACK {ack.get('code') or 'unknown'}.")
    updated_attempt = store.update_dcm4chee_patient_sync_attempt_result(
        int(attempt["id"]),
        attempt_status=DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED if accepted else DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
        response_payload=response_payload,
        ack=ack,
        error_type=error_type,
        error_text=error_text,
    )
    return store.update_dcm4chee_patient_sync_from_attempt(
        int(sync["id"]),
        updated_attempt,
        sync_status=DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED if accepted else DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
    )
