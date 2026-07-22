"""Patient row and boundary presentation."""

from __future__ import annotations

import json
from typing import Any

from backend.mappers.types import RowMapping


def _dcm4chee_result_count(results: list[dict[str, Any]]) -> int:
    """Count clinical results by Study, not by Study/Series/Instance rows."""
    keys = {
        (
            f"simulated:{item.get('resultKey') or item.get('id')}"
            if item.get("source") == "simulated_ap_return"
            else str(item.get("studyInstanceUid") or item.get("accessionNumber") or "").strip()
        )
        for item in results
    }
    return len(keys - {""})


def project(
    row: RowMapping,
    *,
    fhir_record: RowMapping | None = None,
    dcm4chee_patient_sync: dict[str, Any] | None = None,
    dcm4chee_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
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
        "dcm4chee": {**({"patient": dcm4chee_patient_sync} if dcm4chee_patient_sync else {}), "dicomResults": dcm4chee_results, "resultCount": _dcm4chee_result_count(dcm4chee_results)},
        "createdAt": row["created_at"], "updatedAt": row["updated_at"], "localOnly": True,
    }
