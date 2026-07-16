"""GDT workflow row and boundary presentation."""

from __future__ import annotations

import json
from typing import Any

from backend.mappers.types import RowMapping


def json_value(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return fallback


def patient_snapshot(patient: dict[str, Any], gdt_patient_number: str) -> dict[str, Any]:
    demographics = patient.get("patient") if isinstance(patient.get("patient"), dict) else patient
    summary = patient.get("summary") if isinstance(patient.get("summary"), dict) else {}
    return {
        "patientRecordId": patient["id"], "mrn": demographics.get("mrn", summary.get("mrn", "")),
        "gdtPatientNumber": gdt_patient_number, "firstName": demographics.get("firstName", ""),
        "middleName": demographics.get("middleName", ""), "lastName": demographics.get("lastName", ""),
        "dob": demographics.get("dob", summary.get("dob", "")),
        "sex": demographics.get("sex", summary.get("sex", "")),
        "visitNumber": patient.get("visitNumber", summary.get("visitNumber", "")),
    }


def attachment_filename(url: str, path: str = "") -> str:
    source = path or url
    return source.rstrip("/").replace("\\", "/").split("/")[-1] if source else ""


def project_message(row: RowMapping) -> dict[str, Any]:
    return {"id": row["id"], "orderRecordId": row["order_record_id"],
            "patientContextId": row["patient_context_id"], "direction": row["direction"],
            "messageType": row["message_type"], "rawGdtText": row["raw_gdt_text"],
            "parsedFields": json_value(row["parsed_fields_json"], {}),
            "canonical": json_value(row["canonical_json"], {}), "parseStatus": row["parse_status"],
            "matchStatus": row["match_status"], "error": row["error_text"],
            "generatedAt": row["generated_at"], "receivedAt": row["received_at"],
            "createdAt": row["created_at"], "updatedAt": row["updated_at"]}


def project_attachment(row: RowMapping) -> dict[str, Any]:
    return {"id": row["id"], "orderRecordId": row["order_record_id"],
            "messageRecordId": row["message_record_id"], "role": row["role"], "url": row["url"],
            "path": row["path"], "reference": row["reference"], "contentType": row["content_type"],
            "description": row["description"], "sourceFile": row["source_file"], "status": row["status"],
            "details": json_value(row["details_json"], {}), "filename": row["filename"],
            "checksum": row["checksum"], "createdAt": row["created_at"], "updatedAt": row["updated_at"]}


def project_event(row: RowMapping) -> dict[str, Any]:
    return {"id": row["id"], "orderRecordId": row["order_record_id"],
            "patientContextId": row["patient_context_id"], "messageRecordId": row["message_record_id"],
            "attachmentRecordId": row["attachment_record_id"], "eventType": row["event_type"],
            "actor": row["actor"], "details": json_value(row["details_json"], {}),
            "createdAt": row["created_at"]}
