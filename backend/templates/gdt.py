"""Pure outbound GDT payload construction."""

from __future__ import annotations

from typing import Any

from backend.domain.gdt_protocol import (
    GDT_ORDER_CORRELATION_FIELD,
    GDT_ORDER_MESSAGE_TYPE,
    GDT_ORDER_TEST_CODE,
    GDT_ORDER_TEST_CODE_FIELD,
    GdtAdapterResult,
    _gdt_clean_value,
    parse_gdt_message,
    render_gdt_message,
)


def _request_date(value: Any) -> str:
    digits = "".join(character for character in _gdt_clean_value(value) if character.isdigit())
    if len(digits) >= 8:
        year, month, day = digits[:4], digits[4:6], digits[6:8]
        if year.isdigit() and month.isdigit() and day.isdigit():
            return f"{day}{month}{year}"
    return ""


def build_gdt_6302_request(order: dict[str, Any]) -> GdtAdapterResult:
    records: list[tuple[str, Any]] = [
        ("8315", order.get("receiverGdtId", "LABGDT")),
        ("8316", order.get("senderGdtId", "HCLAB")),
        ("3000", order["gdtPatientNumber"]),
        ("3101", order["lastName"]),
        ("3102", order["firstName"]),
        ("3103", order["birthDate"]),
        (GDT_ORDER_CORRELATION_FIELD, order["localGdtOrderNumber"]),
        (GDT_ORDER_TEST_CODE_FIELD, GDT_ORDER_TEST_CODE),
    ]
    request_date = _request_date(order.get("requestedAt", ""))
    if request_date:
        records.append(("6200", request_date))
    if order.get("sex"):
        records.append(("3110", order["sex"]))
    notes = [value for value in (order.get("orderingProvider"), order.get("clinicalIndication")) if _gdt_clean_value(value)]
    if notes:
        records.append(("6227", " | ".join(_gdt_clean_value(value) for value in notes)))
    raw_gdt_text = render_gdt_message(records, set_type=GDT_ORDER_MESSAGE_TYPE)
    parsed = parse_gdt_message(raw_gdt_text)
    canonical = {
        "patient": order.get("patient", {}),
        "order": order.get("order", {}),
        "test": {"field": GDT_ORDER_TEST_CODE_FIELD, "code": GDT_ORDER_TEST_CODE,
                 "label": order.get("testLabel", "12-lead resting ECG")},
        "correlation": {"field": GDT_ORDER_CORRELATION_FIELD,
                        "localGdtOrderNumber": order["localGdtOrderNumber"]},
        "validation": {"errors": [], "warnings": []},
    }
    return GdtAdapterResult(raw_gdt_text, parsed, canonical, {"errors": [], "warnings": []})
