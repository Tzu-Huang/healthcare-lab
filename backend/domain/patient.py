"""Framework-independent Patient validation, identifiers, and projections."""

from __future__ import annotations

import json
from datetime import datetime
from sqlite3 import Row
from typing import Any

from backend.domain.errors import SimulatorValidationError

PATIENT_CLASS_DEFAULT = "O"
PATIENT_MODES = {
    "hl7-v2": {"protocol": "HL7 v2.5.1", "message_type": "ADT^A04"},
    "fhir": {"protocol": "FHIR R4", "message_type": "Patient"},
    "gdt": {"protocol": "GDT 2.1", "message_type": "6301"},
    "dicom": {"protocol": "DICOM", "message_type": "Patient Module"},
}


def clean_text(value: Any, field_name: str, required: bool = False) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise SimulatorValidationError(f"Patient {field_name} is required.")
    return text


def normalize_sex(value: Any) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in {"M", "F", "O", "U"}:
        raise SimulatorValidationError("Patient sex must be M, F, O, or U.")
    return normalized


def normalize_dob(value: Any) -> str:
    digits = "".join(character for character in str(value or "").strip() if character.isdigit())
    if len(digits) != 8:
        raise SimulatorValidationError("Patient dob must be YYYYMMDD.")
    try:
        datetime.strptime(digits, "%Y%m%d")
    except ValueError as exc:
        raise SimulatorValidationError("Patient dob must be a valid YYYYMMDD date.") from exc
    return digits


def normalize_mode(payload: dict[str, Any]) -> str:
    mode = str(payload.get("mode", payload.get("protocolMode", "hl7-v2"))).strip().lower()
    normalized = {
        "hl7": "hl7-v2", "hl7v2": "hl7-v2", "hl7-v2.5.1": "hl7-v2",
        "hl7-v251": "hl7-v2", "fhir-r4": "fhir", "gdt-2.1": "gdt",
        "dicom-patient": "dicom",
    }.get(mode, mode)
    if normalized not in PATIENT_MODES:
        raise SimulatorValidationError("Patient mode must be HL7 v2, FHIR, GDT, or DICOM.")
    return normalized


def normalize_active(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value if value is not None else "true").strip().lower()
    if normalized in {"", "1", "true", "yes", "y", "on", "active"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", "inactive"}:
        return False
    raise SimulatorValidationError("Patient active must be true or false.")


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SimulatorValidationError("Patient payload must be a JSON object.")
    return {
        "mode": normalize_mode(payload),
        "mrn": clean_text(payload.get("mrn"), "mrn"),
        "first_name": clean_text(payload.get("firstName"), "firstName", required=True),
        "last_name": clean_text(payload.get("lastName"), "lastName", required=True),
        "middle_name": clean_text(payload.get("middleName"), "middleName"),
        "dob": normalize_dob(payload.get("dob")),
        "sex": normalize_sex(payload.get("sex")),
        "address": clean_text(payload.get("address"), "address"),
        "phone": clean_text(payload.get("phone"), "phone"),
        "email": clean_text(payload.get("email"), "email"),
        "fhir_active": normalize_active(payload.get("active", payload.get("fhirActive", True))),
        "address_line": clean_text(payload.get("addressLine"), "addressLine"),
        "address_city": clean_text(payload.get("addressCity"), "addressCity"),
        "address_state": clean_text(payload.get("addressState"), "addressState"),
        "address_postal_code": clean_text(payload.get("addressPostalCode"), "addressPostalCode"),
        "address_country": clean_text(payload.get("addressCountry"), "addressCountry"),
        "managing_organization_reference": clean_text(payload.get("managingOrganizationReference"), "managingOrganizationReference"),
        "managing_organization_display": clean_text(payload.get("managingOrganizationDisplay"), "managingOrganizationDisplay"),
        "visit_number": clean_text(payload.get("visitNumber"), "visitNumber"),
        "patient_class": clean_text(payload.get("patientClass", PATIENT_CLASS_DEFAULT), "patientClass") or PATIENT_CLASS_DEFAULT,
        "assigned_location": clean_text(payload.get("assignedLocation"), "assignedLocation"),
        "attending_provider": clean_text(payload.get("attendingProvider"), "attendingProvider"),
        "account_number": clean_text(payload.get("accountNumber"), "accountNumber"),
    }


def record_number(record_id: int) -> str:
    return f"PAT-{record_id:06d}"


def visit_number(record_id: int) -> str:
    return f"VISIT-{record_id:06d}"


def mrn(value: int) -> str:
    return f"MRN-{value:06d}"


def project(row: Row, *, fhir_record=None, dcm4chee_patient_sync=None, dcm4chee_results=None) -> dict[str, Any]:
    dcm4chee_results = dcm4chee_results or []
    patient = {
        "mrn": row["mrn"], "firstName": row["first_name"], "lastName": row["last_name"],
        "middleName": row["middle_name"], "dob": row["dob"], "sex": row["sex"],
        "address": row["address"], "phone": row["phone"], "email": row["email"],
        "active": bool(row["fhir_active"]), "addressLine": row["address_line"],
        "addressCity": row["address_city"], "addressState": row["address_state"],
        "addressPostalCode": row["address_postal_code"], "addressCountry": row["address_country"],
        "managingOrganizationReference": row["managing_organization_reference"],
        "managingOrganizationDisplay": row["managing_organization_display"],
    }
    fhir = None
    if fhir_record:
        fhir = {
            "recordId": fhir_record["id"],
            **{key: fhir_record[key] for key in (
                "localFhirRecordNumber", "resourceType", "identifier", "medplum", "sync", "localOnly"
            )},
        }
    return {
        "id": row["id"], "localPatientNumber": row["local_patient_number"],
        "protocolVersion": row["protocol_version"], "messageType": row["message_type"],
        "patient": patient,
        "summary": {"mrn": row["mrn"], "name": " ".join(part for part in (row["first_name"], row["middle_name"], row["last_name"]) if part), "dob": row["dob"], "sex": row["sex"], "visitNumber": row["visit_number"]},
        "visitNumber": row["visit_number"], "patientClass": row["patient_class"],
        "assignedLocation": row["assigned_location"], "attendingProvider": row["attending_provider"],
        "accountNumber": row["account_number"],
        "validation": {"status": row["validation_status"], "messages": json.loads(row["validation_messages_json"] or "[]")},
        "payload": row["payload_hl7"], "fhir": fhir,
        "dcm4chee": {**({"patient": dcm4chee_patient_sync} if dcm4chee_patient_sync else {}), "dicomResults": dcm4chee_results, "resultCount": len(dcm4chee_results)},
        "createdAt": row["created_at"], "updatedAt": row["updated_at"], "localOnly": True,
    }
