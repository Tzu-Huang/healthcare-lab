"""Order row and boundary presentation."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from backend.mappers.types import RowMapping


def project(row: RowMapping, *, fhir_records=None, dcm4chee_attempt=None,
            dcm4chee_mapping=None,
            dcm4chee_status_view: Callable[..., dict[str, Any]] | None = None) -> dict[str, Any]:
    fhir_records = fhir_records or {}
    dcm_view = dcm4chee_status_view(dcm4chee_attempt, dcm4chee_mapping) if dcm4chee_status_view and (dcm4chee_attempt or dcm4chee_mapping) else None
    return {
        "id": row["id"], "localOrderNumber": row["local_order_number"], "patientRecordId": row["patient_record_id"],
        "protocolVersion": row["protocol_version"], "messageType": row["message_type"], "status": row["order_status"],
        "patient": {"mrn": row["mrn"], "firstName": row["first_name"], "lastName": row["last_name"], "middleName": row["middle_name"], "dob": row["dob"], "sex": row["sex"]},
        "summary": {"mrn": row["mrn"], "name": " ".join(part for part in (row["first_name"], row["middle_name"], row["last_name"]) if part), "dob": row["dob"], "sex": row["sex"], "visitNumber": row["visit_id"], "visitId": row["visit_id"], "orderCode": row["order_code"], "orderText": row["order_code_text"]},
        "visitNumber": row["visit_id"], "visitId": row["visit_id"], "patientClass": row["patient_class"],
        "assignedLocation": row["assigned_location"], "accountNumber": row["account_number"],
        "placerOrderNumber": row["placer_order_number"], "fillerOrderNumber": row["filler_order_number"],
        "priority": row["priority"], "requestedAt": row["requested_at"], "orderingProvider": row["ordering_provider"],
        "clinicalIndication": row["clinical_indication"], "orderCode": row["order_code"], "orderCodeText": row["order_code_text"],
        "alternateCode": row["alternate_code"], "alternateCodeText": row["alternate_code_text"], "alternateCodeSystem": row["alternate_code_system"],
        "fhir": {"serviceRequest": fhir_records.get("ServiceRequest")} if row["protocol_version"] == "FHIR R4" else None,
        "dcm4chee": {"mwl": dcm_view} if row["protocol_version"] == "DICOM" or dcm_view else None,
        "validation": {"status": row["validation_status"], "messages": json.loads(row["validation_messages_json"] or "[]")},
        "payload": row["payload_hl7"],
        "ack": {"code": row["ack_code"], "controlId": row["ack_control_id"], "text": row["ack_text"], "payload": row["ack_payload"]},
        "transportError": row["transport_error"], "lastSentAt": row["last_sent_at"],
        "createdAt": row["created_at"], "updatedAt": row["updated_at"], "localOnly": True,
    }
