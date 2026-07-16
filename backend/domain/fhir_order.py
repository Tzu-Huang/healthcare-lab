"""Pure validation and normalization rules for local FHIR orders."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

from backend.domain.errors import SimulatorValidationError

DEFAULT_CODE = "ECG12"
DEFAULT_TEXT = "12 Lead ECG"
DEFAULT_ALT_CODE = "93000"
DEFAULT_ALT_TEXT = "Electrocardiogram, routine ECG with at least 12 leads"
DEFAULT_ALT_SYSTEM = "C4"
DEFAULT_PROVIDER = "1001^WANG^AMY"
DEFAULT_STATUS = "active"
DEFAULT_INTENT = "order"
DEFAULT_PRIORITY = "routine"


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def list_values(value: Any) -> list[str]:
    if value is None:
        return []
    raw_items = value if isinstance(value, list | tuple) else str(value).replace(",", "\n").splitlines()
    return [str(item or "").strip() for item in raw_items if str(item or "").strip()]


def reference_item(value: str, field_name: str) -> dict[str, str]:
    text = value.strip()
    if not text:
        return {}
    if "/" not in text:
        raise SimulatorValidationError(
            f"FHIR Order {field_name} must be a FHIR reference like Resource/id."
        )
    return {"reference": text}


def reference_list(value: Any, field_name: str) -> list[dict[str, str]]:
    return [item for raw in list_values(value) if (item := reference_item(raw, field_name))]


def codeable_concept(*, text: Any = "", code: Any = "", system: Any = "", display: Any = "") -> dict[str, Any]:
    concept: dict[str, Any] = {}
    text_value, code_value = clean_text(text), clean_text(code)
    system_value, display_value = clean_text(system), clean_text(display)
    if text_value:
        concept["text"] = text_value
    if code_value or system_value or display_value:
        coding = {key: value for key, value in {
            "system": system_value, "code": code_value, "display": display_value,
        }.items() if value}
        concept["coding"] = [coding]
        if not concept.get("text"):
            concept["text"] = display_value or code_value
    return concept


def normalize_datetime(value: Any, fallback: str = "") -> str:
    text = clean_text(value)
    if not text:
        return fallback
    if "T" in text:
        match = re.match(r"^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::(\d{2})(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?$", text)
        if not match:
            return text
        date_part, hour, minute, second, fraction, offset = match.groups()
        normalized = f"{date_part}T{hour}:{minute}:{second or '00'}{fraction or ''}"
        if offset:
            if offset != "Z" and ":" not in offset:
                offset = f"{offset[:3]}:{offset[3:]}"
            return f"{normalized}{offset}"
        local_offset = datetime.now().astimezone().strftime("%z")
        return f"{normalized}{local_offset[:3]}:{local_offset[3:]}"
    digits = "".join(character for character in text if character.isdigit())
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    if len(digits) >= 12:
        base = f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}T{digits[8:10]}:{digits[10:12]}"
        base += f":{digits[12:14]}" if len(digits) >= 14 else ":00"
        local_offset = datetime.now().astimezone().strftime("%z")
        return f"{base}{local_offset[:3]}:{local_offset[3:]}"
    return text


def storage_timestamp(value: Any, fallback_factory: Callable[[], str]) -> str:
    digits = "".join(character for character in clean_text(value) if character.isdigit())
    if len(digits) >= 14:
        return digits[:14]
    if len(digits) >= 12:
        return digits[:12]
    if len(digits) >= 8:
        return digits[:8]
    return fallback_factory()


def storage_priority(value: Any) -> str:
    return {"routine": "R", "stat": "S", "asap": "A", "urgent": "A"}.get(
        clean_text(value or DEFAULT_PRIORITY).lower(), "R"
    )


def validate_payload(
    payload: dict[str, Any], *, timestamp_factory: Callable[[], str],
    storage_timestamp_factory: Callable[[], str],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SimulatorValidationError("FHIR Order payload must be a JSON object.")
    try:
        patient_record_id = int(payload.get("patientRecordId"))
    except (TypeError, ValueError) as exc:
        raise SimulatorValidationError("FHIR Order patientRecordId is required.") from exc
    fhir = payload.get("fhir") if isinstance(payload.get("fhir"), dict) else payload
    status = clean_text(fhir.get("status") or DEFAULT_STATUS)
    intent = clean_text(fhir.get("intent") or DEFAULT_INTENT)
    if not status:
        raise SimulatorValidationError("FHIR Order status is required.")
    if not intent:
        raise SimulatorValidationError("FHIR Order intent is required.")
    priority = clean_text(fhir.get("priority") or DEFAULT_PRIORITY)
    occurrence = normalize_datetime(fhir.get("occurrenceDateTime") or payload.get("requestedAt"))
    authored_on = normalize_datetime(fhir.get("authoredOn"), fallback=timestamp_factory())
    order_code = clean_text(fhir.get("codeCode") or fhir.get("code") or payload.get("orderCode") or DEFAULT_CODE)
    order_text = clean_text(fhir.get("codeDisplay") or payload.get("orderCodeText") or DEFAULT_TEXT)
    return {
        "patient_record_id": patient_record_id, "status": status, "intent": intent,
        "priority": priority,
        "requested_at": storage_timestamp(occurrence or authored_on, storage_timestamp_factory),
        "ordering_provider": clean_text(fhir.get("requester") or payload.get("orderingProvider") or DEFAULT_PROVIDER),
        "clinical_indication": clean_text(fhir.get("reasonCodeText") or payload.get("clinicalIndication")),
        "order_code": order_code or DEFAULT_CODE, "order_code_text": order_text or DEFAULT_TEXT,
        "alternate_code": clean_text(fhir.get("alternateCode") or payload.get("alternateCode") or DEFAULT_ALT_CODE),
        "alternate_code_text": clean_text(fhir.get("alternateCodeText") or payload.get("alternateCodeText") or DEFAULT_ALT_TEXT),
        "alternate_code_system": clean_text(fhir.get("alternateCodeSystem") or payload.get("alternateCodeSystem") or DEFAULT_ALT_SYSTEM),
        "fhir": dict(fhir), "occurrence": occurrence, "authored_on": authored_on,
    }
