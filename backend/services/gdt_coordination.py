"""Narrow coordination between pure GDT protocol behavior and persistence."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from backend.domain import order as order_domain
from backend.domain.errors import SimulatorValidationError
from backend.domain.gdt_protocol import (
    GDT_DEFAULT_ENCODING,
    GDT_ORDER_TEST_CODE,
    GDT_ORDER_TEST_CODE_FIELD,
    GDT_RESULT_MESSAGE_TYPE,
    GdtValidationError,
    build_gdt_6302_request,
    parse_gdt_6310_result,
    render_gdt_message,
)


class GdtWorkflowRepositoryPort(Protocol):
    def create_gdt_order_record(self, values: dict[str, Any]) -> dict[str, Any]: ...
    def record_gdt_result(self, values: dict[str, Any]) -> dict[str, Any]: ...
    def list_gdt_order_records(self) -> list[dict[str, Any]]: ...
    def get_gdt_order_record(self, record_id: int) -> dict[str, Any]: ...
    def list_gdt_messages(self, order_record_id: int | None = None) -> list[dict[str, Any]]: ...
    def list_gdt_events(self, order_record_id: int | None = None) -> list[dict[str, Any]]: ...
    def list_gdt_attachments(self, order_record_id: int | None = None) -> list[dict[str, Any]]: ...
    def list_gdt_workbench(self, *, bridge_inbox: list[dict[str, Any]] | None = None) -> dict[str, Any]: ...
    def record_gdt_order_export(self, order_record_id: int, *, export_path: str,
                                status: str, error_text: str = "") -> dict[str, Any]: ...
    def list_gdt_orders(self) -> list[dict[str, Any]]: ...


def _default_requested_at() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def validate_gdt_patient_number(value: Any, field_name: str = "gdtPatientNumber") -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) > 64:
        raise SimulatorValidationError(f"{field_name} must be 64 characters or fewer.")
    if any(character in text for character in "\r\n"):
        raise SimulatorValidationError(f"{field_name} cannot contain line breaks.")
    try:
        text.encode(GDT_DEFAULT_ENCODING)
    except UnicodeEncodeError as exc:
        raise SimulatorValidationError(
            "GDT 2.1 patient fields must use ANSI/ISO-8859-1 compatible characters."
        ) from exc
    return text


def validate_gdt_test_code(value: Any) -> str:
    normalized = str(value or GDT_ORDER_TEST_CODE).strip().upper()
    if normalized != GDT_ORDER_TEST_CODE:
        raise SimulatorValidationError(
            f"GDT ECG order MVP only supports {GDT_ORDER_TEST_CODE_FIELD}={GDT_ORDER_TEST_CODE}."
        )
    return normalized


def normalize_gdt_order_payload(
    payload: dict[str, Any], *, requested_at_factory: Callable[[], str] = _default_requested_at
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SimulatorValidationError("GDT order payload must be a JSON object.")
    try:
        patient_record_id = int(payload.get("patientRecordId"))
    except (TypeError, ValueError) as exc:
        raise SimulatorValidationError("GDT order patientRecordId is required.") from exc
    return {
        "patient_record_id": patient_record_id,
        "requested_at": order_domain.normalize_requested_at(
            payload.get("requestedAt"), default_factory=requested_at_factory
        ),
        "ordering_provider": order_domain.clean_text(payload.get("orderingProvider"), "orderingProvider"),
        "clinical_indication": order_domain.clean_text(payload.get("clinicalIndication"), "clinicalIndication"),
        "attachment_url": order_domain.clean_text(payload.get("attachmentUrl"), "attachmentUrl"),
        "gdt_patient_number_override": validate_gdt_patient_number(
            payload.get(
                "gdtPatientNumberOverride",
                payload.get("gdtPatientNumber", payload.get("patientNumberOverride", "")),
            ),
            "gdtPatientNumberOverride",
        ),
        "gdt_test_code": validate_gdt_test_code(
            payload.get("gdtTestCode", payload.get("testCode", payload.get("examCode", GDT_ORDER_TEST_CODE)))
        ),
    }


def artifact_status(reference: str, bridge_root: str = "") -> tuple[str, dict[str, Any]]:
    normalized = str(reference or "").strip()
    if not normalized:
        return "missing-reference", {"warning": "Artifact reference is empty."}
    if normalized.lower().startswith(("http://", "https://")):
        return "reference-only", {"kind": "url"}
    reference_path = Path(normalized)
    candidates = [reference_path]
    if bridge_root and not reference_path.is_absolute():
        root = Path(bridge_root)
        candidates.extend((root / normalized, root / "reports" / normalized))
    if any(candidate.exists() for candidate in candidates):
        return "available", {"kind": "path"}
    return "warning", {
        "warning": "Referenced artifact target was not found.",
        "reference": normalized,
    }


def normalize_result_attachment(
    attachment: dict[str, Any], *, bridge_root: str = "", source_file: str = ""
) -> dict[str, Any]:
    item = dict(attachment)
    reference = str(item.get("reference") or "")
    path = str(item.get("path") or "")
    url = str(item.get("url") or "")
    inferred_status, inferred_details = artifact_status(reference or path or url, bridge_root)
    explicit_details = item.get("details") if isinstance(item.get("details"), dict) else {}
    return {
        **item,
        "reference": reference,
        "path": path,
        "url": url,
        "status": str(item.get("status") or inferred_status),
        "details": {**inferred_details, **explicit_details},
        "sourceFile": str(item.get("sourceFile") or item.get("source_file") or source_file),
    }


class GdtWorkflowCoordinator:
    def __init__(
        self,
        repository: GdtWorkflowRepositoryPort,
        *,
        requested_at_factory: Callable[[], str] = _default_requested_at,
    ) -> None:
        self._repository = repository
        self._requested_at_factory = requested_at_factory

    @property
    def repository(self) -> GdtWorkflowRepositoryPort:
        return self._repository

    def create_gdt_order_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._repository.create_gdt_order_record(
            normalize_gdt_order_payload(payload, requested_at_factory=self._requested_at_factory)
        )

    def record_gdt_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SimulatorValidationError("GDT result payload must be a JSON object.")
        raw_gdt_text = str(
            payload.get("rawGdtText", payload.get("payload", payload.get("raw", ""))) or ""
        )
        try:
            parsed = parse_gdt_6310_result(raw_gdt_text).as_dict()
        except GdtValidationError as exc:
            raise SimulatorValidationError(str(exc)) from exc
        bridge_root = str(payload.get("bridgeRoot") or payload.get("bridge_root") or "")
        source_file = str(payload.get("sourceFile") or payload.get("source_file") or "").strip()
        canonical = dict(parsed["canonical"])
        canonical["attachments"] = [
            normalize_result_attachment(item, bridge_root=bridge_root, source_file=source_file)
            for item in canonical.get("attachments", [])
            if isinstance(item, dict)
        ]
        explicit_attachments = [
            normalize_result_attachment(item, bridge_root=bridge_root, source_file=source_file)
            for item in (payload.get("attachments") or [])
            if isinstance(item, dict)
        ]
        return self._repository.record_gdt_result(
            {
                **parsed,
                "canonical": canonical,
                "attachments": explicit_attachments,
                "sourceFile": source_file,
                "sourcePath": str(payload.get("sourcePath") or payload.get("source_path") or ""),
            }
        )

    def create_gdt_demo_result(self, order_record_id: int) -> dict[str, Any]:
        order = self.get_gdt_order_record(order_record_id)
        order_number = order["localGdtOrderNumber"]
        artifact_prefix = order_number.lower()
        raw_gdt_text = render_gdt_message(
            [
                ("8315", "HCLAB"), ("8316", "DEMOECG"),
                ("3000", order["gdtPatientNumber"]),
                ("3101", order["patientSnapshot"].get("lastName", "")),
                ("3102", order["patientSnapshot"].get("firstName", "")),
                ("6200", order_number), ("8402", GDT_ORDER_TEST_CODE),
                ("8410", "HR"), ("8420", "72"), ("8421", "bpm"),
                ("8410", "PR"), ("8420", "160"), ("8421", "ms"),
                ("8410", "QRS"), ("8420", "92"), ("8421", "ms"),
                ("8410", "QT"), ("8420", "390"), ("8421", "ms"),
                ("8410", "QTC"), ("8420", "427"), ("8421", "ms"),
                ("8418", "final"),
                ("6220", "Normal sinus rhythm. No acute ST-T changes."),
                ("6227", "Demo ECG generated by Healthcare Lab."),
                ("6228", "Measurements are deterministic for bridge validation."),
                ("6302", "report"), ("6303", "PDF"), ("6304", "ECG PDF report"),
                ("6305", f"reports/{artifact_prefix}-report.pdf"),
                ("6302", "dicom"), ("6303", "DICOM"),
                ("6304", "DICOM ECG object reference"),
                ("6305", f"reports/{artifact_prefix}.dcm"),
            ],
            set_type=GDT_RESULT_MESSAGE_TYPE,
        )
        return self.record_gdt_result({"rawGdtText": raw_gdt_text, "sourceFile": "demo-result"})

    def list_gdt_order_records(self) -> list[dict[str, Any]]:
        return self._repository.list_gdt_order_records()

    def get_gdt_order_record(self, record_id: int) -> dict[str, Any]:
        return self._repository.get_gdt_order_record(record_id)

    def list_gdt_messages(self, order_record_id: int | None = None) -> list[dict[str, Any]]:
        return self._repository.list_gdt_messages(order_record_id)

    def list_gdt_events(self, order_record_id: int | None = None) -> list[dict[str, Any]]:
        return self._repository.list_gdt_events(order_record_id)

    def list_gdt_attachments(self, order_record_id: int | None = None) -> list[dict[str, Any]]:
        return self._repository.list_gdt_attachments(order_record_id)

    def list_gdt_workbench(self, *, bridge_inbox: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return self._repository.list_gdt_workbench(bridge_inbox=bridge_inbox)

    def record_gdt_order_export(self, order_record_id: int, *, export_path: str,
                                status: str, error_text: str = "") -> dict[str, Any]:
        return self._repository.record_gdt_order_export(
            order_record_id, export_path=export_path, status=status, error_text=error_text
        )

    def list_gdt_orders(self) -> list[dict[str, Any]]:
        return self._repository.list_gdt_orders()


def build_gdt_order_request(values: dict[str, Any]):
    """Named pure collaborator suitable for repository construction."""
    return build_gdt_6302_request(values)
