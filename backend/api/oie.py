"""OIE HTTP request and response mapping."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.domain.errors import SimulatorValidationError, ValidationError
from backend.services.oie_settings import OieSettingsService
from backend.services.oie_workflow import OieTransportError, OieWorkflowService


def create_oie_blueprint(
    settings: OieSettingsService, workflow: OieWorkflowService
) -> Blueprint:
    blueprint = Blueprint("oie", __name__)

    def error(message: str, status: int):
        return jsonify({"success": False, "error": message}), status

    @blueprint.get("/api/oie/settings")
    def get_oie_settings():
        return jsonify({"success": True, "item": settings.get_profile()})

    @blueprint.put("/api/oie/settings")
    def update_oie_settings():
        try:
            result = settings.update_profile(request.get_json(silent=True))
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({
            "success": True,
            "item": result.profile,
            "runtimeReloadRequired": result.runtime_reload_required,
        })

    @blueprint.get("/api/oie/local-adt-patients")
    def list_oie_local_adt_patients():
        return jsonify({
            "success": True,
            "localOnly": True,
            "message": "Local ADT inventory only; messages are not transmitted to OIE.",
            "items": workflow.local_adt_inventory(),
        })

    @blueprint.get("/api/oie/local-orders")
    def list_oie_local_orders():
        return jsonify({
            "success": True,
            "localOnly": True,
            "message": "Local ORM inventory. Send Order transmits one selected order to the configured OIE MLLP endpoint.",
            "items": workflow.local_order_inventory(),
        })

    @blueprint.get("/api/oie/workbench")
    def oie_workbench():
        return jsonify({"success": True, **workflow.workbench()})

    @blueprint.get("/api/oie/results")
    def oie_results():
        return jsonify({"success": True, "items": workflow.results()})

    @blueprint.post("/api/oie/results")
    def receive_oie_result():
        payload = request.get_data(as_text=True)
        if request.is_json:
            payload = str((request.get_json(silent=True) or {}).get("payload") or "")
        try:
            ack, item, status_code = workflow.receive_result(payload)
        except ValueError as exc:
            return error(str(exc), 400)
        return jsonify({"success": status_code < 400, "item": item, "ack": ack}), status_code

    @blueprint.get("/api/oie/result-listener/status")
    def oie_result_listener_status():
        return jsonify({"success": True, "item": workflow.listener_status()})

    @blueprint.post("/api/oie/result-listener/start")
    def start_oie_result_listener():
        try:
            item = workflow.start_listener()
        except (ValueError, ValidationError) as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item})

    @blueprint.post("/api/oie/result-listener/retry")
    def retry_oie_result_listener():
        try:
            item = workflow.retry_listener()
        except (ValueError, ValidationError) as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item})

    @blueprint.post("/api/oie/result-listener/stop")
    def stop_oie_result_listener():
        return jsonify({"success": True, "item": workflow.stop_listener()})

    @blueprint.post("/api/oie/local-orders/<int:order_id>/send")
    def send_oie_local_order(order_id: int):
        try:
            item = workflow.send_order(order_id, request.get_json(silent=True) or {})
        except KeyError:
            return error("Order record was not found.", 404)
        except ValueError as exc:
            return error(str(exc), 400)
        except OieTransportError as exc:
            return jsonify({"success": False, "item": exc.item, "error": str(exc)}), 502
        return jsonify({"success": True, "item": item})

    return blueprint
