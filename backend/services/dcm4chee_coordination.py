"""Explicit coordinator for dcm4chee fixture, evidence, and simulated AP workflows."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.domain.errors import SimulatorValidationError
from backend.domain.statuses import (
    DCM4CHEE_MWL_STATUS_PENDING,
    DCM4CHEE_MWL_VERIFICATION_NOT_VERIFIED,
    DCM4CHEE_RESULT_STATUS_NO_RESULT,
)

DCM4CHEE_DEFAULT_UID_ROOT = "1.2.826.0.1.3680043.10.543"
DCM4CHEE_ORDER_PROTOCOL_VERSION = "DICOM"
DCM4CHEE_RESULT_SOURCE_SIMULATED_AP = "simulated_ap_return"
ORDER_DEFAULT_CODE = "ECG12"
ORDER_DEFAULT_TEXT = "12 Lead ECG"
ORDER_DEFAULT_PROVIDER = "1001^WANG^AMY"


class Dcm4cheeMwlAttemptCoordinator:
    """Prepare protocol payloads before handing persistence-ready values to MWL storage."""

    def __init__(
        self,
        *,
        order_loader: Callable[[int], dict[str, Any]],
        payload_builder: Callable[..., dict[str, Any]],
        attempt_creator: Callable[..., dict[str, Any]],
    ) -> None:
        self._get_order = order_loader
        self._build_payload = payload_builder
        self._create_attempt = attempt_creator

    def create_dcm4chee_mwl_attempt(
        self,
        order_record_id: int,
        profile: dict[str, Any],
        *,
        uid_root: str = DCM4CHEE_DEFAULT_UID_ROOT,
        request_url: str = "",
        request_payload: dict[str, Any] | None = None,
        attempt_status: str = DCM4CHEE_MWL_STATUS_PENDING,
        error_type: str = "",
        error_text: str = "",
        http_status: int | None = None,
        response_body: str = "",
        operation_type: str = "create",
        mapping_id: int | None = None,
    ) -> dict[str, Any]:
        payload = request_payload or self._build_payload(
            self._get_order(order_record_id), profile, uid_root=uid_root
        )
        return self._create_attempt(
            order_record_id,
            profile,
            uid_root=uid_root,
            request_url=request_url,
            request_payload=payload,
            attempt_status=attempt_status,
            error_type=error_type,
            error_text=error_text,
            http_status=http_status,
            response_body=response_body,
            operation_type=operation_type,
            mapping_id=mapping_id,
        )


class Dcm4cheeWorkflowCoordinator:
    def __init__(
        self, *, patient_create, patient_get, order_create, order_get,
        patient_sync_get, mwl_get, mwl_upsert, result_list, result_begin,
        result_upsert, result_complete, latest_simulated_generation,
        mwl_payload_builder, timestamp_factory,
    ) -> None:
        self._create_patient = patient_create
        self._get_patient = patient_get
        self._create_order = order_create
        self._get_order = order_get
        self._get_patient_sync = patient_sync_get
        self._get_mwl = mwl_get
        self._upsert_mwl = mwl_upsert
        self._list_results = result_list
        self._begin_results = result_begin
        self._upsert_result = result_upsert
        self._complete_results = result_complete
        self._latest_simulated_generation = latest_simulated_generation
        self._build_mwl_payload = mwl_payload_builder
        self._timestamp = timestamp_factory

    @staticmethod
    def dcm4chee_e2e_demo_patient_payload() -> dict[str, Any]:
        return {
            "mode": "dicom",
            "mrn": "MRN-DCM-E2E-001",
            "firstName": "Avery",
            "middleName": "Lee",
            "lastName": "Morgan",
            "dob": "19850412",
            "sex": "F",
            "patientClass": "O",
            "assignedLocation": "CARDIOLOGY^ROOM1",
            "visitNumber": "VISIT-DCM-E2E-001",
        }

    @staticmethod
    def dcm4chee_e2e_demo_order_payload(patient_record_id: int) -> dict[str, Any]:
        return {
            "mode": "dicom",
            "patientRecordId": int(patient_record_id),
            "requestedAt": "20260713103000",
            "orderingProvider": ORDER_DEFAULT_PROVIDER,
            "orderCode": ORDER_DEFAULT_CODE,
            "orderCodeText": ORDER_DEFAULT_TEXT,
            "clinicalIndication": "ZAC-42 production-like dcm4chee E2E verification fixture",
        }

    def create_dcm4chee_e2e_demo_fixture(
        self,
        profile: dict[str, Any],
        *,
        uid_root: Any = DCM4CHEE_DEFAULT_UID_ROOT,
    ) -> dict[str, Any]:
        patient = self._create_patient(self.dcm4chee_e2e_demo_patient_payload())
        order = self._create_order(self.dcm4chee_e2e_demo_order_payload(int(patient["id"])))
        payload = self._build_mwl_payload(order, profile, uid_root=uid_root)
        mapping = self._upsert_mwl(
            int(order["id"]),
            profile,
            uid_root=uid_root,
            request_payload=payload,
            sync_status=DCM4CHEE_MWL_STATUS_PENDING,
        )
        patient = self._get_patient(int(patient["id"]))
        order = self._get_order(int(order["id"]))
        return {
            "patient": patient,
            "order": order,
            "mapping": mapping,
            "evidence": self.dcm4chee_e2e_evidence_for_order(int(order["id"]), profile),
        }

    def dcm4chee_e2e_evidence_for_order(self, order_record_id: int, profile: dict[str, Any]) -> dict[str, Any]:
        order = self._get_order(int(order_record_id))
        patient = self._get_patient(int(order["patientRecordId"]))
        mapping = self._get_mwl(int(order_record_id)) or {}
        patient_sync = self._get_patient_sync(int(patient["id"]), profile)
        results = self._list_results(int(patient["id"]))
        order_results = [
            item for item in results
            if str(item.get("orderRecordId") or "") == str(order_record_id)
            or (mapping.get("studyInstanceUid") and item.get("studyInstanceUid") == mapping.get("studyInstanceUid"))
            or (mapping.get("accessionNumber") and item.get("accessionNumber") == mapping.get("accessionNumber"))
        ]
        dimse = profile.get("dimse") if isinstance(profile.get("dimse"), dict) else {}
        mwl = profile.get("mwl") if isinstance(profile.get("mwl"), dict) else {}
        dicomweb = profile.get("dicomweb") if isinstance(profile.get("dicomweb"), dict) else {}
        verification = mapping.get("verification") if isinstance(mapping.get("verification"), dict) else {}
        return {
            "mode": "dcm4chee-production-like-e2e",
            "patientRecordId": patient["id"],
            "orderRecordId": order["id"],
            "profileName": profile.get("profileName", ""),
            "identifiers": {
                "patientId": mapping.get("patientId") or (patient.get("summary") or {}).get("mrn", ""),
                "issuerOfPatientId": mapping.get("issuerOfPatientId") or profile.get("profileName", ""),
                "accessionNumber": mapping.get("accessionNumber", ""),
                "requestedProcedureId": mapping.get("requestedProcedureId", ""),
                "scheduledProcedureStepId": mapping.get("scheduledProcedureStepId", ""),
                "studyInstanceUid": mapping.get("studyInstanceUid", ""),
                "seriesInstanceUid": next((item.get("seriesInstanceUid") for item in order_results if item.get("seriesInstanceUid")), ""),
                "sopInstanceUid": next((item.get("sopInstanceUid") for item in order_results if item.get("sopInstanceUid")), ""),
            },
            "aeTitles": {
                "archiveCalledAETitle": dimse.get("calledAETitle", ""),
                "healthcareLabCallingAETitle": dimse.get("callingAETitle", ""),
                "mwlAETitle": mwl.get("aeTitle", ""),
                "scheduledStationAETitle": mapping.get("scheduledStationAETitle") or mwl.get("defaultScheduledStationAETitle", ""),
            },
            "endpoints": {
                "mwlRestUrl": f"{str(dicomweb.get('baseUrl') or '').rstrip('/')}/mwlitems" if dicomweb.get("baseUrl") else "",
                "qidoRsUrl": dicomweb.get("qidoRsUrl", ""),
                "wadoRsUrl": dicomweb.get("wadoRsUrl", ""),
                "webUiUrl": profile.get("webUiUrl", ""),
            },
            "steps": {
                "patientPrecondition": (patient_sync or {}).get("status") or "not_synced",
                "mwlCreate": mapping.get("status") or "not_created",
                "mwlQueryable": verification.get("status") or DCM4CHEE_MWL_VERIFICATION_NOT_VERIFIED,
                "apReturn": "recorded" if order_results else "not_recorded",
                "resultReconciliation": next((item.get("reconciliationStatus") for item in order_results if item.get("reconciliationStatus")), DCM4CHEE_RESULT_STATUS_NO_RESULT),
                "uiVisibleResult": bool(order_results),
            },
            "results": order_results,
            "generatedAt": self._timestamp(),
        }
    def create_simulated_dcm4chee_ap_return(
        self,
        order_record_id: int,
        profile: dict[str, Any],
        *,
        result_type: str = "both",
        artifact_url: str = "",
        artifact_path: str = "",
    ) -> dict[str, Any]:
        order = self._get_order(int(order_record_id))
        if order.get("protocolVersion") != DCM4CHEE_ORDER_PROTOCOL_VERSION:
            raise SimulatorValidationError("Order record is not DICOM MWL mode.")
        mapping = self._get_mwl(int(order_record_id))
        if not mapping:
            payload = self._build_mwl_payload(order, profile)
            mapping = self._upsert_mwl(
                int(order_record_id),
                profile,
                request_payload=payload,
                sync_status=DCM4CHEE_MWL_STATUS_PENDING,
            )
        result_type = str(result_type or "both").strip().lower()
        if result_type not in {"both", "pdf", "dicom"}:
            raise SimulatorValidationError("Simulated AP return type must be pdf, dicom, or both.")
        generation = (
            self._latest_simulated_generation(int(order_record_id))
            if result_type in {"pdf", "dicom"}
            else ""
        ) or f"simulated-ap-return-{self._timestamp()}"
        self._begin_results(
            int(order["patientRecordId"]),
            generation,
            promote_existing=True,
        )
        base_metadata = {
            "study_instance_uid": str(mapping.get("studyInstanceUid") or ""),
            "accession_number": str(mapping.get("accessionNumber") or ""),
            "patient_id": str(mapping.get("patientId") or ""),
            "issuer_of_patient_id": str(mapping.get("issuerOfPatientId") or ""),
            "requested_procedure_id": str(mapping.get("requestedProcedureId") or ""),
            "scheduled_procedure_step_id": str(mapping.get("scheduledProcedureStepId") or ""),
            "modality": "ECG",
            "study_datetime": "20260713104500",
        }
        created: list[dict[str, Any]] = []
        if result_type in {"both", "dicom"}:
            metadata = {
                **base_metadata,
                "series_instance_uid": f"{base_metadata['study_instance_uid']}.1",
                "sop_instance_uid": f"{base_metadata['study_instance_uid']}.1.1",
                "series_datetime": "20260713104600",
                "instance_datetime": "20260713104630",
            }
            created.append(
                self._upsert_result(
                    metadata,
                    profile,
                    patient_record_id=int(order["patientRecordId"]),
                    query_url="simulated://ap-return/dicom",
                    query_payload={"source": DCM4CHEE_RESULT_SOURCE_SIMULATED_AP, "type": "dicom"},
                    raw_metadata={"source": DCM4CHEE_RESULT_SOURCE_SIMULATED_AP, "type": "dicom", "metadata": metadata},
                    refresh_generation=generation,
                )
            )
        if result_type in {"both", "pdf"}:
            url = artifact_url or "http://localhost/reports/dcm4chee-simulated-ecg-report.pdf"
            path = artifact_path or "reports/dcm4chee-simulated-ecg-report.pdf"
            metadata = {
                **base_metadata,
                "series_instance_uid": f"{base_metadata['study_instance_uid']}.9001",
                "sop_instance_uid": f"{base_metadata['study_instance_uid']}.9001.1",
                "modality": "DOC",
                "series_datetime": "20260713104700",
                "instance_datetime": "20260713104730",
            }
            created.append(
                self._upsert_result(
                    metadata,
                    profile,
                    patient_record_id=int(order["patientRecordId"]),
                    query_url="simulated://ap-return/pdf",
                    query_payload={"source": DCM4CHEE_RESULT_SOURCE_SIMULATED_AP, "type": "pdf"},
                    raw_metadata={
                        "source": DCM4CHEE_RESULT_SOURCE_SIMULATED_AP,
                        "type": "pdf",
                        "metadata": metadata,
                        "artifact": {
                            "label": "Simulated AP ECG PDF",
                            "mediaType": "application/pdf",
                            "url": url,
                            "path": path,
                            "role": "ap-return-report",
                        },
                    },
                    refresh_generation=generation,
                )
            )
        self._complete_results(int(order["patientRecordId"]), generation)
        return {
            "items": created,
            "evidence": self.dcm4chee_e2e_evidence_for_order(int(order_record_id), profile),
            "refreshGeneration": generation,
        }
