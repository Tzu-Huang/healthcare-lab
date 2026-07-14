"""Patient workflow coordination independent of Flask request state."""

from __future__ import annotations

import socket
import urllib.parse
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any, Protocol

from backend.clients.oie import send_hl7_mllp_message
from backend.clients import dcm4chee as dcm4chee_client
from backend.domain.errors import SimulatorValidationError, UpstreamDcm4cheeError, ValidationError
from backend.domain.statuses import (
    DCM4CHEE_PATIENT_SYNC_OPERATION_ADT_CREATE,
    DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
    DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED,
    DCM4CHEE_RESULT_STATUS_DUPLICATE,
    DCM4CHEE_RESULT_STATUS_NO_RESULT,
    DCM4CHEE_RESULT_STATUS_QUERY_FAILED,
    FHIR_SYNC_STATUS_SYNCED,
)
from backend.services.oie_workflow import parse_hl7_ack

request_dcm4chee_qido = dcm4chee_client.request_dcm4chee_qido


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


def dcm4chee_result_query_from_mapping(mapping: dict[str, Any]) -> dict[str, str]:
    query = {
        "StudyInstanceUID": str(mapping.get("studyInstanceUid") or "").strip(),
        "AccessionNumber": str(mapping.get("accessionNumber") or "").strip(),
        "PatientID": str(mapping.get("patientId") or "").strip(),
        "IssuerOfPatientID": str(mapping.get("issuerOfPatientId") or "").strip(),
    }
    return {key: value for key, value in query.items() if value}


def dcm4chee_merge_result_metadata(
    base_metadata: dict[str, str],
    child_metadata: dict[str, str],
) -> dict[str, str]:
    merged = {**base_metadata}
    for key, value in child_metadata.items():
        if value or key not in merged:
            merged[key] = value
    return merged


def dcm4chee_result_refresh_generation(
    *,
    clock: Callable[..., datetime] = datetime.now,
    identifier_factory: Callable[[], Any] = uuid.uuid4,
) -> str:
    timestamp = clock(timezone.utc).isoformat(timespec="microseconds")
    return f"{timestamp}-{identifier_factory().hex}"


