"""FHIR workflow, inventory, preview, and diagnostics HTTP mapping."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Blueprint, jsonify, request

from backend.domain.errors import UpstreamFhirError, ValidationError
from backend.lab_store import DemoStore, FHIR_SYNC_STATUS_SYNCED, SimulatorValidationError


def create_fhir_blueprint(
    store: DemoStore,
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
) -> Blueprint:
    blueprint = Blueprint("fhir", __name__)

    def error(message: str, status: int):
        return jsonify({"success": False, "error": message}), status

    def get_record(record_id: int):
        try:
            return store.get_fhir_workflow_record(record_id), None
        except KeyError:
            return None, error("FHIR workflow record was not found.", 404)

    @blueprint.get("/api/fhir/mappings")
    def list_fhir_mappings():
        return jsonify({"success": True, "items": store.list_fhir_resource_mappings()})

    @blueprint.get("/api/fhir/records")
    def list_fhir_records():
        sync_status = str(request.args.get("syncStatus") or "").strip()
        records = [item for item in store.list_fhir_workflow_records(sync_status) if item["resourceType"] != "Task"]
        return jsonify({"success": True, "items": records})

    @blueprint.get("/api/fhir/inventory")
    def list_fhir_inventory():
        sync_status = str(request.args.get("syncStatus") or "").strip()
        resource_type = str(request.args.get("resourceType") or "").strip()
        if resource_type and resource_type not in inventory_types:
            return error("FHIR resource type is not supported by Medplum inventory.", 400)
        records = [
            item for item in store.list_fhir_workflow_records(sync_status)
            if item["resourceType"] in inventory_types and (not resource_type or item["resourceType"] == resource_type)
        ]
        items = [inventory_mapper(item) for item in records]
        patients = [
            {
                "id": item["id"], "localFhirRecordNumber": item["localFhirRecordNumber"],
                "localSourceId": item["localSourceId"], "identifier": item["identifier"],
                "medplum": item["medplum"], "sync": item["sync"],
                "reference": item["medplum"].get("reference") or "",
            }
            for item in items if item["resourceType"] == "Patient"
        ]
        return jsonify({"success": True, "items": items, "patients": patients, "resourceTypes": list(inventory_types)})

    @blueprint.get("/api/fhir/diagnostic-reports")
    def fetch_diagnostic_reports():
        patient = str(request.args.get("patient") or request.args.get("patientReference") or "").strip()
        service_request = str(request.args.get("serviceRequest") or request.args.get("serviceRequestReference") or "").strip()
        base_url = str(request.args.get("baseUrl") or medplum_base_url()).strip()
        if not base_url:
            return error("Medplum FHIR base URL is required.", 400)
        try:
            result = diagnostic_fetcher(
                base_url, "", patient_reference=patient,
                service_request_reference=service_request, auth_manager=auth_manager(),
            )
        except ValidationError as exc:
            return error(str(exc), 400)
        except UpstreamFhirError as exc:
            status = exc.http_status if exc.http_status in {401, 403} else 502
            return jsonify({
                "success": False, "error": str(exc), "statusCode": exc.http_status,
                "operationOutcome": operation_outcome(exc.response_payload), "response": exc.response_payload,
            }), status
        return jsonify({
            "success": True, "source": "medplum-live", "patientReference": result["patientReference"],
            "serviceRequestReference": result["serviceRequestReference"], "strategy": result["strategy"],
            "fallbackReason": result["fallbackReason"], "empty": result["empty"],
            "requestUrl": result["requestUrl"], "bundle": result["body"],
            "bundles": result["bundles"], "reports": result["reports"],
        })

    def fetch_live_reference(reference: str, base_url: str) -> tuple[int, dict[str, Any]]:
        base = base_url_normalizer(base_url)
        return json_request(
            reference_url_builder(base, reference), "", auth_manager=auth_manager(), base_url=base
        )

    @blueprint.get("/api/fhir/resource-preview")
    def fetch_resource_preview():
        reference = str(request.args.get("reference") or "").strip()
        base_url = str(request.args.get("baseUrl") or medplum_base_url()).strip()
        if not base_url:
            return error("Medplum FHIR base URL is required.", 400)
        try:
            status_code, resource = fetch_live_reference(reference, base_url)
        except ValidationError as exc:
            return error(str(exc), 400)
        except UpstreamFhirError as exc:
            status = exc.http_status if exc.http_status in {401, 403, 404} else 502
            return jsonify({
                "success": False, "error": str(exc), "statusCode": exc.http_status,
                "operationOutcome": operation_outcome(exc.response_payload), "response": exc.response_payload,
            }), status
        return jsonify({"success": True, "source": "medplum-live", "reference": reference, "statusCode": status_code, "resource": resource})

    @blueprint.post("/api/fhir/records")
    def create_fhir_record():
        try:
            item = store.create_fhir_workflow_record(request.get_json(silent=True) or {})
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    @blueprint.get("/api/fhir/records/<int:record_id>")
    def get_fhir_record(record_id: int):
        item, failure = get_record(record_id)
        if failure:
            return failure
        if item["resourceType"] == "Task":
            return error("FHIR Task workflow records are no longer supported.", 400)
        return jsonify({"success": True, "item": item})

    @blueprint.get("/api/fhir/records/<int:record_id>/preview")
    def get_fhir_record_preview(record_id: int):
        item, failure = get_record(record_id)
        if failure:
            return failure
        if item["resourceType"] not in inventory_types:
            return error("FHIR resource type is not supported by Medplum inventory.", 400)
        sync_status = (item.get("sync") or {}).get("status")
        reference = str((item.get("medplum") or {}).get("reference") or "").strip()
        fallback = item.get("resource") or {}
        if sync_status == FHIR_SYNC_STATUS_SYNCED and reference:
            try:
                status_code, resource = fetch_live_reference(reference, medplum_base_url())
                return jsonify({
                    "success": True, "item": item, "resource": resource, "source": "medplum-live",
                    "live": {"fetched": True, "statusCode": status_code, "reference": reference, "error": ""},
                })
            except (ValidationError, SimulatorValidationError, UpstreamFhirError) as exc:
                return jsonify({
                    "success": True, "item": item, "resource": fallback, "source": "local-submitted-fallback",
                    "live": {"fetched": False, "statusCode": upstream_status(str(exc)), "reference": reference, "error": str(exc)},
                })
        return jsonify({
            "success": True, "item": item, "resource": fallback, "source": "local-submitted",
            "live": {"fetched": False, "statusCode": None, "reference": reference, "error": ""},
        })

    @blueprint.get("/api/fhir/records/<int:record_id>/attempts")
    def list_fhir_record_attempts(record_id: int):
        _item, failure = get_record(record_id)
        return failure or jsonify({"success": True, "items": store.list_fhir_sync_attempts(record_id)})

    @blueprint.post("/api/fhir/records/<int:record_id>/sync")
    def sync_fhir_record(record_id: int):
        base_url = str((request.get_json(silent=True) or {}).get("baseUrl") or medplum_base_url()).strip()
        if not base_url:
            return error("Medplum FHIR base URL is required.", 400)
        try:
            current = store.get_fhir_workflow_record(record_id)
            if current["resourceType"] == "Task":
                return error("FHIR Task workflow records are no longer supported.", 400)
            item = record_sync(store, record_id, base_url=base_url, auth_manager=auth_manager())
        except KeyError:
            return error("FHIR workflow record was not found.", 404)
        except (ValidationError, SimulatorValidationError) as exc:
            return error(str(exc), 400)
        return jsonify({"success": item["sync"]["status"] == FHIR_SYNC_STATUS_SYNCED, "item": item})

    return blueprint
