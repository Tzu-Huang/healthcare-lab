from __future__ import annotations

from dataclasses import dataclass
from typing import Any

GDT_VERSION = "02.10"
GDT_DEFAULT_CHARSET_MARKER = "3"
GDT_DEFAULT_ENCODING = "cp1252"
GDT_ORDER_MESSAGE_TYPE = "6302"
GDT_RESULT_MESSAGE_TYPE = "6310"
GDT_ORDER_TEST_CODE_FIELD = "8402"
GDT_ORDER_TEST_CODE = "EKG01"


class GdtValidationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "001",
        field: str = "",
        notices: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.notices = notices or [validation_notice(code, "error", message, field=field)]


@dataclass(frozen=True)
class GdtAdapterResult:
    raw_gdt_text: str
    parsed_fields: dict[str, list[str]]
    canonical: dict[str, Any]
    validation: dict[str, list[dict[str, str]]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "rawGdtText": self.raw_gdt_text,
            "parsedFields": self.parsed_fields,
            "canonical": self.canonical,
            "validation": self.validation,
        }


def validation_notice(
    code: str,
    severity: str,
    message: str,
    *,
    field: str = "",
) -> dict[str, str]:
    notice = {"code": code, "severity": severity, "message": message}
    if field:
        notice["field"] = field
    return notice


def _gdt_clean_value(value: Any) -> str:
    return str(value if value is not None else "").strip().replace("\r", " ").replace("\n", " ")


def _encode_gdt_text(value: str) -> bytes:
    try:
        return value.encode(GDT_DEFAULT_ENCODING)
    except UnicodeEncodeError as exc:
        raise GdtValidationError(
            "GDT 2.1 fields must use ANSI/ISO-8859-1 compatible characters.",
            code="112",
        ) from exc


def render_gdt_record(code: str, value: Any) -> bytes:
    field_code = str(code).strip()
    if len(field_code) != 4 or not field_code.isdigit():
        raise GdtValidationError(
            f"GDT field code must be four digits: {field_code}",
            code="002",
            field=field_code,
        )
    content = _encode_gdt_text(_gdt_clean_value(value))
    record_length = 3 + 4 + len(content) + 2
    if record_length > 999:
        raise GdtValidationError(
            f"GDT field {field_code} exceeds the 999 byte record limit.",
            code="113",
            field=field_code,
        )
    return f"{record_length:03d}{field_code}".encode("ascii") + content + b"\r\n"


def render_gdt_message(records: list[tuple[str, Any]], *, set_type: str) -> str:
    normalized = [
        (code, value)
        for code, value in records
        if code not in {"8000", "8100", "9218", "9206"}
    ]
    total_length = "00000"
    for _ in range(8):
        full_records = [
            ("8000", set_type),
            ("8100", total_length),
            ("9218", GDT_VERSION),
            ("9206", GDT_DEFAULT_CHARSET_MARKER),
        ] + normalized
        payload = b"".join(render_gdt_record(code, value) for code, value in full_records)
        next_length = f"{len(payload):05d}"
        if next_length == total_length:
            return payload.decode(GDT_DEFAULT_ENCODING)
        total_length = next_length
    raise GdtValidationError("Could not stabilize GDT 8100 full message length.", code="090", field="8100")


def parse_gdt_message(payload: str) -> dict[str, list[str]]:
    return parse_gdt_dataset(payload).parsed_fields


def parse_gdt_dataset(payload: str) -> GdtAdapterResult:
    raw_text = str(payload or "")
    raw = raw_text.encode(GDT_DEFAULT_ENCODING)
    fields: dict[str, list[str]] = {}
    offset = 0
    while offset < len(raw):
        if offset + 7 > len(raw):
            raise GdtValidationError("GDT record is truncated.", code="001")
        length_text = raw[offset : offset + 3].decode("ascii", errors="ignore")
        try:
            record_length = int(length_text)
        except ValueError as exc:
            raise GdtValidationError("GDT record length must be three digits.", code="001") from exc
        if len(length_text) != 3 or record_length < 9:
            raise GdtValidationError("GDT record length is invalid.", code="001")
        record = raw[offset : offset + record_length]
        if len(record) != record_length or not record.endswith(b"\r\n"):
            raise GdtValidationError("GDT record byte length does not match its envelope.", code="001")
        code = record[3:7].decode("ascii", errors="ignore")
        if len(code) != 4 or not code.isdigit():
            raise GdtValidationError(f"GDT field code must be four digits: {code}", code="002", field=code)
        value = record[7:-2].decode(GDT_DEFAULT_ENCODING)
        fields.setdefault(code, []).append(value)
        offset += record_length
    if not fields:
        raise GdtValidationError("GDT payload is empty.", code="001")
    _validate_common_required_fields(fields, raw_length=len(raw))
    return GdtAdapterResult(
        raw_gdt_text=raw_text,
        parsed_fields=fields,
        canonical={},
        validation={"errors": [], "warnings": []},
    )


