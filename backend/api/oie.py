"""OIE HTTP request and response mapping."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.domain.errors import SimulatorValidationError, ValidationError
from backend.domain.oie_management import OieManagementError
from backend.services.oie_settings import OieSettingsService
from backend.services.oie_channel_lifecycle import LifecycleGuardError
from backend.services.oie_workflow import OieTransportError, OieWorkflowService


def create_oie_blueprint(
    settings: OieSettingsService, workflow: OieWorkflowService, lifecycle=None
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

    @blueprint.post("/api/oie/settings/test-connection")
    def test_oie_settings_connection():
        body = request.get_json(silent=True)
        if body not in (None, {}):
            return error("Connection test uses saved Settings and accepts no overrides.", 400)
        try:
            item = settings.test_connection()
        except OieManagementError as exc:
            return jsonify({
                "success": False,
                "errorCategory": exc.category.value,
                "error": exc.detail,
            }), 502
        return jsonify({"success": True, "item": item})

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

    if lifecycle is not None:
        @blueprint.get("/api/oie/managed-channels")
        def managed_channels():
            try:
                return jsonify({"success": True, "items": lifecycle.inspect()})
            except Exception as exc:
                category = getattr(getattr(exc, "category", None), "value", None) or getattr(exc, "category", "upstream")
                return jsonify({"success": False, "errorCategory": category, "error": "Managed Channel inspection failed."}), 502

        @blueprint.post("/api/oie/managed-channels/<logical_type>/previews/<operation>")
        def preview_managed_channel(logical_type: str, operation: str):
            body = request.get_json(silent=True)
            if body not in (None, {}):
                return error("Preview request does not accept mutation options.", 400)
            try:
                return jsonify({"success": True, "item": lifecycle.preview(logical_type, operation)})
            except LifecycleGuardError as exc:
                return jsonify({"success": False, "errorCategory": exc.category, "error": exc.detail}), 400

        @blueprint.post("/api/oie/managed-channels/<logical_type>/<operation>")
        def mutate_managed_channel(logical_type: str, operation: str):
            body = request.get_json(silent=True)
            if not isinstance(body, dict) or set(body) - {"previewToken", "confirmation"} or not isinstance(body.get("previewToken"), str):
                return error("Mutation requires only previewToken and optional confirmation.", 400)
            if operation != "delete" and "confirmation" in body:
                return error("Confirmation is accepted only for delete.", 400)
            try:
                item = lifecycle.execute(logical_type, operation, body["previewToken"], confirmation=body.get("confirmation", ""))
                return jsonify({"success": item["outcome"] == "success", "item": item})
            except LifecycleGuardError as exc:
                status = 409 if exc.requires_fresh_preview else 400
                return jsonify({"success": False, "errorCategory": exc.category, "error": exc.detail,
                                "requiresFreshPreview": exc.requires_fresh_preview}), status

    return blueprint
