"""Framework-independent FHIR reference and error mapping helpers."""

from __future__ import annotations

import json
import re
from typing import Any

from .errors import UpstreamFhirError, ValidationError


def normalize_fhir_reference(value: str, resource_type: str) -> str:
    parts = [part.strip() for part in value.strip().split("/") if part.strip()]
    if len(parts) != 2 or parts[0] != resource_type:
        raise ValidationError(f"FHIR reference must look like {resource_type}/id.")
    return f"{resource_type}/{parts[1]}"


def fhir_bundle_resources(bundle: dict[str, Any], resource_type: str) -> list[dict[str, Any]]:
    if bundle.get("resourceType") != "Bundle":
        raise UpstreamFhirError(
            f"Medplum {resource_type} search returned a non-Bundle response.",
            response_payload=bundle,
        )
    entries = bundle.get("entry") or []
    if not isinstance(entries, list):
        raise UpstreamFhirError(
            f"Medplum {resource_type} Bundle entry is malformed.",
            response_payload=bundle,
        )
    return [
        resource
        for entry in entries
        if isinstance(entry, dict)
        and isinstance((resource := entry.get("resource")), dict)
        and resource.get("resourceType") == resource_type
    ]


def service_request_references(references: list[str]) -> list[str]:
    return [reference for reference in references if reference.startswith("ServiceRequest/")]


def diagnostic_report_effective_date(resource: dict[str, Any]) -> str:
    effective = str(resource.get("effectiveDateTime") or "").strip()
    if effective:
        return effective
    period = resource.get("effectivePeriod")
    if isinstance(period, dict):
        return str(period.get("start") or period.get("end") or "").strip()
    return str(resource.get("issued") or "").strip()


def attachment_reference_values(value: Any) -> list[str]:
    references: list[str] = []
    if isinstance(value, dict):
        url = str(value.get("url") or "").strip()
        if url and re.match(r"^[A-Za-z]+/[A-Za-z0-9\-.]+$", url):
            references.append(url)
        nested_values = value.values()
    elif isinstance(value, list):
        nested_values = value
    else:
        return references
    for nested in nested_values:
        for reference in attachment_reference_values(nested):
            if reference not in references:
                references.append(reference)
    return references


def operation_outcome_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return payload if isinstance(payload, dict) and payload.get("resourceType") == "OperationOutcome" else {}


def operation_outcome_from_error(message: str) -> dict[str, Any]:
    _, _, body = message.partition(": ")
    if not body:
        return {}
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return {}
    return operation_outcome_from_payload(parsed)


def http_status_from_upstream_error(message: str) -> int | None:
    match = re.search(r"HTTP\s+(\d+)", message)
    return int(match.group(1)) if match else None
