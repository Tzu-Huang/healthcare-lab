"""FHIR workflow, inventory, preview, and diagnostics HTTP mapping."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from flask import Blueprint, jsonify, request

from backend.domain.errors import SimulatorValidationError, UpstreamFhirError, ValidationError

class FhirRecordsPort(Protocol):
    def create_record(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def get_record(self, record_id: int) -> dict[str, Any]: ...


class FhirInventoryPort(Protocol):
    def mappings(self) -> list[dict[str, Any]]: ...
    def records(self, sync_status: str = "") -> list[dict[str, Any]]: ...
    def inventory(self, sync_status: str = "", resource_type: str = "") -> dict[str, Any]: ...


class FhirPreviewPort(Protocol):
    def resource_preview(self, reference: str, base_url: str = "") -> dict[str, Any]: ...
    def record_preview(self, record_id: int) -> dict[str, Any]: ...


class FhirDiagnosticPort(Protocol):
    def diagnostic_reports(self, *, patient_reference: str = "", service_request_reference: str = "", base_url: str = "") -> dict[str, Any]: ...


class FhirSyncPort(Protocol):
    def attempts(self, record_id: int) -> list[dict[str, Any]]: ...
    def sync_record(self, record_id: int, base_url: str = "") -> tuple[bool, dict[str, Any]]: ...


def create_fhir_blueprint(records: FhirRecordsPort, inventory: FhirInventoryPort, previews: FhirPreviewPort, diagnostics: FhirDiagnosticPort, sync: FhirSyncPort, operation_outcome: Callable[[dict[str, Any]], dict[str, Any]]) -> Blueprint:
    blueprint = Blueprint("fhir", __name__)

    def error(message: str, status: int):
        return jsonify({"success": False, "error": message}), status

    def upstream_error(exc: UpstreamFhirError, allowed_statuses: set[int]):
        status = exc.http_status if exc.http_status in allowed_statuses else 502
        return jsonify({
            "success": False,
            "error": str(exc),
            "statusCode": exc.http_status,
            "operationOutcome": operation_outcome(exc.response_payload),
            "response": exc.response_payload,
        }), status

    @blueprint.get("/api/fhir/mappings")
    def list_fhir_mappings():
        return jsonify({"success": True, "items": inventory.mappings()})

    @blueprint.get("/api/fhir/records")
    def list_fhir_records():
        sync_status = str(request.args.get("syncStatus") or "").strip()
        return jsonify({"success": True, "items": inventory.records(sync_status)})

    @blueprint.get("/api/fhir/inventory")
    def list_fhir_inventory():
        try:
            result = inventory.inventory(
                str(request.args.get("syncStatus") or "").strip(),
                str(request.args.get("resourceType") or "").strip(),
            )
        except ValueError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, **result})

    @blueprint.get("/api/fhir/diagnostic-reports")
    def fetch_diagnostic_reports():
        try:
            result = diagnostics.diagnostic_reports(
                patient_reference=str(
                    request.args.get("patient")
                    or request.args.get("patientReference")
                    or ""
                ).strip(),
                service_request_reference=str(
                    request.args.get("serviceRequest")
                    or request.args.get("serviceRequestReference")
                    or ""
                ).strip(),
                base_url=str(request.args.get("baseUrl") or "").strip(),
            )
        except (ValueError, ValidationError) as exc:
            return error(str(exc), 400)
        except UpstreamFhirError as exc:
            return upstream_error(exc, {401, 403})
        return jsonify({
            "success": True,
            "source": "medplum-live",
            "patientReference": result["patientReference"],
            "serviceRequestReference": result["serviceRequestReference"],
            "strategy": result["strategy"],
            "fallbackReason": result["fallbackReason"],
            "empty": result["empty"],
            "requestUrl": result["requestUrl"],
            "bundle": result["body"],
            "bundles": result["bundles"],
            "reports": result["reports"],
        })

    @blueprint.get("/api/fhir/resource-preview")
    def fetch_resource_preview():
        reference = str(request.args.get("reference") or "").strip()
        try:
            result = previews.resource_preview(
                reference, str(request.args.get("baseUrl") or "").strip()
            )
        except (ValueError, ValidationError) as exc:
            return error(str(exc), 400)
        except UpstreamFhirError as exc:
            return upstream_error(exc, {401, 403, 404})
        return jsonify({"success": True, **result})

    @blueprint.post("/api/fhir/records")
    def create_fhir_record():
        try:
            item = records.create_record(request.get_json(silent=True) or {})
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    @blueprint.get("/api/fhir/records/<int:record_id>")
    def get_fhir_record(record_id: int):
        try:
            item = records.get_record(record_id)
        except KeyError:
            return error("FHIR workflow record was not found.", 404)
        except ValueError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item})

    @blueprint.get("/api/fhir/records/<int:record_id>/preview")
    def get_fhir_record_preview(record_id: int):
        try:
            result = previews.record_preview(record_id)
        except KeyError:
            return error("FHIR workflow record was not found.", 404)
        except ValueError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, **result})

    @blueprint.get("/api/fhir/records/<int:record_id>/attempts")
    def list_fhir_record_attempts(record_id: int):
        try:
            items = sync.attempts(record_id)
        except KeyError:
            return error("FHIR workflow record was not found.", 404)
        except ValueError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "items": items})

    @blueprint.post("/api/fhir/records/<int:record_id>/sync")
    def sync_fhir_record(record_id: int):
        try:
            success, item = sync.sync_record(
                record_id,
                str((request.get_json(silent=True) or {}).get("baseUrl") or "").strip(),
            )
        except KeyError:
            return error("FHIR workflow record was not found.", 404)
        except (ValueError, ValidationError, SimulatorValidationError) as exc:
            return error(str(exc), 400)
        return jsonify({"success": success, "item": item})

    return blueprint
