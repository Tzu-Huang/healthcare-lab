"""Patient workflow HTTP mapping."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.domain.errors import ValidationError
from backend.lab_store import SimulatorValidationError
from backend.services.patient_workflow import PatientWorkflowService


def create_patients_blueprint(service: PatientWorkflowService) -> Blueprint:
    blueprint = Blueprint("patients", __name__)

    def error(message: str, status: int):
        return jsonify({"success": False, "error": message}), status

    @blueprint.get("/api/patients")
    def list_patients():
        version = str(request.args.get("protocolVersion") or "").strip()
        return jsonify({"success": True, "items": service.list(version)})

    @blueprint.post("/api/patients")
    def create_patient():
        try:
            item = service.create(request.get_json(silent=True) or {})
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    @blueprint.post("/api/patients/<int:record_id>/fhir-sync")
    def sync_patient_fhir_record(record_id: int):
        try:
            success, item = service.sync_fhir(record_id)
        except KeyError:
            return error("Patient record was not found.", 404)
        except (ValueError, ValidationError, SimulatorValidationError) as exc:
            return error(str(exc), 400)
        return jsonify({"success": success, "item": item})

    @blueprint.post("/api/patients/<int:record_id>/dcm4chee-results-refresh")
    def refresh_patient_dcm4chee_result_records(record_id: int):
        try:
            result = service.refresh_dcm4chee_results(record_id)
        except KeyError:
            return error("Patient record was not found.", 404)
        return jsonify(result)

    @blueprint.post("/api/dcm4chee/e2e-fixture")
    def create_dcm4chee_e2e_fixture():
        try:
            result = service.create_dcm4chee_fixture()
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, **result}), 201

    return blueprint
