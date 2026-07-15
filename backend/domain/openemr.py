"""Framework-independent OpenEMR configuration defaults and parsing."""

from __future__ import annotations

import hashlib
import json
from typing import Any


OPENEMR_DEFAULT_ALLOWED_PROCEDURE_CODES = ("1001",)


def parse_openemr_allowed_procedure_codes(value: Any) -> tuple[str, ...]:
    if value is None:
        return OPENEMR_DEFAULT_ALLOWED_PROCEDURE_CODES
    if isinstance(value, str):
        codes = [item.strip() for item in value.replace(";", ",").split(",")]
    else:
        codes = [str(item).strip() for item in value]
    return tuple(code for code in codes if code)


def normalize_openemr_dob(value: Any) -> str:
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 else text


def normalize_openemr_gender(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"m", "male", "man"}:
        return "M"
    if normalized in {"f", "female", "woman"}:
        return "F"
    if normalized in {"o", "other"}:
        return "O"
    return "U" if normalized else ""


def openemr_provider_name(row: dict[str, Any]) -> str:
    full_name = " ".join(
        part for part in (
            str(row.get("provider_fname") or "").strip(),
            str(row.get("provider_lname") or "").strip(),
        ) if part
    )
    return full_name or str(row.get("provider_username") or "").strip()


def openemr_row_source_key(row: dict[str, Any]) -> tuple[int, int]:
    return int(row["procedure_order_id"]), int(row.get("procedure_order_seq") or 1)


def map_openemr_procedure_order_to_gdt_order(row: dict[str, Any]) -> dict[str, Any]:
    order_id, sequence = openemr_row_source_key(row)
    order_number = f"OE-PO-{order_id}-{sequence}"
    mrn = str(row.get("pubpid") or row.get("pid") or row.get("patient_id") or "").strip()
    return {
        "source": "openemr", "sourceProcedureOrderId": order_id,
        "sourceProcedureOrderSeq": sequence,
        "sourceFingerprint": hashlib.sha256(
            json.dumps(row, default=str, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "orderNumber": order_number, "placerOrderNumber": order_number,
        "fillerOrderNumber": "",
        "correlationId": f"openemr-procedure-order:{order_id}:{sequence}",
        "patientMrn": mrn,
        "patient": {
            "mrn": mrn, "first_name": str(row.get("patient_fname") or "").strip(),
            "last_name": str(row.get("patient_lname") or "").strip(), "middle_name": "",
            "dob": normalize_openemr_dob(row.get("patient_dob")),
            "gender": normalize_openemr_gender(row.get("patient_sex")),
        },
        "encounterId": str(row.get("encounter_id") or "").strip(),
        "examCode": str(row.get("procedure_code") or "").strip(),
        "examDescription": str(row.get("procedure_name") or "").strip(),
        "orderingProvider": openemr_provider_name(row),
        "orderDate": str(row.get("date_ordered") or "").strip(),
        "encounterDate": str(row.get("encounter_date") or "").strip(),
        "encounterReason": str(row.get("encounter_reason") or "").strip(),
        "status": "QUEUED_FOR_GDT",
    }
