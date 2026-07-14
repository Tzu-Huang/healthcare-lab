"""FHIR inventory, preview, and synchronization coordination."""

from __future__ import annotations

import json
import re
import urllib.parse
from collections.abc import Callable
from typing import Any, Protocol

from backend.domain.errors import SimulatorValidationError, UpstreamFhirError, ValidationError
from backend.domain import fhir as fhir_domain
from backend.domain.statuses import (
    FHIR_SYNC_STATUS_FAILED,
    FHIR_SYNC_STATUS_PENDING,
    FHIR_SYNC_STATUS_SYNCED,
)
from backend.clients.medplum import (
    MedplumAuthManager,
    normalize_fhir_base_url,
    request_fhir_json,
)
from backend.domain.fhir import (
    http_status_from_upstream_error,
    operation_outcome_from_error,
    operation_outcome_from_payload,
)

MEDPLUM_INVENTORY_RESOURCE_TYPES = (
    "Patient",
    "ServiceRequest",
    "DiagnosticReport",
    "Observation",
    "DocumentReference",
)
MEDPLUM_READ_RESOURCE_TYPES = MEDPLUM_INVENTORY_RESOURCE_TYPES + ("Binary",)
MEDPLUM_PATIENT_REFERENCE_FIELDS = ("subject", "patient")


