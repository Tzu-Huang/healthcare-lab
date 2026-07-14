"""Order and dcm4chee MWL workflow HTTP mapping."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.domain.errors import SimulatorValidationError
from backend.services.order_workflow import OrderWorkflowService


def create_orders_blueprint(service: OrderWorkflowService) -> Blueprint:
    blueprint = Blueprint("orders", __name__)

    def error(message: str, status: int):
        return jsonify({"success": False, "error": message}), status

    def service_call(operation):
        try:
            return operation(), None
        except KeyError:
            return None, error("Order record was not found.", 404)
        except (ValueError, SimulatorValidationError) as exc:
            return None, error(str(exc), 400)

    @blueprint.get("/api/orders")
    def list_orders():
        return jsonify({"success": True, "items": service.list()})

    @blueprint.get("/api/orders/<int:order_id>")
    def get_order(order_id: int):
        item, failure = service_call(lambda: service.get(order_id))
        return failure or jsonify({"success": True, "item": item})

    @blueprint.post("/api/orders")
    def create_order():
        try:
            item = service.create(request.get_json(silent=True) or {})
        except KeyError:
            return error("Patient record was not found.", 404)
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    @blueprint.get("/api/orders/<int:order_id>/dcm4chee-attempts")
    def list_dcm4chee_attempts(order_id: int):
        items, failure = service_call(lambda: service.list_dcm4chee_attempts(order_id))
        return failure or jsonify({"success": True, "items": items})

    @blueprint.post("/api/orders/<int:order_id>/dcm4chee-sync")
    def sync_dcm4chee_order(order_id: int):
        result, failure = service_call(lambda: service.sync_dcm4chee(order_id))
        return failure or jsonify(result)

    @blueprint.post("/api/orders/<int:order_id>/dcm4chee-mwl-verify")
    def verify_dcm4chee_order(order_id: int):
        result, failure = service_call(lambda: service.verify_dcm4chee(order_id))
        return failure or jsonify(result)

    @blueprint.get("/api/orders/<int:order_id>/dcm4chee-e2e-evidence")
    def dcm4chee_evidence(order_id: int):
        evidence, failure = service_call(lambda: service.dcm4chee_evidence(order_id))
        return failure or jsonify({"success": True, "evidence": evidence})

    @blueprint.post("/api/orders/<int:order_id>/dcm4chee-simulated-ap-return")
    def dcm4chee_simulated_return(order_id: int):
        result, failure = service_call(
            lambda: service.create_dcm4chee_simulated_return(
                order_id, request.get_json(silent=True) or {}
            )
        )
        return failure or (jsonify({"success": True, **result}), 201)

    return blueprint
