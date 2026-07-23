"""Patient workflow HTTP mapping."""

from __future__ import annotations

from typing import Any, Protocol

from flask import Blueprint, jsonify, request

from backend.domain.errors import SimulatorValidationError, ValidationError


class PatientRecordPort(Protocol):
    def list(self, protocol_version: str = "") -> list[dict[str, Any]]: ...
    def create(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class PatientFhirSyncPort(Protocol):
    def sync(self, record_id: int) -> tuple[bool, dict[str, Any]]: ...


class PatientResultRefreshPort(Protocol):
    def refresh(self, record_id: int) -> dict[str, Any]: ...


class DcmFixturePort(Protocol):
    def create(self) -> dict[str, Any]: ...


def create_patients_blueprint(records: PatientRecordPort, fhir_sync: PatientFhirSyncPort, result_refresh: PatientResultRefreshPort, fixture: DcmFixturePort) -> Blueprint:
    blueprint = Blueprint("patients", __name__)

    def error(message: str, status: int):
        return jsonify({"success": False, "error": message}), status

    @blueprint.get("/api/patients")
    def list_patients():
        version = str(request.args.get("protocolVersion") or "").strip()
        return jsonify({"success": True, "items": records.list(version)})

    @blueprint.post("/api/patients")
    def create_patient():
        try:
            item = records.create(request.get_json(silent=True) or {})
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    @blueprint.post("/api/patients/<int:record_id>/fhir-sync")
    def sync_patient_fhir_record(record_id: int):
        try:
            success, item = fhir_sync.sync(record_id)
        except KeyError:
            return error("Patient record was not found.", 404)
        except (ValueError, ValidationError, SimulatorValidationError) as exc:
            return error(str(exc), 400)
        return jsonify({"success": success, "item": item})

    @blueprint.post("/api/patients/<int:record_id>/dcm4chee-results-refresh")
    def refresh_patient_dcm4chee_result_records(record_id: int):
        try:
            result = result_refresh.refresh(record_id)
        except KeyError:
            return error("Patient record was not found.", 404)
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify(result)

    @blueprint.post("/api/dcm4chee/e2e-fixture")
    def create_dcm4chee_e2e_fixture():
        try:
            result = fixture.create()
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, **result}), 201

    return blueprint
