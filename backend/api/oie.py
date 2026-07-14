"""OIE HTTP request and response mapping."""

from __future__ import annotations

import socket
from collections.abc import Callable
from typing import Any

from flask import Blueprint, Flask, jsonify, request

from backend.domain.errors import ValidationError
from backend.lab_store import (
    DemoStore,
    ORDER_STATUS_ACCEPTED,
    ORDER_STATUS_ERROR,
    ORDER_STATUS_REJECTED,
    ORDER_STATUS_TRANSPORT_ERROR,
    SimulatorValidationError,
)
from backend.services.oie_settings import OieSettingsService


def create_oie_blueprint(
    app: Flask,
    store: DemoStore,
    service: OieSettingsService,
    *,
    result_handler: Callable[[DemoStore, str], tuple[str, dict[str, Any], int]],
    ack_parser: Callable[[str], dict[str, str]],
    order_sender_provider: Callable[[], Callable[..., str]],
) -> Blueprint:
    blueprint = Blueprint("oie", __name__)

    def error(message: str, status: int):
        return jsonify({"success": False, "error": message}), status

    @blueprint.get("/api/oie/settings")
    def get_oie_settings():
        return jsonify({"success": True, "item": service.get_profile()})

    @blueprint.put("/api/oie/settings")
    def update_oie_settings():
        payload = request.get_json(silent=True)
        try:
            item = service.update_profile(payload)
        except SimulatorValidationError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        return jsonify({"success": True, "item": item})

    @blueprint.get("/api/oie/local-adt-patients")
    def list_oie_local_adt_patients():
        return jsonify({
            "success": True,
            "localOnly": True,
            "message": "Local ADT inventory only; messages are not transmitted to OIE.",
            "items": store.list_oie_local_adt_inventory(),
        })

    @blueprint.get("/api/oie/local-orders")
    def list_oie_local_orders():
        return jsonify({
            "success": True,
            "localOnly": True,
            "message": "Local ORM inventory. Send Order transmits one selected order to the configured OIE MLLP endpoint.",
            "items": store.list_oie_local_order_inventory(),
        })

    @blueprint.get("/api/oie/workbench")
    def oie_workbench():
        return jsonify({"success": True, **store.list_oie_workbench()})

    @blueprint.get("/api/oie/results")
    def oie_results():
        return jsonify({"success": True, "items": store.list_oie_results()})

    @blueprint.post("/api/oie/results")
    def receive_oie_result():
        payload = request.get_data(as_text=True)
        if request.is_json:
            payload = str((request.get_json(silent=True) or {}).get("payload") or "")
        if not payload.strip():
            return error("HL7 payload is required.", 400)
        ack, item, status_code = result_handler(store, payload)
        return jsonify({"success": status_code < 400, "item": item, "ack": ack}), status_code

    @blueprint.get("/api/oie/result-listener/status")
    def oie_result_listener_status():
        return jsonify({"success": True, "item": app.extensions["oie_result_listener"].status()})

    @blueprint.post("/api/oie/result-listener/start")
    def start_oie_result_listener():
        listener = app.extensions["oie_result_listener"]
        payload = request.get_json(silent=True) or {}
        host = str(payload.get("host", app.config["OIE_MLLP_RESULT_HOST"]) or "").strip()
        try:
            port = int(payload.get("port", app.config["OIE_MLLP_RESULT_PORT"]))
        except (TypeError, ValueError):
            return error("Listener port must be numeric.", 400)
        try:
            item = listener.start(host=host, port=port, framing=bool(payload.get("mllpFraming", True)))
        except ValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item})

    @blueprint.post("/api/oie/result-listener/stop")
    def stop_oie_result_listener():
        return jsonify({"success": True, "item": app.extensions["oie_result_listener"].stop()})

    @blueprint.post("/api/oie/local-orders/<int:order_id>/send")
    def send_oie_local_order(order_id: int):
        payload = request.get_json(silent=True) or {}
        host = str(payload.get("host", app.config["OIE_MLLP_ORDER_HOST"]) or app.config["OIE_MLLP_ORDER_HOST"]).strip()
        try:
            port = int(payload.get("port", app.config["OIE_MLLP_ORDER_PORT"]) or app.config["OIE_MLLP_ORDER_PORT"])
            timeout_seconds = float(payload.get("timeoutSeconds", 5) or 5)
        except (TypeError, ValueError):
            return error("OIE port and timeout must be numeric.", 400)
        if not host:
            return error("OIE host is required.", 400)
        if not 1 <= port <= 65535:
            return error("OIE port must be between 1 and 65535.", 400)
        if timeout_seconds <= 0:
            return error("OIE timeout must be positive.", 400)
        try:
            order = store.get_order_record(order_id)
        except KeyError:
            return error("Order record was not found.", 404)
        try:
            ack_payload = order_sender_provider()(
                order["payload"], host=host, port=port, timeout_seconds=timeout_seconds,
                framing=bool(payload.get("mllpFraming", True)),
            )
            ack = ack_parser(ack_payload)
            status = ORDER_STATUS_ACCEPTED if ack["code"] == "AA" else (
                ORDER_STATUS_REJECTED if ack["code"] == "AR" else ORDER_STATUS_ERROR
            )
            item = store.update_order_send_result(
                order_id, order_status=status, ack_code=ack["code"],
                ack_control_id=ack["controlId"], ack_text=ack["text"], ack_payload=ack_payload,
            )
        except (OSError, socket.timeout, TimeoutError) as exc:
            item = store.update_order_send_result(
                order_id, order_status=ORDER_STATUS_TRANSPORT_ERROR, transport_error=str(exc)
            )
            return jsonify({"success": False, "item": item, "error": str(exc)}), 502
        return jsonify({"success": True, "item": item})

    return blueprint
