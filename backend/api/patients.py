"""Patient workflow HTTP mapping."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Blueprint, Flask, jsonify, request

from backend.domain.errors import ValidationError
from backend.lab_store import DemoStore, FHIR_SYNC_STATUS_SYNCED, SimulatorValidationError


def create_patients_blueprint(
    app: Flask,
    store: DemoStore,
    *,
    medplum_base_url: Callable[[], str],
    auth_manager: Callable[[], Any],
    fhir_sync: Callable[..., Any],
    dicom_patient_sync: Callable[..., Any],
    dcm_result_refresh: Callable[..., dict[str, Any]],
    dcm_profile: Callable[[dict[str, Any]], dict[str, Any]],
) -> Blueprint:
    blueprint = Blueprint("patients", __name__)

    def error(message: str, status: int):
        return jsonify({"success": False, "error": message}), status

    @blueprint.get("/api/patients")
    def list_patients():
        version = str(request.args.get("protocolVersion") or "").strip()
        return jsonify({"success": True, "items": store.list_patient_records(version)})

    @blueprint.post("/api/patients")
    def create_patient():
        try:
            item = store.create_patient_record(request.get_json(silent=True) or {})
            if item["protocolVersion"] == "FHIR R4":
                record = store.create_patient_fhir_workflow_record(item)
                base_url = medplum_base_url()
                if base_url:
                    fhir_sync(store, int(record["id"]), base_url=base_url, auth_manager=auth_manager())
                else:
                    store.mark_fhir_sync_failure(int(record["id"]), error_text="Medplum FHIR base URL is required.")
                item = store.get_patient_record(int(item["id"]))
            elif item["protocolVersion"] == "DICOM":
                dicom_patient_sync(store, item, dcm_profile(app.config))
                item = store.get_patient_record(int(item["id"]))
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    @blueprint.post("/api/patients/<int:record_id>/fhir-sync")
    def sync_patient_fhir_record(record_id: int):
        try:
            item = store.get_patient_record(record_id)
        except KeyError:
            return error("Patient record was not found.", 404)
        if item["protocolVersion"] != "FHIR R4":
            return error("Patient record is not FHIR mode.", 400)
        record = item.get("fhir") or store.create_patient_fhir_workflow_record(item)
        base_url = medplum_base_url()
        if not base_url:
            return error("Medplum FHIR base URL is required.", 400)
        try:
            fhir_sync(
                store,
                int(record.get("recordId") or record["id"]),
                base_url=base_url,
                auth_manager=auth_manager(),
            )
        except (ValidationError, SimulatorValidationError) as exc:
            return error(str(exc), 400)
        item = store.get_patient_record(record_id)
        status = ((item.get("fhir") or {}).get("sync") or {}).get("status")
        return jsonify({"success": status == FHIR_SYNC_STATUS_SYNCED, "item": item})

    @blueprint.post("/api/patients/<int:record_id>/dcm4chee-results-refresh")
    def refresh_patient_dcm4chee_result_records(record_id: int):
        try:
            result = dcm_result_refresh(store, record_id, dcm_profile(app.config))
        except KeyError:
            return error("Patient record was not found.", 404)
        return jsonify(result)

    @blueprint.post("/api/dcm4chee/e2e-fixture")
    def create_dcm4chee_e2e_fixture():
        try:
            result = store.create_dcm4chee_e2e_demo_fixture(
                dcm_profile(app.config), uid_root=app.config["DCM4CHEE_UID_ROOT"]
            )
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, **result}), 201

    return blueprint
