"""Framework-independent generic Order validation, identifiers, and projections."""

from __future__ import annotations

import json
from datetime import datetime
from sqlite3 import Row
from typing import Any, Callable

from backend.domain.errors import SimulatorValidationError

ALLOWED_PRIORITIES = ("R", "S", "A")
DEFAULT_CODE = "ECG12"
DEFAULT_TEXT = "12 Lead ECG"
DEFAULT_ALT_CODE = "93000"
DEFAULT_ALT_TEXT = "Electrocardiogram, routine ECG with at least 12 leads"
DEFAULT_ALT_SYSTEM = "C4"
DEFAULT_PROVIDER = "1001^WANG^AMY"


def clean_text(value: Any, field_name: str, required: bool = False) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise SimulatorValidationError(f"Order {field_name} is required.")
    return text


def normalize_priority(value: Any) -> str:
    normalized = str(value or "R").strip().upper() or "R"
    if normalized not in ALLOWED_PRIORITIES:
        raise SimulatorValidationError(f"Order priority must be one of: {', '.join(ALLOWED_PRIORITIES)}.")
    return normalized


def normalize_requested_at(value: Any, *, default_factory: Callable[[], str]) -> str:
    raw = str(value or "").strip()
    if not raw:
        return default_factory()
    digits = "".join(character for character in raw if character.isdigit())
    if len(digits) not in {8, 12, 14}:
        raise SimulatorValidationError("Order requested time must be YYYYMMDD, YYYYMMDDHHMM, or YYYYMMDDHHMMSS.")
    try:
        datetime.strptime(digits[:8], "%Y%m%d")
        if len(digits) >= 12:
            datetime.strptime(digits[:12], "%Y%m%d%H%M")
        if len(digits) == 14:
            datetime.strptime(digits, "%Y%m%d%H%M%S")
    except ValueError as exc:
        raise SimulatorValidationError("Order requested time is not a valid HL7 timestamp.") from exc
    return digits


def _current_hl7_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def validate_payload(
    payload: dict[str, Any], *, timestamp_factory: Callable[[], str] | None = None
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SimulatorValidationError("Order payload must be a JSON object.")
    try:
        patient_record_id = int(payload.get("patientRecordId"))
    except (TypeError, ValueError) as exc:
        raise SimulatorValidationError("Order patientRecordId is required.") from exc
    return {
        "patient_record_id": patient_record_id,
        "priority": normalize_priority(payload.get("priority")),
        "requested_at": normalize_requested_at(
            payload.get("requestedAt"), default_factory=timestamp_factory or _current_hl7_timestamp
        ),
        "ordering_provider": clean_text(payload.get("orderingProvider", DEFAULT_PROVIDER), "orderingProvider") or DEFAULT_PROVIDER,
        "clinical_indication": clean_text(payload.get("clinicalIndication"), "clinicalIndication"),
        "order_code": clean_text(payload.get("orderCode", DEFAULT_CODE), "orderCode") or DEFAULT_CODE,
        "order_code_text": clean_text(payload.get("orderCodeText", DEFAULT_TEXT), "orderCodeText") or DEFAULT_TEXT,
        "alternate_code": clean_text(payload.get("alternateCode", DEFAULT_ALT_CODE), "alternateCode") or DEFAULT_ALT_CODE,
        "alternate_code_text": clean_text(payload.get("alternateCodeText", DEFAULT_ALT_TEXT), "alternateCodeText") or DEFAULT_ALT_TEXT,
        "alternate_code_system": clean_text(payload.get("alternateCodeSystem", DEFAULT_ALT_SYSTEM), "alternateCodeSystem") or DEFAULT_ALT_SYSTEM,
    }


def record_number(record_id: int) -> str:
    return f"ORD-{record_id:06d}"


def visit_id(record_id: int) -> str:
    return f"VISIT-ORD-{record_id:06d}"


def account_number(record_id: int) -> str:
    return f"ACC-ORD-{record_id:06d}"


def project(row: Row, *, fhir_records=None, dcm4chee_attempt=None, dcm4chee_mapping=None,
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