def first_gdt_field(fields: dict[str, list[str]], code: str) -> str:
    values = fields.get(code) or []
    return values[0] if values else ""


def build_gdt_6302_request(order: dict[str, Any]) -> GdtAdapterResult:
    records: list[tuple[str, Any]] = [
        ("8315", order.get("receiverGdtId", "LABGDT")),
        ("8316", order.get("senderGdtId", "HCLAB")),
        ("3000", order["gdtPatientNumber"]),
        ("3101", order["lastName"]),
        ("3102", order["firstName"]),
        ("3103", order["birthDate"]),
        ("6200", order["localGdtOrderNumber"]),
        (GDT_ORDER_TEST_CODE_FIELD, GDT_ORDER_TEST_CODE),
    ]
    if order.get("sex"):
        records.append(("3110", order["sex"]))
    if order.get("requestedAt"):
        records.append(("6220", order["requestedAt"]))
    if order.get("orderingProvider"):
        records.append(("6227", order["orderingProvider"]))
    if order.get("clinicalIndication"):
        records.append(("6228", order["clinicalIndication"]))
    raw_gdt_text = render_gdt_message(records, set_type=GDT_ORDER_MESSAGE_TYPE)
    parsed = parse_gdt_message(raw_gdt_text)
    canonical = {
        "patient": order.get("patient", {}),
        "order": order.get("order", {}),
        "test": {
            "field": GDT_ORDER_TEST_CODE_FIELD,
            "code": GDT_ORDER_TEST_CODE,
            "label": order.get("testLabel", "12-lead resting ECG"),
        },
        "correlation": {"localGdtOrderNumber": order["localGdtOrderNumber"]},
        "validation": {"errors": [], "warnings": []},
    }
    return GdtAdapterResult(raw_gdt_text, parsed, canonical, {"errors": [], "warnings": []})


MEASUREMENT_ALIASES = {
    "HR": "HR",
    "PR": "PR",
    "QRS": "QRS",
    "QT": "QT",
    "QTC": "QTC",
    "QTc": "QTC",
    "P-AXIS": "P_AXIS",
    "P_AXIS": "P_AXIS",
    "QRS-AXIS": "QRS_AXIS",
    "QRS_AXIS": "QRS_AXIS",
    "T-AXIS": "T_AXIS",
    "T_AXIS": "T_AXIS",
}


def parse_gdt_6310_result(raw_gdt_text: str) -> GdtAdapterResult:
    parsed = parse_gdt_message(raw_gdt_text)
    message_type = first_gdt_field(parsed, "8000")
    if message_type != GDT_RESULT_MESSAGE_TYPE:
        raise GdtValidationError(
            f"GDT result import only supports {GDT_RESULT_MESSAGE_TYPE}.",
            code="201",
            field="8000",
        )
    warnings: list[dict[str, str]] = []
    measurements, measurement_warnings = _measurement_payloads(parsed)
    warnings.extend(measurement_warnings)
    canonical = {
        "patient": {
            "gdtPatientNumber": first_gdt_field(parsed, "3000"),
            "lastName": first_gdt_field(parsed, "3101"),
            "firstName": first_gdt_field(parsed, "3102"),
            "dob": first_gdt_field(parsed, "3103"),
            "sex": first_gdt_field(parsed, "3110"),
        },
        "order": {
            "localGdtOrderNumber": "",
            "identifiers": result_order_identifiers(parsed),
        },
        "result": {
            "status": first_gdt_field(parsed, "8418"),
            "interpretation": parsed.get("6220", []),
            "comments": parsed.get("6227", []),
            "formattedText": parsed.get("6228", []),
            "measurements": measurements,
            "summary": {
                code: parsed.get(code, [])
                for code in ("8401", "8402", "8403", "8404", "8405")
                if code in parsed
            },
        },
        "attachments": attachment_payloads_from_result_fields(parsed),
        "correlation": {
            "matchStatus": "",
            "identifiers": result_order_identifiers(parsed),
        },
        "validation": {"errors": [], "warnings": warnings},
    }
    return GdtAdapterResult(
        raw_gdt_text=str(raw_gdt_text or ""),
        parsed_fields=parsed,
        canonical=canonical,
        validation={"errors": [], "warnings": warnings},
    )


