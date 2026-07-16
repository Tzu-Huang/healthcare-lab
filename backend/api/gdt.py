"""GDT order, bridge, watcher, and result HTTP mapping."""

from __future__ import annotations

from typing import Any, Protocol

from flask import Blueprint, jsonify, request

from backend.domain.errors import SimulatorValidationError, ValidationError
from backend.services.gdt_workflow import (
    GdtConfigurationConflict,
    GdtExportError,
)


class GdtOrderPort(Protocol):
    def list(self) -> list[dict[str, Any]]: ...
    def get(self, order_id: int) -> dict[str, Any]: ...
    def create(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class GdtBridgePort(Protocol):
    def bridge_config(self) -> dict[str, Any]: ...
    def update_bridge_config(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def write_6302(self, order_id: int) -> tuple[dict[str, Any], str]: ...
    def inbox_items(self) -> list[dict[str, Any]]: ...
    def import_bridge_file(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def watcher_status(self) -> dict[str, Any]: ...
    def start_watcher(self) -> dict[str, Any]: ...
    def stop_watcher(self) -> dict[str, Any]: ...


class GdtResultPort(Protocol):
    def workbench(self) -> dict[str, Any]: ...
    def create_demo_result(self, order_id: int) -> dict[str, Any]: ...
    def messages(self) -> list[dict[str, Any]]: ...
    def events(self, order_id: int) -> list[dict[str, Any]]: ...
    def import_result(self, payload: dict[str, Any]) -> dict[str, Any]: ...


def create_gdt_blueprint(orders: GdtOrderPort, bridge: GdtBridgePort, results: GdtResultPort) -> Blueprint:
    blueprint = Blueprint("gdt", __name__)

    def error(message: str, status: int):
        return jsonify({"success": False, "error": message}), status

    @blueprint.get("/api/gdt/orders")
    def list_orders():
        return jsonify({"success": True, "items": orders.list()})

    @blueprint.get("/api/gdt/orders/<int:order_id>")
    def get_order(order_id: int):
        try:
            item = orders.get(order_id)
        except KeyError:
            return error("GDT order was not found.", 404)
        return jsonify({"success": True, "item": item})

    @blueprint.post("/api/gdt/orders")
    def create_order():
        try:
            item = orders.create(request.get_json(silent=True) or {})
        except KeyError:
            return error("Patient record was not found.", 404)
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    @blueprint.get("/api/gdt/bridge/config")
    def get_config():
        return jsonify({"success": True, "item": bridge.bridge_config()})

    @blueprint.put("/api/gdt/bridge/config")
    def update_config():
        try:
            item = bridge.update_bridge_config(request.get_json(silent=True) or {})
        except GdtConfigurationConflict as exc:
            return error(str(exc), 409)
        except ValueError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item})

    @blueprint.get("/api/gdt/workbench")
    def workbench():
        return jsonify({"success": True, **results.workbench()})

    @blueprint.post("/api/gdt/orders/<int:order_id>/write-6302")
    def write_6302(order_id: int):
        try:
            item, path = bridge.write_6302(order_id)
        except KeyError:
            return error("GDT order was not found.", 404)
        except GdtExportError as exc:
            return jsonify({"success": False, "item": exc.item, "error": str(exc)}), 500
        return jsonify({"success": True, "item": item, "path": path})

    @blueprint.get("/api/gdt/bridge/inbox")
    def bridge_inbox():
        return jsonify({"success": True, "items": bridge.inbox_items()})

    @blueprint.post("/api/gdt/bridge/import")
    def import_bridge_file():
        try:
            result = bridge.import_bridge_file(request.get_json(silent=True) or {})
        except ValueError as exc:
            return error(str(exc), 400)
        if result["imported"]:
            first = result["imported"][0]
            return jsonify({
                "success": True,
                "item": first["item"],
                "path": first["path"],
                "result": result,
            }), 201
        if result["failures"]:
            first = result["failures"][0]
            return jsonify({
                "success": False,
                "error": first["error"],
                "path": first["path"],
                "result": result,
            }), 400
        reason = (
            result["skipped"][0].get("reason", "GDT outbox file was not found.")
            if result["skipped"]
            else "GDT outbox file was not found."
        )
        return error(reason, 404)

    @blueprint.get("/api/gdt/bridge/watcher/status")
    def watcher_status():
        return jsonify({"success": True, "item": bridge.watcher_status()})

    @blueprint.post("/api/gdt/bridge/watcher/start")
    def watcher_start():
        try:
            item = bridge.start_watcher()
        except (ValidationError, SimulatorValidationError) as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item})

    @blueprint.post("/api/gdt/bridge/watcher/stop")
    def watcher_stop():
        return jsonify({"success": True, "item": bridge.stop_watcher()})

    @blueprint.post("/api/gdt/orders/<int:order_id>/demo-result")
    def demo_result(order_id: int):
        try:
            item = results.create_demo_result(order_id)
        except KeyError:
            return error("GDT order was not found.", 404)
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    @blueprint.get("/api/gdt/messages")
    def messages():
        return jsonify({"success": True, "items": results.messages()})

    @blueprint.get("/api/gdt/orders/<int:order_id>/events")
    def events(order_id: int):
        try:
            items = results.events(order_id)
        except KeyError:
            return error("GDT order was not found.", 404)
        return jsonify({"success": True, "items": items})

    @blueprint.post("/api/gdt/results")
    def import_result():
        try:
            item = results.import_result(request.get_json(silent=True) or {})
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    return blueprint
