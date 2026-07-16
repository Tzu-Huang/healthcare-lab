"""Stateless construction and pure compatibility helpers for legacy facades."""

from __future__ import annotations

from typing import Any

from backend.domain import fhir_ledger as fhir_domain
from backend.domain import fhir_order
from backend.mappers import fhir as fhir_mappers
from backend.domain.gdt_protocol import (
    attachment_payloads_from_result_fields,
    first_gdt_field,
)
from backend.services.gdt_coordination import (
    artifact_status,
    normalize_gdt_order_payload,
    validate_gdt_patient_number,
    validate_gdt_test_code,
)

FHIR_RESOURCE_DEPENDENCY_ORDER = fhir_domain.FHIR_RESOURCE_DEPENDENCY_ORDER
FHIR_IDENTIFIER_SYSTEMS = fhir_domain.FHIR_IDENTIFIER_SYSTEMS
FHIR_RESOURCE_MAPPINGS = fhir_domain.FHIR_RESOURCE_MAPPINGS


def fhir_order_values(payload: dict[str, Any]) -> dict[str, Any]:
    fhir = payload.get("fhir") if isinstance(payload.get("fhir"), dict) else payload
    return fhir if isinstance(fhir, dict) else {}


def validate_fhir_order_payload(payload, *, timestamp_factory, storage_timestamp_factory):
    return fhir_order.validate_payload(
        payload,
        timestamp_factory=timestamp_factory,
        storage_timestamp_factory=storage_timestamp_factory,
    )


def gdt_order_number(record_id: int) -> str:
    return f"GDT-ORD-{record_id:06d}"


def gdt_patient_number(patient_record_id: int) -> str:
    return f"GDT-PAT-{patient_record_id:06d}"


def gdt_birth_date(dob: str) -> str:
    return f"{dob[6:]}{dob[4:6]}{dob[:4]}"


def gdt_attachment_filename(url: str, path: str = "") -> str:
    source = path or url
    return source.rstrip("/").replace("\\", "/").split("/")[-1] if source else ""


def gdt_result_measurements(fields: dict[str, list[str]]) -> dict[str, str]:
    return {
        label: first_gdt_field(fields, code)
        for label, code in (("HR", "8401"), ("PR", "8402"), ("QRS", "8403"),
                            ("QT", "8404"), ("QTC", "8405"))
        if first_gdt_field(fields, code)
    }


json_value = fhir_domain.json_value
fhir_record_number = fhir_domain.record_number
fhir_clean_text = fhir_domain.clean_text
fhir_identifier_token = fhir_domain.identifier_token
fhir_mapping_for_resource_type = fhir_domain.mapping_for_resource_type
list_fhir_resource_mappings = fhir_domain.list_resource_mappings
fhir_identifier_value = fhir_domain.identifier_value
fhir_resource_with_identifier = fhir_domain.resource_with_identifier
normalize_fhir_record_payload = fhir_domain.normalize_record_payload
project_fhir_workflow_record = fhir_mappers.project_workflow_record
project_fhir_sync_attempt = fhir_mappers.project_sync_attempt
fhir_order_clean_text = fhir_order.clean_text
fhir_order_list = fhir_order.list_values
fhir_reference_item = fhir_order.reference_item
fhir_reference_list = fhir_order.reference_list
fhir_codeable_concept = fhir_order.codeable_concept
fhir_order_datetime = fhir_order.normalize_datetime
fhir_order_storage_timestamp = fhir_order.storage_timestamp
fhir_order_storage_priority = fhir_order.storage_priority
gdt_artifact_status = artifact_status
gdt_attachment_payloads = attachment_payloads_from_result_fields
normalize_gdt_payload = normalize_gdt_order_payload
validate_gdt_override = validate_gdt_patient_number
validate_gdt_code = validate_gdt_test_code


def is_url_reference(value: str) -> bool:
    return str(value or "").lower().startswith(("http://", "https://"))
