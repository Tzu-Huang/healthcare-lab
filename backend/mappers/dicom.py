"""DICOM and dcm4chee row and boundary presentation."""

from __future__ import annotations

import json
from typing import Any

from backend.domain.statuses import (
    DCM4CHEE_MWL_OPERATION_CREATE,
    DCM4CHEE_MWL_VERIFICATION_NOT_VERIFIED,
    DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
    DCM4CHEE_PATIENT_SYNC_STATUS_PENDING,
    DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED,
)
from backend.mappers.types import RowMapping


def _json_value(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return fallback


def project_mwl_attempt(row: RowMapping) -> dict[str, Any]:
    return {
        "id": row["id"],
        "mappingId": row["mapping_id"] if "mapping_id" in row.keys() else None,
        "operationType": row["operation_type"] if "operation_type" in row.keys() else DCM4CHEE_MWL_OPERATION_CREATE,
        "orderRecordId": row["order_record_id"],
        "profileName": row["profile_name"],
        "serverIdentity": row["server_identity"],
        "mwlAETitle": row["mwl_ae_title"],
        "scheduledStationAETitle": row["scheduled_station_ae_title"],
        "localDcm4cheeOrderNumber": row["local_dcm4chee_order_number"],
        "accessionNumber": row["accession_number"],
        "requestedProcedureId": row["requested_procedure_id"],
        "scheduledProcedureStepId": row["scheduled_procedure_step_id"],
        "studyInstanceUid": row["study_instance_uid"],
        "uidRoot": row["uid_root"],
        "requestUrl": row["request_url"],
        "requestPayload": _json_value(row["request_payload_json"], {}),
        "httpStatus": row["http_status"],
        "responseBody": row["response_body"],
        "status": row["attempt_status"],
        "errorType": row["error_type"],
        "error": row["error_text"],
        "attemptedAt": row["attempted_at"],
        "completedAt": row["completed_at"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def project_mwl_mapping(row: RowMapping) -> dict[str, Any]:
    return {
        "id": row["id"],
        "orderRecordId": row["order_record_id"],
        "profileName": row["profile_name"],
        "serverIdentity": row["server_identity"],
        "mwlAETitle": row["mwl_ae_title"],
        "scheduledStationAETitle": row["scheduled_station_ae_title"],
        "localDcm4cheeOrderNumber": row["local_dcm4chee_order_number"],
        "patientId": row["patient_id"],
        "issuerOfPatientId": row["issuer_of_patient_id"],
        "accessionNumber": row["accession_number"],
        "requestedProcedureId": row["requested_procedure_id"],
        "scheduledProcedureStepId": row["scheduled_procedure_step_id"],
        "studyInstanceUid": row["study_instance_uid"],
        "worklistLabel": row["worklist_label"],
        "uidRoot": row["uid_root"],
        "status": row["sync_status"],
        "lastSyncAt": row["last_sync_at"],
        "retryCount": row["retry_count"],
        "lastAttemptId": row["last_attempt_id"],
        "lastHttpStatus": row["last_http_status"],
        "lastResponseBody": row["last_response_body"],
        "lastErrorType": row["last_error_type"],
        "lastError": row["last_error_text"],
        "lastErrorPayload": _json_value(row["last_error_payload_json"], {}),
        "latestRequestPayload": _json_value(row["latest_request_payload_json"], {}),
        "latestReadbackPayload": _json_value(row["latest_readback_payload_json"], {}),
        "verification": {
            "status": row["verification_status"] if "verification_status" in row.keys() else DCM4CHEE_MWL_VERIFICATION_NOT_VERIFIED,
            "lastVerifiedAt": row["last_verification_at"] if "last_verification_at" in row.keys() else "",
            "method": row["last_verification_method"] if "last_verification_method" in row.keys() else "",
            "attemptId": row["last_verification_attempt_id"] if "last_verification_attempt_id" in row.keys() else None,
            "query": _json_value(row["last_verification_query_json"] if "last_verification_query_json" in row.keys() else "{}", {}),
            "match": _json_value(row["last_verification_match_json"] if "last_verification_match_json" in row.keys() else "{}", {}),
            "errorType": row["last_verification_error_type"] if "last_verification_error_type" in row.keys() else "",
            "error": row["last_verification_error_text"] if "last_verification_error_text" in row.keys() else "",
            "errorPayload": _json_value(row["last_verification_error_payload_json"] if "last_verification_error_payload_json" in row.keys() else "{}", {}),
        },
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def project_patient_sync(row: RowMapping) -> dict[str, Any]:
    status = str(row["sync_status"] or "")
    retryable = status in {DCM4CHEE_PATIENT_SYNC_STATUS_PENDING, DCM4CHEE_PATIENT_SYNC_STATUS_FAILED}
    return {
        "id": row["id"], "patientRecordId": row["patient_record_id"], "profileName": row["profile_name"],
        "serverIdentity": row["server_identity"], "patientId": row["patient_id"],
        "issuerOfPatientId": row["issuer_of_patient_id"], "hl7Host": row["hl7_host"],
        "hl7Port": row["hl7_port"], "receivingApplication": row["receiving_application"],
        "receivingFacility": row["receiving_facility"], "status": status,
        "displayStatus": "Synced" if status == DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED else status,
        "retryable": retryable, "retryCount": row["retry_count"], "lastAttemptId": row["last_attempt_id"],
        "ack": {"code": row["last_ack_code"], "controlId": row["last_ack_control_id"], "text": row["last_ack_text"]},
        "lastResponsePayload": row["last_response_payload"], "lastErrorType": row["last_error_type"],
        "lastError": row["last_error_text"], "lastSyncAt": row["last_sync_at"],
        "createdAt": row["created_at"], "updatedAt": row["updated_at"],
    }


def project_patient_sync_attempt(row: RowMapping) -> dict[str, Any]:
    return {
        "id": row["id"], "patientSyncId": row["patient_sync_id"], "operationType": row["operation_type"],
        "patientRecordId": row["patient_record_id"], "profileName": row["profile_name"],
        "serverIdentity": row["server_identity"], "patientId": row["patient_id"],
        "issuerOfPatientId": row["issuer_of_patient_id"], "requestUrl": row["request_url"],
        "requestPayload": row["request_payload"], "responsePayload": row["response_payload"],
        "ack": {"code": row["ack_code"], "controlId": row["ack_control_id"], "text": row["ack_text"]},
        "status": row["attempt_status"], "errorType": row["error_type"], "error": row["error_text"],
        "attemptedAt": row["attempted_at"], "completedAt": row["completed_at"],
        "createdAt": row["created_at"], "updatedAt": row["updated_at"],
    }
