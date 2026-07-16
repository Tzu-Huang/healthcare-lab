"""Pure FHIR ledger mapping, normalization, and projection rules."""

from __future__ import annotations

import json
from typing import Any

from backend.domain.errors import SimulatorValidationError

FHIR_SUPPORTED_RESOURCE_TYPES = (
    "Patient", "ServiceRequest", "Binary", "Observation",
    "DocumentReference", "DiagnosticReport", "Provenance",
)
FHIR_RESOURCE_DEPENDENCY_ORDER = {
    "Patient": 10, "ServiceRequest": 20, "Binary": 40, "Observation": 50,
    "DocumentReference": 60, "DiagnosticReport": 70, "Provenance": 80,
}
FHIR_IDENTIFIER_SYSTEMS = {
    resource_type: f"https://healthcare-lab.local/fhir/identifier/{slug}"
    for resource_type, slug in (
        ("Patient", "patient"), ("ServiceRequest", "service-request"),
        ("Binary", "binary"), ("Observation", "observation"),
        ("DocumentReference", "document-reference"),
        ("DiagnosticReport", "diagnostic-report"), ("Provenance", "provenance"),
    )
}
FHIR_RESOURCE_MAPPINGS = {
    "Patient": ("local_patient_records", ()),
    "ServiceRequest": ("local_order_records", ("Patient",)),
    "Binary": ("local_fhir_artifacts", ()),
    "Observation": ("local_fhir_results", ("Patient", "ServiceRequest")),
    "DocumentReference": ("local_fhir_artifacts", ("Patient", "ServiceRequest", "Binary")),
    "DiagnosticReport": (
        "local_fhir_results", ("Patient", "ServiceRequest", "Observation", "DocumentReference")
    ),
    "Provenance": (
        "local_fhir_provenance",
        ("Patient", "ServiceRequest", "Binary", "Observation", "DocumentReference", "DiagnosticReport"),
    ),
}


def json_value(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return fallback


def clean_text(value: Any, field_name: str, required: bool = False) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise SimulatorValidationError(f"FHIR {field_name} is required.")
    return text


def identifier_token(value: Any) -> str:
    text = str(value if value is not None else "").strip().lower()
    cleaned: list[str] = []
    previous_dash = False
    for character in text:
        if character.isalnum():
            cleaned.append(character)
            previous_dash = False
        elif not previous_dash:
            cleaned.append("-")
            previous_dash = True
    return "".join(cleaned).strip("-") or "record"


def mapping_for_resource_type(resource_type: str) -> dict[str, Any]:
    normalized = clean_text(resource_type, "resourceType", required=True)
    if normalized not in FHIR_SUPPORTED_RESOURCE_TYPES:
        raise SimulatorValidationError(
            f"FHIR resourceType must be one of: {', '.join(FHIR_SUPPORTED_RESOURCE_TYPES)}."
        )
    source_type, depends_on = FHIR_RESOURCE_MAPPINGS[normalized]
    return {
        "resourceType": normalized,
        "localSourceType": source_type,
        "identifierSystem": FHIR_IDENTIFIER_SYSTEMS[normalized],
        "identifierPath": "identifier",
        "dependsOn": list(depends_on),
        "dependencyOrder": FHIR_RESOURCE_DEPENDENCY_ORDER[normalized],
    }


def list_resource_mappings() -> list[dict[str, Any]]:
    return [mapping_for_resource_type(item) for item in FHIR_SUPPORTED_RESOURCE_TYPES]


def identifier_value(resource_type: str, local_source_type: str, local_source_id: Any) -> str:
    mapping = mapping_for_resource_type(resource_type)
    return (
        f"{identifier_token(local_source_type or mapping['localSourceType'])}-"
        f"{identifier_token(local_source_id)}"
    )


def resource_with_identifier(
    resource: dict[str, Any], *, resource_type: str,
    identifier_system: str, identifier_value_text: str,
) -> dict[str, Any]:
    if not isinstance(resource, dict):
        raise SimulatorValidationError("FHIR resource must be a JSON object.")
    normalized = dict(resource)
    normalized["resourceType"] = resource_type
    identifiers = normalized.get("identifier")
    identifiers = (
        [item for item in identifiers if isinstance(item, dict)]
        if isinstance(identifiers, list) else []
    )
    if not any(
        item.get("system") == identifier_system and item.get("value") == identifier_value_text
        for item in identifiers
    ):
        identifiers.insert(0, {"system": identifier_system, "value": identifier_value_text})
    normalized["identifier"] = identifiers
    return normalized


def normalize_record_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SimulatorValidationError("FHIR workflow payload must be a JSON object.")
    raw_resource = payload.get("resource") or payload.get("resourceJson") or {}
    if isinstance(raw_resource, str):
        try:
            raw_resource = json.loads(raw_resource)
        except json.JSONDecodeError as exc:
            raise SimulatorValidationError("FHIR resource JSON is invalid.") from exc
    if not isinstance(raw_resource, dict):
        raise SimulatorValidationError("FHIR resource must be a JSON object.")
    resource_type = clean_text(
        payload.get("resourceType") or raw_resource.get("resourceType"),
        "resourceType", required=True,
    )
    mapping = mapping_for_resource_type(resource_type)
    local_source_type = clean_text(
        payload.get("localSourceType") or mapping["localSourceType"],
        "localSourceType", required=True,
    )
    local_source_id = clean_text(payload.get("localSourceId"), "localSourceId", required=True)
    identifier_system = clean_text(
        payload.get("identifierSystem") or mapping["identifierSystem"],
        "identifierSystem", required=True,
    )
    identifier_value_text = clean_text(
        payload.get("identifierValue")
        or identifier_value(resource_type, local_source_type, local_source_id),
        "identifierValue", required=True,
    )
    dependencies = payload.get("dependencies", payload.get("dependsOn", mapping["dependsOn"]))
    if not isinstance(dependencies, list | tuple):
        raise SimulatorValidationError("FHIR dependencies must be a list.")
    resource = resource_with_identifier(
        raw_resource, resource_type=resource_type,
        identifier_system=identifier_system, identifier_value_text=identifier_value_text,
    )
    return {
        "local_source_type": local_source_type,
        "local_source_id": local_source_id,
        "resource_type": resource_type,
        "identifier_system": identifier_system,
        "identifier_value": identifier_value_text,
        "resource_json": json.dumps(resource, sort_keys=True),
        "dependency_json": json.dumps(list(dependencies)),
    }


def record_number(record_id: int) -> str:
    return f"FHIR-{record_id:06d}"