class FhirRepositoryPort(Protocol):
    def list_fhir_resource_mappings(self) -> list[dict[str, Any]]: ...

    def list_fhir_workflow_records(self, sync_status: str = "") -> list[dict[str, Any]]: ...

    def create_fhir_workflow_record(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def get_fhir_workflow_record(self, record_id: int) -> dict[str, Any]: ...

    def list_fhir_sync_attempts(self, record_id: int) -> list[dict[str, Any]]: ...


class FhirWorkflowService:
    def __init__(
        self,
        repository: FhirRepositoryPort,
        *,
        inventory_types: tuple[str, ...],
        medplum_base_url: Callable[[], str],
        auth_manager: Callable[[], Any],
        inventory_mapper: Callable[[dict[str, Any]], dict[str, Any]],
        diagnostic_fetcher: Callable[..., dict[str, Any]],
        base_url_normalizer: Callable[[str], str],
        reference_url_builder: Callable[[str, str], str],
        json_request: Callable[..., tuple[int, dict[str, Any]]],
        operation_outcome: Callable[[dict[str, Any]], dict[str, Any]],
        upstream_status: Callable[[str], int | None],
        record_sync: Callable[..., dict[str, Any]],
    ) -> None:
        self._repository = repository
        self._inventory_types = inventory_types
        self._medplum_base_url = medplum_base_url
        self._auth_manager = auth_manager
        self._inventory_mapper = inventory_mapper
        self._diagnostic_fetcher = diagnostic_fetcher
        self._base_url_normalizer = base_url_normalizer
        self._reference_url_builder = reference_url_builder
        self._json_request = json_request
        self._operation_outcome = operation_outcome
        self._upstream_status = upstream_status
        self._record_sync = record_sync

    def operation_outcome(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._operation_outcome(payload)

    def mappings(self) -> list[dict[str, Any]]:
        return self._repository.list_fhir_resource_mappings()

    def records(self, sync_status: str = "") -> list[dict[str, Any]]:
        return [
            item
            for item in self._repository.list_fhir_workflow_records(sync_status)
            if item["resourceType"] != "Task"
        ]

    def inventory(self, sync_status: str = "", resource_type: str = "") -> dict[str, Any]:
        if resource_type and resource_type not in self._inventory_types:
            raise ValueError("FHIR resource type is not supported by Medplum inventory.")
        records = [
            item
            for item in self._repository.list_fhir_workflow_records(sync_status)
            if item["resourceType"] in self._inventory_types
            and (not resource_type or item["resourceType"] == resource_type)
        ]
        items = [self._inventory_mapper(item) for item in records]
        patients = [
            {
                "id": item["id"],
                "localFhirRecordNumber": item["localFhirRecordNumber"],
                "localSourceId": item["localSourceId"],
                "identifier": item["identifier"],
                "medplum": item["medplum"],
                "sync": item["sync"],
                "reference": item["medplum"].get("reference") or "",
            }
            for item in items
            if item["resourceType"] == "Patient"
        ]
        return {
            "items": items,
            "patients": patients,
            "resourceTypes": list(self._inventory_types),
        }

    def diagnostic_reports(
        self,
        *,
        patient_reference: str = "",
        service_request_reference: str = "",
        base_url: str = "",
    ) -> dict[str, Any]:
        resolved_base_url = str(base_url or self._medplum_base_url()).strip()
        if not resolved_base_url:
            raise ValueError("Medplum FHIR base URL is required.")
        return self._diagnostic_fetcher(
            resolved_base_url,
            "",
            patient_reference=patient_reference,
            service_request_reference=service_request_reference,
            auth_manager=self._auth_manager(),
        )

    def _fetch_live_reference(
        self, reference: str, base_url: str
    ) -> tuple[int, dict[str, Any]]:
        base = self._base_url_normalizer(base_url)
        return self._json_request(
            self._reference_url_builder(base, reference),
            "",
            auth_manager=self._auth_manager(),
            base_url=base,
        )

    def resource_preview(self, reference: str, base_url: str = "") -> dict[str, Any]:
        resolved_base_url = str(base_url or self._medplum_base_url()).strip()
        if not resolved_base_url:
            raise ValueError("Medplum FHIR base URL is required.")
        status_code, resource = self._fetch_live_reference(reference, resolved_base_url)
        return {
            "source": "medplum-live",
            "reference": reference,
            "statusCode": status_code,
            "resource": resource,
        }

    def create_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._repository.create_fhir_workflow_record(payload)

    def _raw_record(self, record_id: int) -> dict[str, Any]:
        return self._repository.get_fhir_workflow_record(record_id)

    def get_record(self, record_id: int) -> dict[str, Any]:
        item = self._raw_record(record_id)
        if item["resourceType"] == "Task":
            raise ValueError("FHIR Task workflow records are no longer supported.")
        return item

    def record_preview(self, record_id: int) -> dict[str, Any]:
        item = self._raw_record(record_id)
        if item["resourceType"] not in self._inventory_types:
            raise ValueError("FHIR resource type is not supported by Medplum inventory.")
        sync_status = (item.get("sync") or {}).get("status")
        reference = str((item.get("medplum") or {}).get("reference") or "").strip()
        fallback = item.get("resource") or {}
        if sync_status == FHIR_SYNC_STATUS_SYNCED and reference:
            try:
                status_code, resource = self._fetch_live_reference(
                    reference, self._medplum_base_url()
                )
                return {
                    "item": item,
                    "resource": resource,
                    "source": "medplum-live",
                    "live": {
                        "fetched": True,
                        "statusCode": status_code,
                        "reference": reference,
                        "error": "",
                    },
                }
            except (ValidationError, SimulatorValidationError, UpstreamFhirError) as exc:
                return {
                    "item": item,
                    "resource": fallback,
                    "source": "local-submitted-fallback",
                    "live": {
                        "fetched": False,
                        "statusCode": self._upstream_status(str(exc)),
                        "reference": reference,
                        "error": str(exc),
                    },
                }
        return {
            "item": item,
            "resource": fallback,
            "source": "local-submitted",
            "live": {
                "fetched": False,
                "statusCode": None,
                "reference": reference,
                "error": "",
            },
        }

    def attempts(self, record_id: int) -> list[dict[str, Any]]:
        self._raw_record(record_id)
        return self._repository.list_fhir_sync_attempts(record_id)

    def sync_record(
        self, record_id: int, base_url: str = ""
    ) -> tuple[bool, dict[str, Any]]:
        resolved_base_url = str(base_url or self._medplum_base_url()).strip()
        if not resolved_base_url:
            raise ValueError("Medplum FHIR base URL is required.")
        current = self._raw_record(record_id)
        if current["resourceType"] == "Task":
            raise ValueError("FHIR Task workflow records are no longer supported.")
        item = self._record_sync(
            self._repository,
            record_id,
            base_url=resolved_base_url,
            auth_manager=self._auth_manager(),
        )
        return item["sync"]["status"] == FHIR_SYNC_STATUS_SYNCED, item


def medplum_identifier_search_url(base_url: str, record: dict[str, Any]) -> str:
    identifier = record["identifier"]
    token = f"{identifier['system']}|{identifier['value']}"
    query = urllib.parse.urlencode({"identifier": token})
    return f"{base_url}/{record['resourceType']}?{query}"


def medplum_create_resource_url(base_url: str, record: dict[str, Any]) -> str:
    return f"{base_url}/{record['resourceType']}"


def medplum_update_resource_url(base_url: str, record: dict[str, Any], resource_id: str) -> str:
    return f"{base_url}/{record['resourceType']}/{urllib.parse.quote(resource_id, safe='')}"


def first_fhir_bundle_resource(bundle: dict[str, Any], resource_type: str) -> dict[str, Any] | None:
    if bundle.get("resourceType") != "Bundle":
        return None
    for entry in bundle.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource")
        if isinstance(resource, dict) and resource.get("resourceType") == resource_type:
            return resource
    return None


def medplum_resource_reference(resource: dict[str, Any], resource_type: str) -> tuple[str, str]:
    resource_id = str(resource.get("id") or "").strip()
    if not resource_id:
        raise UpstreamFhirError(f"Medplum {resource_type} response did not include an id.")
    return resource_id, f"{resource_type}/{resource_id}"


def sync_fhir_workflow_record_to_medplum(
    store: FhirRepositoryPort,
    record_id: int,
    *,
    base_url: str,
    auth_manager: MedplumAuthManager,
) -> dict[str, Any]:
    base = normalize_fhir_base_url(base_url)
    current_record = store.get_fhir_workflow_record(record_id)
    original_sync_status = current_record.get("sync", {}).get("status")
    record = store.mark_fhir_syncing(record_id)
    search_url = medplum_identifier_search_url(base, record)

    def sync_request(
        request_url: str,
        *,
        method: str,
        request_payload: dict[str, Any] | None = None,
        body: bytes | None = None,
        content_type: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        try:
            return request_fhir_json(
                request_url,
                "",
                method=method,
                body=body,
                content_type=content_type,
                auth_manager=auth_manager,
                base_url=base,
            )
        except (UpstreamFhirError, ValidationError, SimulatorValidationError) as exc:
            message = str(exc)
            response_payload = (
                exc.response_payload if isinstance(exc, UpstreamFhirError) else {}
            )
            http_status = (
                exc.http_status
                if isinstance(exc, UpstreamFhirError)
                else http_status_from_upstream_error(message)
            )
            outcome = (
                operation_outcome_from_payload(response_payload)
                or operation_outcome_from_error(message)
            )
            store.record_fhir_sync_attempt(
                record_id,
                method=method,
                request_url=request_url,
                request_payload=request_payload or {},
                http_status=http_status,
                response_payload=response_payload,
                operation_outcome=outcome,
                error_text=message,
            )
            if isinstance(exc, UpstreamFhirError):
                exc.attempt_recorded = True
            else:
                setattr(exc, "attempt_recorded", True)
            raise

    try:
        status_code, search_body = sync_request(
            search_url,
            method="GET",
        )
        store.record_fhir_sync_attempt(
            record_id,
            method="GET",
            request_url=search_url,
            http_status=status_code,
            response_payload=search_body,
            operation_outcome=operation_outcome_from_payload(search_body),
        )
        existing = first_fhir_bundle_resource(search_body, record["resourceType"])
        if existing:
            medplum_id, reference = medplum_resource_reference(existing, record["resourceType"])
            return store.mark_fhir_sync_success(
                record_id,
                medplum_resource_id=medplum_id,
                medplum_resource_reference=reference,
            )

        stored_medplum = record.get("medplum") or {}
        stored_medplum_id = str(stored_medplum.get("id") or "").strip()
        if stored_medplum_id:
            if original_sync_status == FHIR_SYNC_STATUS_SYNCED:
                return store.mark_fhir_sync_success(
                    record_id,
                    medplum_resource_id=stored_medplum_id,
                    medplum_resource_reference=str(stored_medplum.get("reference") or "").strip(),
                )
            update_payload = dict(record["resource"])
            update_payload["id"] = stored_medplum_id
            update_url = medplum_update_resource_url(base, record, stored_medplum_id)
            update_status, update_body = sync_request(
                update_url,
                method="PUT",
                request_payload=update_payload,
                body=json.dumps(update_payload).encode("utf-8"),
                content_type="application/fhir+json",
            )
            store.record_fhir_sync_attempt(
                record_id,
                method="PUT",
                request_url=update_url,
                request_payload=update_payload,
                http_status=update_status,
                response_payload=update_body,
                operation_outcome=operation_outcome_from_payload(update_body),
            )
            medplum_id, reference = medplum_resource_reference(update_body, record["resourceType"])
            return store.mark_fhir_sync_success(
                record_id,
                medplum_resource_id=medplum_id,
                medplum_resource_reference=reference,
            )

        create_url = medplum_create_resource_url(base, record)
        request_payload = record["resource"]
        create_status, create_body = sync_request(
            create_url,
            method="POST",
            request_payload=request_payload,
            body=json.dumps(request_payload).encode("utf-8"),
            content_type="application/fhir+json",
        )
        store.record_fhir_sync_attempt(
            record_id,
            method="POST",
            request_url=create_url,
            request_payload=request_payload,
            http_status=create_status,
            response_payload=create_body,
            operation_outcome=operation_outcome_from_payload(create_body),
        )
        medplum_id, reference = medplum_resource_reference(create_body, record["resourceType"])
        return store.mark_fhir_sync_success(
            record_id,
            medplum_resource_id=medplum_id,
            medplum_resource_reference=reference,
        )
    except (UpstreamFhirError, ValidationError, SimulatorValidationError) as exc:
        message = str(exc)
        outcome = operation_outcome_from_error(message)
        if not getattr(exc, "attempt_recorded", False):
            store.record_fhir_sync_attempt(
                record_id,
                method="SYNC",
                request_url=search_url,
                request_payload=record.get("resource") or {},
                http_status=http_status_from_upstream_error(message),
                operation_outcome=outcome,
                error_text=message,
            )
        return store.mark_fhir_sync_failure(
            record_id,
            error_text=message,
            operation_outcome=outcome,
        )


def fetch_fhir_service_requests(
    base_url: str,
    token: str,
    *,
    auth_manager: MedplumAuthManager | None = None,
) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        [
            ("_count", 20),
            ("_sort", "-_lastUpdated"),
            ("_include", "ServiceRequest:subject"),
            ("_include", "ServiceRequest:encounter"),
            ("_include", "ServiceRequest:requester"),
            ("_include", "ServiceRequest:performer"),
        ]
    )
    url = f"{base_url}/ServiceRequest?{query}"
    status_code, parsed_body = request_fhir_json(
        url, token, auth_manager=auth_manager, base_url=base_url
    )
    return {
        "resourceType": str(parsed_body.get("resourceType", "")).strip() or "Bundle",
        "status": status_code,
        "body": parsed_body,
        "requestUrl": url,
    }


def normalize_fhir_reference(value: str, resource_type: str) -> str:
    reference = value.strip()
    parts = [part.strip() for part in reference.split("/") if part.strip()]
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
    resources: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource")
        if isinstance(resource, dict) and resource.get("resourceType") == resource_type:
            resources.append(resource)
    return resources


def service_request_references(references: list[str]) -> list[str]:
    return [reference for reference in references if reference.startswith("ServiceRequest/")]


def diagnostic_report_effective_date(resource: dict[str, Any]) -> str:
    effective = str(resource.get("effectiveDateTime") or "").strip()
    if effective:
        return effective
    effective_period = resource.get("effectivePeriod")
    if isinstance(effective_period, dict):
        return str(
            effective_period.get("start")
            or effective_period.get("end")
            or ""
        ).strip()
    return str(resource.get("issued") or "").strip()


def attachment_reference_values(value: Any) -> list[str]:
    references: list[str] = []
    if isinstance(value, dict):
        url = str(value.get("url") or "").strip()
        if url and re.match(r"^[A-Za-z]+/[A-Za-z0-9\-.]+$", url):
            references.append(url)
        for nested in value.values():
            for reference in attachment_reference_values(nested):
                if reference not in references:
                    references.append(reference)
    elif isinstance(value, list):
        for item in value:
            for reference in attachment_reference_values(item):
                if reference not in references:
                    references.append(reference)
    return references


def diagnostic_report_relationships(resource: dict[str, Any]) -> dict[str, Any]:
    media_references: list[str] = []
    for item in resource.get("media") or []:
        if isinstance(item, dict):
            media_references.extend(fhir_reference_values(item.get("link")))
    presented_form = resource.get("presentedForm") if isinstance(resource.get("presentedForm"), list) else []
    presented_form_references = attachment_reference_values(presented_form)
    related_references: list[dict[str, str]] = []
    for reference in all_fhir_references(resource) + presented_form_references:
        resource_type = reference.split("/", 1)[0] if "/" in reference else ""
        if resource_type not in {"Observation", "DocumentReference", "Binary"}:
            continue
        if any(item["reference"] == reference for item in related_references):
            continue
        related_references.append({"resourceType": resource_type, "reference": reference})
    return {
        "subject": fhir_reference_values(resource.get("subject")),
        "basedOn": fhir_reference_values(resource.get("basedOn")),
        "result": fhir_reference_values(resource.get("result")),
        "media": media_references,
        "presentedForm": presented_form_references,
        "related": related_references,
    }


def diagnostic_report_summary(
    resource: dict[str, Any],
    *,
    selected_service_request: str = "",
) -> dict[str, Any]:
    resource_id = str(resource.get("id") or "").strip()
    reference = f"DiagnosticReport/{resource_id}" if resource_id else ""
    relationships = diagnostic_report_relationships(resource)
    based_on = relationships["basedOn"]
    service_refs = service_request_references(based_on)
    result_refs = relationships["result"]
    attachment_count = len(relationships["media"]) + len(relationships["presentedForm"])
    relationship_type = (
        "order-linked"
        if service_refs and (not selected_service_request or selected_service_request in service_refs)
        else "patient-level"
    )
    return {
        "id": resource_id,
        "reference": reference,
        "resourceType": "DiagnosticReport",
        "code": first_code_text(resource.get("code")),
        "display": first_code_text(resource.get("code")) or reference or "DiagnosticReport",
        "status": str(resource.get("status") or "").strip(),
        "date": diagnostic_report_effective_date(resource),
        "issued": str(resource.get("issued") or "").strip(),
        "subject": relationships["subject"][0] if relationships["subject"] else "",
        "basedOn": based_on,
        "linkedOrder": service_refs[0] if service_refs else "",
        "relationshipType": relationship_type,
        "resultCount": len(result_refs),
        "attachmentCount": attachment_count,
        "relationships": relationships,
        "resource": resource,
    }


def fetch_fhir_diagnostic_report_bundle(
    base_url: str,
    token: str,
    *,
    patient_reference: str = "",
    service_request_reference: str = "",
    auth_manager: MedplumAuthManager | None = None,
) -> dict[str, Any]:
    base = normalize_fhir_base_url(base_url)
    patient_ref = normalize_fhir_reference(patient_reference, "Patient") if patient_reference else ""
    service_ref = (
        normalize_fhir_reference(service_request_reference, "ServiceRequest")
        if service_request_reference
        else ""
    )
    if not patient_ref and not service_ref:
        raise ValidationError("Patient or ServiceRequest reference is required.")

    def search(params: list[tuple[str, str]]) -> dict[str, Any]:
        query = urllib.parse.urlencode([("_count", "50"), ("_sort", "-date"), *params])
        url = f"{base}/DiagnosticReport?{query}"
        status_code, parsed_body = request_fhir_json(
            url, token, auth_manager=auth_manager, base_url=base
        )
        fhir_bundle_resources(parsed_body, "DiagnosticReport")
        return {"status": status_code, "body": parsed_body, "requestUrl": url}

    patient_fetch: dict[str, Any] | None = None
    patient_reports: list[dict[str, Any]] = []
    based_on_fetch: dict[str, Any] | None = None
    fallback_reason = ""
    report_resources: list[dict[str, Any]] = []
    strategy = "patient"

    def fetch_patient_reports(*, optional: bool = False) -> list[dict[str, Any]]:
        nonlocal patient_fetch, fallback_reason
        if not patient_ref:
            return []
        try:
            patient_fetch = search([("subject", patient_ref)])
            return fhir_bundle_resources(patient_fetch["body"], "DiagnosticReport")
        except UpstreamFhirError as exc:
            if not optional or exc.http_status not in {400, 404, 422}:
                raise
            fallback_reason = str(exc)
            return []

    if service_ref:
        try:
            based_on_fetch = search([("based-on", service_ref)])
            order_reports = fhir_bundle_resources(based_on_fetch["body"], "DiagnosticReport")
            patient_reports = fetch_patient_reports(optional=True)
            patient_level_reports = [
                item for item in patient_reports
                if not service_request_references(fhir_reference_values(item.get("basedOn")))
            ]
            by_reference: dict[str, dict[str, Any]] = {}
            for item in order_reports + patient_level_reports:
                item_id = str(item.get("id") or "").strip()
                key = f"DiagnosticReport/{item_id}" if item_id else json.dumps(item, sort_keys=True)
                by_reference[key] = item
            report_resources = list(by_reference.values())
            strategy = "based-on"
        except UpstreamFhirError as exc:
            if exc.http_status not in {400, 404, 422}:
                raise
            fallback_reason = str(exc)
            patient_reports = fetch_patient_reports()
            report_resources = [
                item for item in patient_reports
                if service_ref in fhir_reference_values(item.get("basedOn"))
                or not service_request_references(fhir_reference_values(item.get("basedOn")))
            ]
            strategy = "patient-filter"
    else:
        patient_reports = fetch_patient_reports()
        report_resources = patient_reports

    summaries = [
        diagnostic_report_summary(item, selected_service_request=service_ref)
        for item in report_resources
    ]
    return {
        "resourceType": "Bundle",
        "status": patient_fetch["status"] if patient_fetch else based_on_fetch["status"],
        "requestUrl": patient_fetch["requestUrl"] if patient_fetch else based_on_fetch["requestUrl"],
        "patientReference": patient_ref,
        "serviceRequestReference": service_ref,
        "strategy": strategy,
        "fallbackReason": fallback_reason,
        "empty": not summaries,
        "body": patient_fetch["body"] if patient_fetch else based_on_fetch["body"],
        "bundles": {
            "patient": patient_fetch,
            "basedOn": based_on_fetch,
        },
        "reports": summaries,
    }


def operation_outcome_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict) and payload.get("resourceType") == "OperationOutcome":
        return payload
    return {}


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


# Compatibility names backed by framework-independent domain implementations.
normalize_fhir_reference = fhir_domain.normalize_fhir_reference
fhir_bundle_resources = fhir_domain.fhir_bundle_resources
service_request_references = fhir_domain.service_request_references
diagnostic_report_effective_date = fhir_domain.diagnostic_report_effective_date
attachment_reference_values = fhir_domain.attachment_reference_values
operation_outcome_from_payload = fhir_domain.operation_outcome_from_payload
operation_outcome_from_error = fhir_domain.operation_outcome_from_error
http_status_from_upstream_error = fhir_domain.http_status_from_upstream_error


def medplum_reference_resource_url(base_url: str, reference: str) -> str:
    parts = [part.strip() for part in reference.strip().split("/") if part.strip()]
    if len(parts) != 2:
        raise ValidationError("Medplum resource reference must look like ResourceType/id.")
    resource_type, resource_id = parts
    if resource_type not in MEDPLUM_READ_RESOURCE_TYPES:
        raise ValidationError("Medplum resource reference type is not supported.")
    return (
        f"{base_url}/{urllib.parse.quote(resource_type, safe='')}/"
        f"{urllib.parse.quote(resource_id, safe='')}"
    )


def fhir_reference_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, dict):
        reference = str(value.get("reference") or "").strip()
        return [reference] if reference else []
    if isinstance(value, list):
        references: list[str] = []
        for item in value:
            references.extend(fhir_reference_values(item))
        return references
    return []


