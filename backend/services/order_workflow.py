"""Order workflow coordination independent of Flask request state."""

from __future__ import annotations

import json
import urllib.parse
from collections.abc import Callable, Mapping
from typing import Any, Protocol, runtime_checkable

from backend.clients import dcm4chee as dcm4chee_client
from backend.domain.dicom import validate_dcm4chee_profile
from backend.domain.errors import SimulatorValidationError, UpstreamDcm4cheeError
from backend.domain.statuses import (
    DCM4CHEE_MWL_OPERATION_CREATE,
    DCM4CHEE_MWL_OPERATION_READBACK,
    DCM4CHEE_MWL_STATUS_CREATED,
    DCM4CHEE_MWL_STATUS_FAILED,
    DCM4CHEE_MWL_STATUS_PATIENT_MISSING,
    DCM4CHEE_MWL_STATUS_PENDING,
    DCM4CHEE_MWL_VERIFICATION_AMBIGUOUS,
    DCM4CHEE_MWL_VERIFICATION_FAILED,
    DCM4CHEE_PATIENT_SYNC_OPERATION_PREFLIGHT,
    DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED,
    DCM4CHEE_MWL_VERIFICATION_VERIFIED,
)
from backend.services.patient_workflow import require_dcm4chee_enabled, sync_patient_to_dcm4chee

request_dcm4chee_mwl_create = dcm4chee_client.request_dcm4chee_mwl_create
request_dcm4chee_mwl_readback = dcm4chee_client.request_dcm4chee_mwl_readback
request_dcm4chee_mwl_verification = dcm4chee_client.request_dcm4chee_mwl_verification


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


class OrderLedgerPort(Protocol):
    def list_order_records(self) -> list[dict[str, Any]]: ...

    def get_order_record(self, order_id: int) -> dict[str, Any]: ...

    def create_order_record(self, payload: dict[str, Any]) -> dict[str, Any]: ...



