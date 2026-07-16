"""Pure GDT workflow identifiers and persistence preparation."""

from __future__ import annotations

from typing import Any

from backend.domain.gdt_protocol import GdtAdapterResult


GDT_PATIENT_SEX_CODES = {"M": "1", "F": "2"}


def order_number(record_id: int) -> str:
    return f"GDT-ORD-{record_id:06d}"


def patient_number(patient_record_id: int) -> str:
    return f"GDT-PAT-{patient_record_id:06d}"


def birth_date(dob: str) -> str:
    return f"{dob[6:]}{dob[4:6]}{dob[:4]}"


def adapter_values(
    result: GdtAdapterResult | dict[str, Any],
) -> tuple[str, dict[str, list[str]], dict[str, Any]]:
    if isinstance(result, GdtAdapterResult) or all(
        hasattr(result, name) for name in ("raw_gdt_text", "parsed_fields", "canonical")
    ):
        return result.raw_gdt_text, result.parsed_fields, result.canonical
    return (
        str(result.get("rawGdtText", "")),
        dict(result.get("parsedFields") or {}),
        dict(result.get("canonical") or {}),
    )


def prepare_order_payload(
    *, demographics: dict[str, Any], summary: dict[str, Any],
    gdt_patient_number: str, local_order_number: str,
    requested_at: str, ordering_provider: str, clinical_indication: str,
    patient_snapshot: dict[str, Any], order_snapshot: dict[str, Any], test_label: str,
) -> dict[str, Any]:
    dob = demographics.get("dob", summary.get("dob", ""))
    sex = demographics.get("sex", summary.get("sex", ""))
    return {
        "gdtPatientNumber": gdt_patient_number,
        "lastName": demographics.get("lastName", ""),
        "firstName": demographics.get("firstName", ""),
        "birthDate": birth_date(dob),
        "localGdtOrderNumber": local_order_number,
        "sex": GDT_PATIENT_SEX_CODES.get(sex, ""),
        "requestedAt": requested_at,
        "orderingProvider": ordering_provider,
        "clinicalIndication": clinical_indication,
        "patient": patient_snapshot,
        "order": order_snapshot,
        "testLabel": test_label,
    }