def result_order_identifiers(fields: dict[str, list[str]]) -> list[str]:
    return [value for value in fields.get("6200", []) if value]


def attachment_payloads_from_result_fields(fields: dict[str, list[str]]) -> list[dict[str, str]]:
    attachments: list[dict[str, str]] = []
    artifact_ids = fields.get("6302", [])
    formats = fields.get("6303", [])
    descriptions = fields.get("6304", [])
    paths = fields.get("6305", [])
    grouped_artifacts = bool(
        artifact_ids
        and len(paths) >= len(artifact_ids)
        and formats
        and all("/" not in item for item in formats)
    )
    if grouped_artifacts:
        for index, artifact_id in enumerate(artifact_ids):
            path = paths[index] if index < len(paths) else ""
            file_format = formats[index] if index < len(formats) else ""
            description = descriptions[index] if index < len(descriptions) else ""
            role = _attachment_role(file_format, description)
            attachments.append(
                {
                    "role": role,
                    "path": path,
                    "contentType": _attachment_content_type(file_format),
                    "filename": artifact_id,
                }
            )
        return attachments
    legacy_pdf_path = first_gdt_field(fields, "6302")
    if legacy_pdf_path:
        attachments.append(
            {
                "role": "report",
                "path": legacy_pdf_path,
                "contentType": first_gdt_field(fields, "6303") or "application/pdf",
            }
        )
    legacy_waveform_path = first_gdt_field(fields, "6304")
    if legacy_waveform_path:
        attachments.append(
            {
                "role": "waveform",
                "path": legacy_waveform_path,
                "contentType": first_gdt_field(fields, "6305") or "application/xml",
            }
        )
    return attachments


def _validate_common_required_fields(fields: dict[str, list[str]], *, raw_length: int) -> None:
    notices = []
    for code in ("8000", "8100", "9218"):
        if not first_gdt_field(fields, code):
            notices.append(validation_notice("201", "error", f"GDT field {code} is required.", field=code))
    if notices:
        raise GdtValidationError(notices[0]["message"], notices=notices)
    total_length = first_gdt_field(fields, "8100")
    if not total_length.isdigit() or len(total_length) != 5:
        raise GdtValidationError("GDT 8100 total length must be five digits.", code="020", field="8100")
    if int(total_length) != raw_length:
        raise GdtValidationError(
            "GDT 8100 total length does not match actual byte length.",
            code="020",
            field="8100",
        )


def _measurement_payloads(
    fields: dict[str, list[str]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    measurements: dict[str, dict[str, Any]] = {}
    warnings: list[dict[str, str]] = []
    ids = fields.get("8410", [])
    values = fields.get("8420", [])
    units = fields.get("8421", [])
    for index, test_id in enumerate(ids):
        canonical_key = MEASUREMENT_ALIASES.get(test_id)
        if not canonical_key:
            if index < len(values):
                warnings.append(
                    validation_notice(
                        "301",
                        "warning",
                        f"GDT 8410 Test-ID is not mapped: {test_id}",
                        field="8410",
                    )
                )
            continue
        if index >= len(values):
            warnings.append(
                validation_notice(
                    "302",
                    "warning",
                    f"GDT 8420 result value is missing for {test_id}.",
                    field="8420",
                )
            )
            continue
        measurements[canonical_key] = {
            "value": _coerce_measurement_value(values[index]),
            "unit": units[index] if index < len(units) else "",
            "sourceTestId": test_id,
        }
    return measurements, warnings


def _coerce_measurement_value(value: str) -> int | float | str:
    try:
        number = float(value)
    except ValueError:
        return value
    return int(number) if number.is_integer() else number


def _attachment_role(file_format: str, description: str) -> str:
    text = f"{file_format} {description}".upper()
    if "PDF" in text or "REPORT" in text:
        return "report"
    if "DICOM" in text or "WAVEFORM" in text or "XML" in text:
        return "waveform"
    return "result-artifact"


def _attachment_content_type(file_format: str) -> str:
    normalized = file_format.strip().lower()
    if normalized == "pdf":
        return "application/pdf"
    if normalized == "dicom":
        return "application/dicom"
    if normalized == "xml":
        return "application/xml"
    if normalized.startswith("application/"):
        return normalized
    return normalized