def direct_patient_references(resource: dict[str, Any]) -> list[str]:
    references: list[str] = []
    for field_name in MEDPLUM_PATIENT_REFERENCE_FIELDS:
        for reference in fhir_reference_values(resource.get(field_name)):
            if reference.startswith("Patient/") and reference not in references:
                references.append(reference)
    return references


def all_fhir_references(value: Any) -> list[str]:
    references: list[str] = []
    if isinstance(value, dict):
        reference = str(value.get("reference") or "").strip()
        if reference and reference not in references:
            references.append(reference)
        for nested in value.values():
            for nested_reference in all_fhir_references(nested):
                if nested_reference not in references:
                    references.append(nested_reference)
    elif isinstance(value, list):
        for item in value:
            for nested_reference in all_fhir_references(item):
                if nested_reference not in references:
                    references.append(nested_reference)
    return references


def first_code_text(value: Any) -> str:
    if isinstance(value, dict):
        text = str(value.get("text") or "").strip()
        if text:
            return text
        coding = value.get("coding")
        if isinstance(coding, list):
            for item in coding:
                if not isinstance(item, dict):
                    continue
                display = str(item.get("display") or item.get("code") or "").strip()
                if display:
                    return display
    return ""


def fhir_resource_summary(resource: dict[str, Any], reference: str) -> dict[str, str]:
    resource_type = str(resource.get("resourceType") or "").strip()
    status = str(resource.get("status") or "").strip()
    code = first_code_text(resource.get("code"))
    title = str(resource.get("title") or resource.get("description") or "").strip()
    if resource_type == "Patient":
        names = resource.get("name") if isinstance(resource.get("name"), list) else []
        name = ""
        for item in names:
            if not isinstance(item, dict):
                continue
            name = str(item.get("text") or "").strip()
            if not name:
                given = " ".join(str(value).strip() for value in item.get("given") or [] if str(value).strip())
                family = str(item.get("family") or "").strip()
                name = " ".join(value for value in (given, family) if value)
            if name:
                break
        identifiers = resource.get("identifier") if isinstance(resource.get("identifier"), list) else []
        mrn = ""
        for item in identifiers:
            if isinstance(item, dict) and str(item.get("value") or "").strip():
                mrn = str(item.get("value")).strip()
                break
        return {"primary": name or mrn or reference or "Patient", "secondary": mrn, "status": status}
    if resource_type == "DiagnosticReport":
        return {
            "primary": code or title or reference or "DiagnosticReport",
            "secondary": str(resource.get("issued") or resource.get("effectiveDateTime") or "").strip(),
            "status": status,
        }
    if resource_type == "Observation":
        value = ""
        if "valueQuantity" in resource and isinstance(resource["valueQuantity"], dict):
            quantity = resource["valueQuantity"]
            value = " ".join(
                str(part).strip()
                for part in (quantity.get("value"), quantity.get("unit") or quantity.get("code"))
                if str(part or "").strip()
            )
        return {"primary": code or reference or "Observation", "secondary": value, "status": status}
    if resource_type == "DocumentReference":
        return {"primary": title or code or reference or "DocumentReference", "secondary": str(resource.get("docStatus") or "").strip(), "status": status}
    return {"primary": code or title or reference or resource_type, "secondary": "", "status": status}


