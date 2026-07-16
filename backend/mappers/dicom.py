"""DICOM and dcm4chee row and boundary presentation."""

from __future__ import annotations

from typing import Any

from backend.domain.statuses import (
    DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
    DCM4CHEE_PATIENT_SYNC_STATUS_PENDING,
    DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED,
)
from backend.mappers.types import RowMapping


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