@runtime_checkable
class OrderCoordinationPort(Protocol):
    def build_dcm4chee_mwl_payload(self, order: dict[str, Any], profile: dict[str, Any], *, uid_root: str = "1.2.826.0.1.3680043.10.543") -> dict[str, Any]: ...

    def create_dcm4chee_mwl_attempt(self, order_record_id: int, profile: dict[str, Any], *, uid_root: str = "1.2.826.0.1.3680043.10.543", request_url: str = "", request_payload: dict[str, Any] | None = None, attempt_status: str = "Pending sync", error_type: str = "", error_text: str = "", http_status: int | None = None, response_body: str = "", operation_type: str = "create", mapping_id: int | None = None) -> dict[str, Any]: ...

    def create_dcm4chee_mwl_profile_failure_attempt(self, order_record_id: int, profile: dict[str, Any], *, uid_root: str = "1.2.826.0.1.3680043.10.543", request_url: str = "", diagnostics: dict[str, Any] | None = None) -> dict[str, Any]: ...

    def create_dcm4chee_mwl_verification_attempt(self, order_record_id: int, mapping: dict[str, Any], *, request_url: str, query_criteria: dict[str, str], attempt_status: str = "Pending sync", error_type: str = "", error_text: str = "", http_status: int | None = None, response_body: str = "") -> dict[str, Any]: ...

    def create_dcm4chee_order_record(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def create_fhir_order_record(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def create_order_service_request_fhir_workflow_record(self, order: dict[str, Any]) -> dict[str, Any]: ...

    def create_simulated_dcm4chee_ap_return(self, order_record_id: int, profile: dict[str, Any], *, result_type: str = "both", artifact_url: str = "", artifact_path: str = "") -> dict[str, Any]: ...

    def dcm4chee_datasets_from_response_body(self, response_body: str) -> list[dict[str, Any]]: ...

    def dcm4chee_e2e_evidence_for_order(self, order_record_id: int, profile: dict[str, Any]) -> dict[str, Any]: ...

    def dcm4chee_identifiers_from_dataset(self, dataset: dict[str, Any]) -> dict[str, str]: ...

    def dcm4chee_identifiers_from_payload(self, order: dict[str, Any], profile: dict[str, Any], *, uid_root: str = "1.2.826.0.1.3680043.10.543", payload: dict[str, Any] | None = None) -> dict[str, str]: ...

    def dcm4chee_identifiers_from_response_body(self, response_body: str) -> dict[str, str]: ...

    def dcm4chee_mwl_verification_query_from_mapping(self, mapping: dict[str, Any]) -> dict[str, str]: ...

    def get_dcm4chee_mwl_mapping_for_order(self, order_record_id: int) -> dict[str, Any] | None: ...

    def get_dcm4chee_patient_sync_for_patient(self, patient_record_id: int, profile: dict[str, Any] | None = None) -> dict[str, Any] | None: ...

    def get_fhir_workflow_record(self, record_id: int) -> dict[str, Any]: ...

    def get_order_record(self, record_id: int) -> dict[str, Any]: ...

    def get_patient_record(self, record_id: int) -> dict[str, Any]: ...

    def list_dcm4chee_mwl_attempts(self, order_record_id: int | None = None) -> list[dict[str, Any]]: ...

    def mark_fhir_sync_failure(self, record_id: int, *, error_text: str, operation_outcome: dict[str, Any] | None = None) -> dict[str, Any]: ...

    def mark_fhir_sync_success(self, record_id: int, *, medplum_resource_id: str, medplum_resource_reference: str = "") -> dict[str, Any]: ...

    def mark_fhir_syncing(self, record_id: int) -> dict[str, Any]: ...

    def record_fhir_sync_attempt(self, record_id: int, *, method: str, request_url: str, request_payload: dict[str, Any] | None = None, http_status: int | None = None, response_payload: dict[str, Any] | None = None, operation_outcome: dict[str, Any] | None = None, error_text: str = "") -> dict[str, Any]: ...

    def update_dcm4chee_mwl_attempt_result(self, attempt_id: int, *, attempt_status: str, http_status: int | None = None, response_body: str = "", error_type: str = "", error_text: str = "") -> dict[str, Any]: ...

    def update_dcm4chee_mwl_mapping_from_attempt(self, order_record_id: int, *, attempt_id: int | None, sync_status: str, http_status: int | None = None, response_body: str = "", error_type: str = "", error_text: str = "", error_payload: dict[str, Any] | None = None, readback_payload: dict[str, Any] | list[Any] | None = None, identifiers: dict[str, str] | None = None) -> dict[str, Any]: ...

    def update_dcm4chee_mwl_verification_result(self, order_record_id: int, *, attempt_id: int, verification_status: str, method: str, query_criteria: dict[str, Any], match_payload: dict[str, Any] | None = None, error_type: str = "", error_text: str = "", error_payload: dict[str, Any] | None = None) -> dict[str, Any]: ...

    def upsert_dcm4chee_mwl_mapping(self, order_record_id: int, profile: dict[str, Any], *, uid_root: str = "1.2.826.0.1.3680043.10.543", request_payload: dict[str, Any] | None = None, sync_status: str = "Pending sync", increment_retry: bool = False) -> dict[str, Any]: ...


class OrderFhirCapability(Protocol):
    def create_fhir_order_record(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def create_order_service_request_fhir_workflow_record(self, order: dict[str, Any]) -> dict[str, Any]: ...
    def mark_fhir_sync_failure(self, record_id: int, *, error_text: str, operation_outcome: dict[str, Any] | None = None) -> dict[str, Any]: ...


class DcmOrderCapability(Protocol):
    def create_dcm4chee_order_record(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def list_dcm4chee_mwl_attempts(self, order_record_id: int | None = None) -> list[dict[str, Any]]: ...


class DcmEvidenceCapability(Protocol):
    def dcm4chee_e2e_evidence_for_order(self, order_record_id: int, profile: dict[str, Any]) -> dict[str, Any]: ...
    def create_simulated_dcm4chee_ap_return(self, order_record_id: int, profile: dict[str, Any], *, result_type: str = "both", artifact_url: str = "", artifact_path: str = "") -> dict[str, Any]: ...
    def get_patient_record(self, record_id: int) -> dict[str, Any]: ...


class DcmOrderSync(Protocol):
    def __call__(self, order: dict[str, Any], profile: dict[str, Any], *, uid_root: str) -> dict[str, Any]: ...


class DcmOrderVerification(Protocol):
    def __call__(self, order: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]: ...


class DcmMwlSyncService:
    """Coordinate DICOM Order eligibility, patient prerequisite, and MWL sync."""

    def __init__(self, repository: OrderLedgerPort, configuration: Mapping[str, Any], *, dcm_sync: DcmOrderSync, dcm_profile: Callable[[Mapping[str, Any]], dict[str, Any]]) -> None:
        self._repository = repository
        self._configuration = configuration
        self._dcm_sync = dcm_sync
        self._dcm_profile = dcm_profile

    def get_order(self, order_id: int) -> dict[str, Any]:
        item = self._repository.get_order_record(order_id)
        if item["protocolVersion"] != "DICOM":
            raise ValueError("Order record is not DICOM MWL mode.")
        return item

    def sync(self, order_id: int) -> dict[str, Any]:
        profile = self._dcm_profile(self._configuration)
        require_dcm4chee_enabled(profile)
        self._dcm_sync(
            self.get_order(order_id),
            profile,
            uid_root=str(profile["uidRoot"]),
        )
        item = self._repository.get_order_record(order_id)
        mwl = (item.get("dcm4chee") or {}).get("mwl") or {}
        return {"success": (mwl.get("mapping") or {}).get("status") == DCM4CHEE_MWL_STATUS_CREATED, "item": item, "mwl": mwl, "latestAttempt": mwl if mwl.get("id") else None}



class DcmMwlVerificationService:
    """Coordinate MWL verification and expose its persisted view."""

    def __init__(self, repository: OrderLedgerPort, configuration: Mapping[str, Any], *, dcm_verify: DcmOrderVerification, dcm_profile: Callable[[Mapping[str, Any]], dict[str, Any]]) -> None:
        self._repository = repository
        self._configuration = configuration
        self._dcm_verify = dcm_verify
        self._dcm_profile = dcm_profile

    def verify(self, order_id: int) -> dict[str, Any]:
        item = self._repository.get_order_record(order_id)
        if item["protocolVersion"] != "DICOM":
            raise ValueError("Order record is not DICOM MWL mode.")
        profile = self._dcm_profile(self._configuration)
        require_dcm4chee_enabled(profile)
        result = self._dcm_verify(item, profile)
        item = self._repository.get_order_record(order_id)
        mwl = (item.get("dcm4chee") or {}).get("mwl") or {}
        verification = (mwl.get("mapping") or {}).get("verification") or mwl.get("verification") or {}
        return {"success": verification.get("status") == DCM4CHEE_MWL_VERIFICATION_VERIFIED, "item": item, "mwl": mwl, "verification": verification, "latestAttempt": result.get("attempt")}


class DcmEvidenceService:
    """Coordinate dcm4chee evidence and simulated AP-return use cases."""

    def __init__(self, repository: OrderLedgerPort, capability: DcmEvidenceCapability, configuration: Mapping[str, Any], *, dcm_profile: Callable[[Mapping[str, Any]], dict[str, Any]]) -> None:
        self._repository = repository
        self._capability = capability
        self._configuration = configuration
        self._dcm_profile = dcm_profile

    def _order(self, order_id: int) -> dict[str, Any]:
        item = self._repository.get_order_record(order_id)
        if item["protocolVersion"] != "DICOM":
            raise ValueError("Order record is not DICOM MWL mode.")
        return item

    def evidence(self, order_id: int) -> dict[str, Any]:
        self._order(order_id)
        profile = self._dcm_profile(self._configuration)
        require_dcm4chee_enabled(profile)
        return self._capability.dcm4chee_e2e_evidence_for_order(order_id, profile)

    def simulated_return(self, order_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        item = self._order(order_id)
        profile = self._dcm_profile(self._configuration)
        require_dcm4chee_enabled(profile)
        result = self._capability.create_simulated_dcm4chee_ap_return(order_id, profile, result_type=str(payload.get("type") or "both"), artifact_url=str(payload.get("artifactUrl") or ""), artifact_path=str(payload.get("artifactPath") or ""))
        return {"patient": self._capability.get_patient_record(int(item["patientRecordId"])), **result}


class OrderWorkflowService:
    def __init__(
        self,
        repository: OrderLedgerPort,
        configuration: Mapping[str, Any],
        *,
        coordination: OrderCoordinationPort | None = None,
        fhir_capability: OrderFhirCapability | None = None,
        dcm_order_capability: DcmOrderCapability | None = None,
        evidence_capability: DcmEvidenceCapability | None = None,
        medplum_base_url: Callable[[], str],
        auth_manager: Callable[[], Any],
        fhir_sync: Callable[..., Any],
        dcm_sync: Callable[..., Any],
        dcm_verify: Callable[..., dict[str, Any]],
        dcm_profile: Callable[[Mapping[str, Any]], dict[str, Any]],
    ) -> None:
        self._repository = repository
        fallback = coordination or repository
        self._fhir = fhir_capability or fallback
        self._dcm_order = dcm_order_capability or fallback
        self._evidence = evidence_capability or fallback
        self._coordination = fallback  # compatibility inspection only
        self._configuration = configuration
        self._medplum_base_url = medplum_base_url
        self._auth_manager = auth_manager
        self._fhir_sync = fhir_sync
        self._dcm_sync = dcm_sync
        self._dcm_verify = dcm_verify
        self._dcm_profile = dcm_profile
        self.mwl_sync_service = DcmMwlSyncService(repository, configuration, dcm_sync=dcm_sync, dcm_profile=dcm_profile)
        self.mwl_verification_service = DcmMwlVerificationService(repository, configuration, dcm_verify=dcm_verify, dcm_profile=dcm_profile)
        self.evidence_service = DcmEvidenceService(repository, self._evidence, configuration, dcm_profile=dcm_profile)


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
            item = self._fhir.create_fhir_order_record(payload)
            record = self._fhir.create_order_service_request_fhir_workflow_record(item)
            base_url = self._medplum_base_url()
            if base_url:
                self._fhir_sync(
                    int(record["id"]),
                    base_url=base_url,
                    auth_manager=self._auth_manager(),
                )
            else:
                self._fhir.mark_fhir_sync_failure(
                    int(record["id"]), error_text="Medplum FHIR base URL is required."
                )
            return self._repository.get_order_record(int(item["id"]))
        if mode == "dicom":
            profile = self._dcm_profile(self._configuration)
            require_dcm4chee_enabled(profile)
            item = self._dcm_order.create_dcm4chee_order_record(payload)
            self._dcm_sync(
                item,
                profile,
                uid_root=str(profile["uidRoot"]),
            )
            return self._repository.get_order_record(int(item["id"]))
        return self._repository.create_order_record(payload)

    def list_dcm4chee_attempts(self, order_id: int) -> list[dict[str, Any]]:
        self.get_dicom(order_id)
        return self._dcm_order.list_dcm4chee_mwl_attempts(order_id)

    def sync_dcm4chee(self, order_id: int) -> dict[str, Any]:
        return self.mwl_sync_service.sync(order_id)

    def verify_dcm4chee(self, order_id: int) -> dict[str, Any]:
        return self.mwl_verification_service.verify(order_id)

    def dcm4chee_evidence(self, order_id: int) -> dict[str, Any]:
        return self.evidence_service.evidence(order_id)

    def create_dcm4chee_simulated_return(
        self, order_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self.evidence_service.simulated_return(order_id, payload)


def sync_order_to_dcm4chee_mwl(
    store: OrderCoordinationPort,
    order: dict[str, Any],
    profile: dict[str, Any],
    *,
    uid_root: str,
    patient_syncer: Callable[..., dict[str, Any]] = sync_patient_to_dcm4chee,
) -> dict[str, Any]:
    require_dcm4chee_enabled(profile)
    diagnostics = validate_dcm4chee_profile(profile)
    dicomweb = profile.get("dicomweb") if isinstance(profile.get("dicomweb"), dict) else {}
    base_url = str(dicomweb.get("baseUrl") or "").strip().rstrip("/")
    request_url = f"{base_url}/mwlitems" if base_url else ""
    if not diagnostics["valid"]:
        return store.create_dcm4chee_mwl_profile_failure_attempt(
            int(order["id"]),
            profile,
            uid_root=uid_root,
            request_url=request_url,
            diagnostics=diagnostics,
        )
    payload = store.build_dcm4chee_mwl_payload(order, profile, uid_root=uid_root)
    existing_mapping = store.get_dcm4chee_mwl_mapping_for_order(int(order["id"]))
    if existing_mapping and existing_mapping.get("status") == DCM4CHEE_MWL_STATUS_CREATED:
        return existing_mapping
    patient_record_id = int(order.get("patientRecordId") or 0)
    patient_sync = store.get_dcm4chee_patient_sync_for_patient(patient_record_id, profile) if patient_record_id else None
    patient = store.get_patient_record(patient_record_id) if patient_record_id else {}
    requires_patient_sync = patient.get("protocolVersion") == "DICOM" or patient_sync is not None
    if requires_patient_sync and (not patient_sync or patient_sync.get("status") != DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED):
        patient_sync = patient_syncer(
            store,
            patient,
            profile,
            operation_type=DCM4CHEE_PATIENT_SYNC_OPERATION_PREFLIGHT,
        )
    if requires_patient_sync and (not patient_sync or patient_sync.get("status") != DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED):
        mapping = store.upsert_dcm4chee_mwl_mapping(
            int(order["id"]),
            profile,
            uid_root=uid_root,
            request_payload=payload,
            sync_status=DCM4CHEE_MWL_STATUS_PATIENT_MISSING,
            increment_retry=existing_mapping is not None,
        )
        error_text = (
            str(patient_sync.get("lastError") or "")
            if patient_sync
            else "dcm4chee Patient sync is required before MWL creation."
        )
        if not error_text:
            error_text = "dcm4chee Patient sync is required before MWL creation."
        attempt = store.create_dcm4chee_mwl_attempt(
            int(order["id"]),
            profile,
            uid_root=uid_root,
            request_url=request_url,
            request_payload=payload,
            attempt_status=DCM4CHEE_MWL_STATUS_PATIENT_MISSING,
            error_type="patient_sync_failed",
            error_text=error_text,
            operation_type=DCM4CHEE_MWL_OPERATION_CREATE,
            mapping_id=int(mapping["id"]),
        )
        store.update_dcm4chee_mwl_mapping_from_attempt(
            int(order["id"]),
            attempt_id=int(attempt["id"]),
            sync_status=DCM4CHEE_MWL_STATUS_PATIENT_MISSING,
            error_type="patient_sync_failed",
            error_text=error_text,
            error_payload={"patientSync": patient_sync or {}},
        )
        return attempt
    if not requires_patient_sync:
        try:
            ensure_dcm4chee_patient_for_mwl_payload(profile, payload)
        except UpstreamDcm4cheeError as exc:
            mapping = store.upsert_dcm4chee_mwl_mapping(
                int(order["id"]),
                profile,
                uid_root=uid_root,
                request_payload=payload,
                sync_status=DCM4CHEE_MWL_STATUS_FAILED,
                increment_retry=existing_mapping is not None,
            )
            attempt = store.create_dcm4chee_mwl_attempt(
                int(order["id"]),
                profile,
                uid_root=uid_root,
                request_url=request_url,
                request_payload=payload,
                attempt_status=DCM4CHEE_MWL_STATUS_FAILED,
                error_type="dcm4chee_request_failed",
                error_text=str(exc),
                operation_type=DCM4CHEE_MWL_OPERATION_CREATE,
                mapping_id=int(mapping["id"]),
            )
            store.update_dcm4chee_mwl_mapping_from_attempt(
                int(order["id"]),
                attempt_id=int(attempt["id"]),
                sync_status=DCM4CHEE_MWL_STATUS_FAILED,
                http_status=exc.http_status,
                response_body=exc.response_body,
                error_type=attempt["errorType"],
                error_text=attempt["error"],
                error_payload={"responseBody": exc.response_body},
            )
            return attempt
    if existing_mapping:
        created_but_unconfirmed = (
            int(existing_mapping.get("lastHttpStatus") or 0) in range(200, 300)
            and str(existing_mapping.get("lastErrorType") or "").startswith("dcm4chee_readback")
        )
        readback_attempt = store.create_dcm4chee_mwl_attempt(
            int(order["id"]),
            profile,
            uid_root=uid_root,
            request_url=request_url,
            request_payload=payload,
            operation_type=DCM4CHEE_MWL_OPERATION_READBACK,
            mapping_id=int(existing_mapping["id"]),
        )
        try:
            readback_status, readback_body, _readback_url = request_dcm4chee_mwl_readback(
                profile,
                {
                    "study_instance_uid": existing_mapping.get("studyInstanceUid", ""),
                    "accession_number": existing_mapping.get("accessionNumber", ""),
                    "requested_procedure_id": existing_mapping.get("requestedProcedureId", ""),
                    "scheduled_procedure_step_id": existing_mapping.get("scheduledProcedureStepId", ""),
                    "patient_id": existing_mapping.get("patientId", ""),
                    "issuer_of_patient_id": existing_mapping.get("issuerOfPatientId", ""),
                },
            )
            readback_identifiers = store.dcm4chee_identifiers_from_response_body(readback_body)
            try:
                readback_payload = json.loads(readback_body) if readback_body else {}
            except json.JSONDecodeError:
                readback_payload = {"raw": readback_body}
            readback_status_text = (
                DCM4CHEE_MWL_STATUS_CREATED if readback_identifiers else DCM4CHEE_MWL_STATUS_FAILED
            )
            readback_error = "" if readback_identifiers else "dcm4chee read-back returned no identifiers."
            updated_readback_attempt = store.update_dcm4chee_mwl_attempt_result(
                int(readback_attempt["id"]),
                attempt_status=readback_status_text,
                http_status=readback_status,
                response_body=readback_body,
                error_type="" if readback_identifiers else "dcm4chee_readback_empty",
                error_text=readback_error,
            )
            store.update_dcm4chee_mwl_mapping_from_attempt(
                int(order["id"]),
                attempt_id=int(updated_readback_attempt["id"]),
                sync_status=readback_status_text,
                http_status=readback_status,
                response_body=readback_body,
                error_type=updated_readback_attempt["errorType"],
                error_text=updated_readback_attempt["error"],
                error_payload={} if readback_identifiers else {"responseBody": readback_body},
                readback_payload=readback_payload,
                identifiers=readback_identifiers,
            )
            if readback_identifiers:
                return updated_readback_attempt
            if created_but_unconfirmed:
                return updated_readback_attempt
        except UpstreamDcm4cheeError as exc:
            updated_readback_attempt = store.update_dcm4chee_mwl_attempt_result(
                int(readback_attempt["id"]),
                attempt_status=DCM4CHEE_MWL_STATUS_FAILED,
                http_status=exc.http_status,
                response_body=exc.response_body,
                error_type="dcm4chee_readback_failed",
                error_text=str(exc),
            )
            store.update_dcm4chee_mwl_mapping_from_attempt(
                int(order["id"]),
                attempt_id=int(updated_readback_attempt["id"]),
                sync_status=DCM4CHEE_MWL_STATUS_FAILED,
                http_status=exc.http_status,
                response_body=exc.response_body,
                error_type=updated_readback_attempt["errorType"],
                error_text=updated_readback_attempt["error"],
                error_payload={"responseBody": exc.response_body},
            )
            if created_but_unconfirmed:
                return updated_readback_attempt
    mapping = store.upsert_dcm4chee_mwl_mapping(
        int(order["id"]),
        profile,
        uid_root=uid_root,
        request_payload=payload,
        sync_status=DCM4CHEE_MWL_STATUS_PENDING,
        increment_retry=existing_mapping is not None,
    )
    attempt = store.create_dcm4chee_mwl_attempt(
        int(order["id"]),
        profile,
        uid_root=uid_root,
        request_url=request_url,
        request_payload=payload,
        mapping_id=int(mapping["id"]),
    )
    try:
        status, response_body, actual_url = request_dcm4chee_mwl_create(profile, payload)
    except UpstreamDcm4cheeError as exc:
        response_body = exc.response_body
        lower_body = response_body.lower()
        is_patient_missing = exc.http_status == 404 and "patient" in lower_body and "exist" in lower_body
        updated_attempt = store.update_dcm4chee_mwl_attempt_result(
            int(attempt["id"]),
            attempt_status=DCM4CHEE_MWL_STATUS_PATIENT_MISSING if is_patient_missing else DCM4CHEE_MWL_STATUS_FAILED,
            http_status=exc.http_status,
            response_body=response_body,
            error_type="patient_missing" if is_patient_missing else "dcm4chee_request_failed",
            error_text=str(exc),
        )
        store.update_dcm4chee_mwl_mapping_from_attempt(
            int(order["id"]),
            attempt_id=int(updated_attempt["id"]),
            sync_status=updated_attempt["status"],
            http_status=exc.http_status,
            response_body=response_body,
            error_type=updated_attempt["errorType"],
            error_text=updated_attempt["error"],
            error_payload={"responseBody": response_body},
        )
        return updated_attempt
    if actual_url != attempt["requestUrl"]:
        request_url = actual_url
    response_identifiers = store.dcm4chee_identifiers_from_response_body(response_body)
    readback_payload: dict[str, Any] | list[Any] | None = None
    readback_identifiers: dict[str, str] = {}
    readback_error_type = ""
    readback_error_text = ""
    try:
        readback_status, readback_body, _readback_url = request_dcm4chee_mwl_readback(
            profile,
            {
                **store.dcm4chee_identifiers_from_payload(order, profile, uid_root=uid_root, payload=payload),
                **response_identifiers,
            },
        )
        try:
            readback_payload = json.loads(readback_body) if readback_body else {}
        except json.JSONDecodeError:
            readback_payload = {"raw": readback_body}
        readback_identifiers = store.dcm4chee_identifiers_from_response_body(readback_body)
        if not readback_identifiers:
            readback_error_type = "dcm4chee_readback_empty"
            readback_error_text = "dcm4chee read-back returned no identifiers."
    except UpstreamDcm4cheeError as exc:
        readback_status = exc.http_status
        readback_error_type = "dcm4chee_readback_failed"
        readback_error_text = str(exc)
        readback_payload = {"responseBody": exc.response_body}
    updated_attempt = store.update_dcm4chee_mwl_attempt_result(
        int(attempt["id"]),
        attempt_status=DCM4CHEE_MWL_STATUS_CREATED,
        http_status=status,
        response_body=response_body,
        error_type=readback_error_type,
        error_text=readback_error_text,
    )
    store.update_dcm4chee_mwl_mapping_from_attempt(
        int(order["id"]),
        attempt_id=int(updated_attempt["id"]),
        sync_status=DCM4CHEE_MWL_STATUS_PENDING if readback_error_type else DCM4CHEE_MWL_STATUS_CREATED,
        http_status=status,
        response_body=response_body,
        error_type=readback_error_type,
        error_text=readback_error_text,
        error_payload=readback_payload if readback_error_type else {},
        readback_payload=readback_payload,
        identifiers={**response_identifiers, **readback_identifiers},
    )
    return updated_attempt


def classify_dcm4chee_mwl_verification_error(exc: UpstreamDcm4cheeError) -> str:
    body = str(exc.response_body or "").lower()
    text = str(exc).lower()
    if exc.http_status == 404 and "patient" in body and "exist" in body:
        return "patient_missing"
    if "mwl_rsservice" in body or "no web application" in body:
        return "mwl_endpoint_unsupported"
    if "profile" in text or "baseurl" in text:
        return "mwl_profile_invalid"
    return "dcm4chee_unreachable" if exc.http_status is None else "mwl_query_failed"


def match_dcm4chee_mwl_items(
    store: OrderCoordinationPort,
    mapping: dict[str, Any],
    response_body: str,
) -> dict[str, Any]:
    expected = {
        "patient_id": str(mapping.get("patientId") or "").strip(),
        "issuer_of_patient_id": str(mapping.get("issuerOfPatientId") or "").strip(),
        "accession_number": str(mapping.get("accessionNumber") or "").strip(),
        "requested_procedure_id": str(mapping.get("requestedProcedureId") or "").strip(),
        "scheduled_procedure_step_id": str(mapping.get("scheduledProcedureStepId") or "").strip(),
        "scheduled_station_ae_title": str(mapping.get("scheduledStationAETitle") or "").strip(),
        "study_instance_uid": str(mapping.get("studyInstanceUid") or "").strip(),
        "worklist_label": str(mapping.get("worklistLabel") or "").strip(),
    }
    datasets = store.dcm4chee_datasets_from_response_body(response_body)
    if not datasets:
        return {
            "status": DCM4CHEE_MWL_VERIFICATION_FAILED,
            "errorType": "mwl_empty",
            "error": "dcm4chee MWL query returned no items for the expected identifiers.",
            "match": {},
            "errorPayload": {"expected": expected, "returnedCount": 0},
        }

    candidates: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for index, dataset in enumerate(datasets):
        found = store.dcm4chee_identifiers_from_dataset(dataset)
        strong_matches = []
        if expected["accession_number"] and found.get("accession_number") == expected["accession_number"]:
            strong_matches.append("accession_number")
        if (
            expected["requested_procedure_id"]
            and expected["scheduled_procedure_step_id"]
            and found.get("requested_procedure_id") == expected["requested_procedure_id"]
            and found.get("scheduled_procedure_step_id") == expected["scheduled_procedure_step_id"]
        ):
            strong_matches.append("requested_procedure_id+scheduled_procedure_step_id")
        conflicts = {
            key: {"expected": expected_value, "actual": found.get(key, "")}
            for key, expected_value in expected.items()
            if expected_value and found.get(key) and found.get(key) != expected_value
            and key
            in {
                "patient_id",
                "issuer_of_patient_id",
                "accession_number",
                "requested_procedure_id",
                "scheduled_procedure_step_id",
                "scheduled_station_ae_title",
            }
        }
        summary = {
            "index": index,
            "identifiers": found,
            "strongMatches": strong_matches,
            "conflicts": conflicts,
        }
        if strong_matches and not conflicts:
            candidates.append(summary)
        else:
            mismatches.append(summary)

    if len(candidates) == 1:
        return {
            "status": DCM4CHEE_MWL_VERIFICATION_VERIFIED,
            "errorType": "",
            "error": "",
            "match": {
                **candidates[0],
                "method": "dcm4chee-mwl-rest",
                "expected": expected,
                "returnedCount": len(datasets),
            },
            "errorPayload": {},
        }
    if len(candidates) > 1:
        return {
            "status": DCM4CHEE_MWL_VERIFICATION_AMBIGUOUS,
            "errorType": "mwl_ambiguous",
            "error": "dcm4chee MWL query returned multiple matching items.",
            "match": {},
            "errorPayload": {"expected": expected, "candidates": candidates, "returnedCount": len(datasets)},
        }
    return {
        "status": DCM4CHEE_MWL_VERIFICATION_FAILED,
        "errorType": "mwl_mismatch",
        "error": "dcm4chee MWL query returned items, but none matched the expected order identifiers.",
        "match": {},
        "errorPayload": {"expected": expected, "items": mismatches, "returnedCount": len(datasets)},
    }


def verify_order_dcm4chee_mwl(
    store: OrderCoordinationPort,
    order: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    require_dcm4chee_enabled(profile)
    diagnostics = validate_dcm4chee_profile(profile)
    mapping = store.get_dcm4chee_mwl_mapping_for_order(int(order["id"]))
    if not mapping:
        raise SimulatorValidationError("dcm4chee MWL mapping is not available for this order.")
    query_criteria = store.dcm4chee_mwl_verification_query_from_mapping(mapping)
    dicomweb = profile.get("dicomweb") if isinstance(profile.get("dicomweb"), dict) else {}
    base_url = str(dicomweb.get("baseUrl") or "").strip().rstrip("/")
    request_url = f"{base_url}/mwlitems"
    if query_criteria:
        request_url = f"{request_url}?{urllib.parse.urlencode(query_criteria)}"

    attempt = store.create_dcm4chee_mwl_verification_attempt(
        int(order["id"]),
        mapping,
        request_url=request_url,
        query_criteria=query_criteria,
    )
    method = "dcm4chee-mwl-rest"
    if (
        str(mapping.get("status") or "").strip() == DCM4CHEE_MWL_STATUS_PATIENT_MISSING
        or str(mapping.get("lastErrorType") or "").strip() == "patient_missing"
    ):
        error_text = (
            str(mapping.get("lastError") or "").strip()
            or "dcm4chee patient precondition is missing for this MWL order."
        )
        error_payload = {
            "lastSyncStatus": mapping.get("status") or "",
            "lastHttpStatus": mapping.get("lastHttpStatus"),
            "lastResponseBody": mapping.get("lastResponseBody") or "",
        }
        updated_attempt = store.update_dcm4chee_mwl_attempt_result(
            int(attempt["id"]),
            attempt_status=DCM4CHEE_MWL_STATUS_PATIENT_MISSING,
            http_status=mapping.get("lastHttpStatus"),
            response_body=mapping.get("lastResponseBody") or "",
            error_type="patient_missing",
            error_text=error_text,
        )
        updated_mapping = store.update_dcm4chee_mwl_verification_result(
            int(order["id"]),
            attempt_id=int(updated_attempt["id"]),
            verification_status=DCM4CHEE_MWL_VERIFICATION_FAILED,
            method=method,
            query_criteria=query_criteria,
            error_type="patient_missing",
            error_text=error_text,
            error_payload=error_payload,
        )
        return {"attempt": updated_attempt, "mapping": updated_mapping}
    if not diagnostics["valid"]:
        error_text = str(diagnostics.get("summary") or "dcm4chee profile is incomplete or invalid.")
        updated_attempt = store.update_dcm4chee_mwl_attempt_result(
            int(attempt["id"]),
            attempt_status=DCM4CHEE_MWL_STATUS_FAILED,
            error_type="mwl_profile_invalid",
            error_text=error_text,
            response_body=json.dumps(diagnostics, sort_keys=True),
        )
        updated_mapping = store.update_dcm4chee_mwl_verification_result(
            int(order["id"]),
            attempt_id=int(updated_attempt["id"]),
            verification_status=DCM4CHEE_MWL_VERIFICATION_FAILED,
            method=method,
            query_criteria=query_criteria,
            error_type="mwl_profile_invalid",
            error_text=error_text,
            error_payload=diagnostics,
        )
        return {"attempt": updated_attempt, "mapping": updated_mapping}

    try:
        status, response_body, actual_url = request_dcm4chee_mwl_verification(profile, query_criteria)
    except UpstreamDcm4cheeError as exc:
        error_type = classify_dcm4chee_mwl_verification_error(exc)
        verification_status = (
            DCM4CHEE_MWL_VERIFICATION_FAILED
            if error_type != "mwl_ambiguous"
            else DCM4CHEE_MWL_VERIFICATION_AMBIGUOUS
        )
        updated_attempt = store.update_dcm4chee_mwl_attempt_result(
            int(attempt["id"]),
            attempt_status=DCM4CHEE_MWL_STATUS_PATIENT_MISSING
            if error_type == "patient_missing"
            else DCM4CHEE_MWL_STATUS_FAILED,
            http_status=exc.http_status,
            response_body=exc.response_body,
            error_type=error_type,
            error_text=str(exc),
        )
        updated_mapping = store.update_dcm4chee_mwl_verification_result(
            int(order["id"]),
            attempt_id=int(updated_attempt["id"]),
            verification_status=verification_status,
            method=method,
            query_criteria=query_criteria,
            error_type=error_type,
            error_text=str(exc),
            error_payload={"responseBody": exc.response_body, "httpStatus": exc.http_status},
        )
        return {"attempt": updated_attempt, "mapping": updated_mapping}

    match_result = match_dcm4chee_mwl_items(store, mapping, response_body)
    attempt_status = (
        DCM4CHEE_MWL_STATUS_CREATED
        if match_result["status"] == DCM4CHEE_MWL_VERIFICATION_VERIFIED
        else DCM4CHEE_MWL_STATUS_FAILED
    )
    updated_attempt = store.update_dcm4chee_mwl_attempt_result(
        int(attempt["id"]),
        attempt_status=attempt_status,
        http_status=status,
        response_body=response_body,
        error_type=match_result["errorType"],
        error_text=match_result["error"],
    )
    updated_mapping = store.update_dcm4chee_mwl_verification_result(
        int(order["id"]),
        attempt_id=int(updated_attempt["id"]),
        verification_status=match_result["status"],
        method=method,
        query_criteria={**query_criteria, "requestUrl": actual_url},
        match_payload=match_result["match"],
        error_type=match_result["errorType"],
        error_text=match_result["error"],
        error_payload=match_result["errorPayload"],
    )
    return {"attempt": updated_attempt, "mapping": updated_mapping}