def medplum_inventory_record(record: dict[str, Any]) -> dict[str, Any]:
    sync_status = str((record.get("sync") or {}).get("status") or "")
    medplum = record.get("medplum") or {}
    reference = str(medplum.get("reference") or "").strip()
    resource = record.get("resource") if isinstance(record.get("resource"), dict) else {}
    patient_references = direct_patient_references(resource)
    if record.get("resourceType") == "Patient" and reference and reference not in patient_references:
        patient_references.insert(0, reference)
    references = all_fhir_references(resource)
    return {
        "id": record["id"],
        "localFhirRecordNumber": record["localFhirRecordNumber"],
        "localSourceType": record["localSourceType"],
        "localSourceId": record["localSourceId"],
        "resourceType": record["resourceType"],
        "identifier": record["identifier"],
        "patientReferences": patient_references,
        "references": references,
        "summary": fhir_resource_summary(resource, reference),
        "medplum": medplum,
        "sync": record["sync"],
        "createdAt": record["createdAt"],
        "updatedAt": record["updatedAt"],
        "retryable": sync_status in (FHIR_SYNC_STATUS_PENDING, FHIR_SYNC_STATUS_FAILED),
        "previewSource": (
            "medplum-live"
            if sync_status == FHIR_SYNC_STATUS_SYNCED and reference
            else "local-submitted"
        ),
    }
