"""Order and dcm4chee MWL workflow HTTP mapping."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Blueprint, Flask, jsonify, request

from backend.lab_store import (
    DCM4CHEE_MWL_STATUS_CREATED,
    DCM4CHEE_MWL_VERIFICATION_VERIFIED,
    DemoStore,
    SimulatorValidationError,
)


def create_orders_blueprint(
    app: Flask,
    store: DemoStore,
    *,
    medplum_base_url: Callable[[], str],
    auth_manager: Callable[[], Any],
    fhir_sync: Callable[..., Any],
    dcm_sync: Callable[..., Any],
    dcm_verify: Callable[..., dict[str, Any]],
    dcm_profile: Callable[[dict[str, Any]], dict[str, Any]],
) -> Blueprint:
    blueprint = Blueprint("orders", __name__)

    def error(message: str, status: int):
        return jsonify({"success": False, "error": message}), status

    def order_or_error(order_id: int):
        try:
            return store.get_order_record(order_id), None
        except KeyError:
            return None, error("Order record was not found.", 404)

    def dicom_order_or_error(order_id: int):
        item, failure = order_or_error(order_id)
        if failure:
            return None, failure
        if item["protocolVersion"] != "DICOM":
            return None, error("Order record is not DICOM MWL mode.", 400)
        return item, None

    @blueprint.get("/api/orders")
    def list_orders():
        return jsonify({"success": True, "items": store.list_order_records()})

    @blueprint.get("/api/orders/<int:order_id>")
    def get_order(order_id: int):
        item, failure = order_or_error(order_id)
        return failure or jsonify({"success": True, "item": item})

    @blueprint.post("/api/orders")
    def create_order():
        payload = request.get_json(silent=True) or {}
        try:
            mode = str(payload.get("mode") or "").strip().lower()
            if mode == "fhir":
                item = store.create_fhir_order_record(payload)
                record = store.create_order_service_request_fhir_workflow_record(item)
                base_url = medplum_base_url()
                if base_url:
                    fhir_sync(store, int(record["id"]), base_url=base_url, auth_manager=auth_manager())
                else:
                    store.mark_fhir_sync_failure(int(record["id"]), error_text="Medplum FHIR base URL is required.")
                item = store.get_order_record(int(item["id"]))
            elif mode == "dicom":
                item = store.create_dcm4chee_order_record(payload)
                dcm_sync(store, item, dcm_profile(app.config), uid_root=app.config["DCM4CHEE_UID_ROOT"])
                item = store.get_order_record(int(item["id"]))
            else:
                item = store.create_order_record(payload)
        except KeyError:
            return error("Patient record was not found.", 404)
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    @blueprint.get("/api/orders/<int:order_id>/dcm4chee-attempts")
    def list_dcm4chee_attempts(order_id: int):
        _item, failure = dicom_order_or_error(order_id)
        return failure or jsonify({"success": True, "items": store.list_dcm4chee_mwl_attempts(order_id)})

    @blueprint.post("/api/orders/<int:order_id>/dcm4chee-sync")
    def sync_dcm4chee_order(order_id: int):
        item, failure = dicom_order_or_error(order_id)
        if failure:
            return failure
        try:
            dcm_sync(store, item, dcm_profile(app.config), uid_root=app.config["DCM4CHEE_UID_ROOT"])
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        item = store.get_order_record(order_id)
        mwl = (item.get("dcm4chee") or {}).get("mwl") or {}
        return jsonify({
            "success": (mwl.get("mapping") or {}).get("status") == DCM4CHEE_MWL_STATUS_CREATED,
            "item": item, "mwl": mwl, "latestAttempt": mwl if mwl.get("id") else None,
        })

    @blueprint.post("/api/orders/<int:order_id>/dcm4chee-mwl-verify")
    def verify_dcm4chee_order(order_id: int):
        item, failure = dicom_order_or_error(order_id)
        if failure:
            return failure
        try:
            result = dcm_verify(store, item, dcm_profile(app.config))
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        item = store.get_order_record(order_id)
        mwl = (item.get("dcm4chee") or {}).get("mwl") or {}
        verification = (mwl.get("mapping") or {}).get("verification") or mwl.get("verification") or {}
        return jsonify({
            "success": verification.get("status") == DCM4CHEE_MWL_VERIFICATION_VERIFIED,
            "item": item, "mwl": mwl, "verification": verification, "latestAttempt": result.get("attempt"),
        })

    @blueprint.get("/api/orders/<int:order_id>/dcm4chee-e2e-evidence")
    def dcm4chee_evidence(order_id: int):
        _item, failure = dicom_order_or_error(order_id)
        if failure:
            return failure
        return jsonify({"success": True, "evidence": store.dcm4chee_e2e_evidence_for_order(order_id, dcm_profile(app.config))})

    @blueprint.post("/api/orders/<int:order_id>/dcm4chee-simulated-ap-return")
    def dcm4chee_simulated_return(order_id: int):
        item, failure = dicom_order_or_error(order_id)
        if failure:
            return failure
        payload = request.get_json(silent=True) or {}
        try:
            result = store.create_simulated_dcm4chee_ap_return(
                order_id, dcm_profile(app.config), result_type=str(payload.get("type") or "both"),
                artifact_url=str(payload.get("artifactUrl") or ""), artifact_path=str(payload.get("artifactPath") or ""),
            )
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        patient = store.get_patient_record(int(item["patientRecordId"]))
        return jsonify({"success": True, "patient": patient, **result}), 201

    return blueprint