def refresh_patient_dcm4chee_results(
    store: PatientRepositoryPort,
    patient_record_id: int,
    profile: dict[str, Any],
) -> dict[str, Any]:
    store.get_patient_record(patient_record_id)
    mappings = store.list_dcm4chee_mwl_mappings_for_patient(patient_record_id)
    refreshed: list[dict[str, Any]] = []
    queries: list[dict[str, Any]] = []
    study_uid_counts: dict[str, int] = {}
    refresh_generation = dcm4chee_result_refresh_generation()
    store.begin_dcm4chee_result_refresh(patient_record_id, refresh_generation)
    if not mappings:
        diagnostic = store.record_dcm4chee_result_refresh_diagnostic(
            patient_record_id=patient_record_id,
            profile=profile,
            status=DCM4CHEE_RESULT_STATUS_NO_RESULT,
            diagnostic_payload={"reason": "no_local_dcm4chee_orders"},
            refresh_generation=refresh_generation,
        )
        store.complete_dcm4chee_result_refresh(patient_record_id, refresh_generation)
        patient = store.get_patient_record(patient_record_id)
        return {
            "success": True,
            "patient": patient,
            "items": patient.get("dcm4chee", {}).get("dicomResults", []),
            "refreshed": [diagnostic],
            "queries": [],
            "refreshGeneration": refresh_generation,
        }

    for mapping in mappings:
        query = dcm4chee_result_query_from_mapping(mapping)
        try:
            status, studies_body, studies_url = request_dcm4chee_qido(profile, "studies", query)
        except (ValidationError, SimulatorValidationError) as exc:
            diagnostic = store.record_dcm4chee_result_refresh_diagnostic(
                patient_record_id=patient_record_id,
                profile=profile,
                status=DCM4CHEE_RESULT_STATUS_QUERY_FAILED,
                query_payload=query,
                diagnostic_payload={"reason": "profile_invalid", "error": str(exc)},
                refresh_generation=refresh_generation,
            )
            refreshed.append(diagnostic)
            continue
        except UpstreamDcm4cheeError as exc:
            diagnostic = store.record_dcm4chee_result_refresh_diagnostic(
                patient_record_id=patient_record_id,
                profile=profile,
                status=DCM4CHEE_RESULT_STATUS_QUERY_FAILED,
                query_payload=query,
                diagnostic_payload={
                    "reason": "dcm4chee_query_failed",
                    "error": str(exc),
                    "httpStatus": exc.http_status,
                    "responseBody": exc.response_body,
                },
                refresh_generation=refresh_generation,
            )
            refreshed.append(diagnostic)
            continue
        queries.append({"url": studies_url, "status": status, "query": query})
        study_datasets = store.dcm4chee_datasets_from_response_body(studies_body)
        if not study_datasets:
            diagnostic = store.record_dcm4chee_result_refresh_diagnostic(
                patient_record_id=patient_record_id,
                profile=profile,
                status=DCM4CHEE_RESULT_STATUS_NO_RESULT,
                query_url=studies_url,
                query_payload=query,
                diagnostic_payload={"reason": "empty_study_query", "mappingId": mapping.get("id")},
                refresh_generation=refresh_generation,
            )
            refreshed.append(diagnostic)
            continue
        for study_dataset in study_datasets:
            study_metadata = store.dcm4chee_result_metadata_from_dataset(study_dataset)
            study_uid = study_metadata.get("study_instance_uid", "")
            if study_uid:
                study_uid_counts[study_uid] = study_uid_counts.get(study_uid, 0) + 1
            refreshed.append(
                store.upsert_dcm4chee_result_record(
                    study_metadata,
                    profile,
                    patient_record_id=patient_record_id,
                    query_url=studies_url,
                    query_payload=query,
                    raw_metadata=study_dataset,
                    refresh_generation=refresh_generation,
                )
            )
            if not study_uid:
                continue
            study_path = f"studies/{urllib.parse.quote(study_uid, safe='')}"
            for child_path in (f"{study_path}/series", f"{study_path}/instances"):
                try:
                    _child_status, child_body, child_url = request_dcm4chee_qido(profile, child_path, {})
                except UpstreamDcm4cheeError:
                    continue
                for child_dataset in store.dcm4chee_datasets_from_response_body(child_body):
                    child_metadata = store.dcm4chee_result_metadata_from_dataset(child_dataset)
                    metadata = dcm4chee_merge_result_metadata(study_metadata, child_metadata)
                    refreshed.append(
                        store.upsert_dcm4chee_result_record(
                            metadata,
                            profile,
                            patient_record_id=patient_record_id,
                            query_url=child_url,
                            query_payload={"parentStudyInstanceUID": study_uid},
                            raw_metadata=child_dataset,
                            refresh_generation=refresh_generation,
                        )
                    )

    for study_uid, count in study_uid_counts.items():
        if count > 1:
            refreshed.append(
                store.record_dcm4chee_result_refresh_diagnostic(
                    patient_record_id=patient_record_id,
                    profile=profile,
                    status=DCM4CHEE_RESULT_STATUS_DUPLICATE,
                    query_payload={"studyInstanceUid": study_uid},
                    diagnostic_payload={
                        "reason": "duplicate_study_candidates",
                        "studyInstanceUid": study_uid,
                        "count": count,
                    },
                    refresh_generation=refresh_generation,
                )
            )
    store.complete_dcm4chee_result_refresh(patient_record_id, refresh_generation)
    patient = store.get_patient_record(patient_record_id)
    return {
        "success": not any(
            item.get("reconciliationStatus") == DCM4CHEE_RESULT_STATUS_QUERY_FAILED
            for item in refreshed
        ),
        "patient": patient,
        "items": patient.get("dcm4chee", {}).get("dicomResults", []),
        "refreshed": refreshed,
        "queries": queries,
        "refreshGeneration": refresh_generation,
    }
