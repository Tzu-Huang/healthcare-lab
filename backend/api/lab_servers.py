"""Lab server metadata, CRUD, health, and history HTTP mapping."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from flask import Blueprint, Flask, jsonify, request

from backend.lab_store import (
    DemoStore,
    LAB_HEALTH_STATUSES,
    LAB_SERVER_PROTOCOLS,
    LAB_SERVER_TYPES,
    SimulatorValidationError,
)
from backend.lab_operations import LabOperationError

HealthChecker = Callable[[DemoStore, int], dict[str, Any]]
AvailabilityDecorator = Callable[[Flask, dict[str, Any]], dict[str, Any]]
OperationRunner = Callable[..., dict[str, Any]]


def create_lab_servers_blueprint(
    app: Flask,
    store: DemoStore,
    *,
    health_checker: HealthChecker,
    decorate_availability: AvailabilityDecorator,
    operation_runner: OperationRunner,
    operator_resolver: Callable[[], str],
) -> Blueprint:
    blueprint = Blueprint("lab_servers", __name__)

    def error(message: str, status: int):
        return jsonify({"success": False, "error": message}), status

    @blueprint.get("/api/lab/server-metadata")
    def lab_server_metadata():
        return jsonify({
            "success": True,
            "serverTypes": list(LAB_SERVER_TYPES),
            "protocols": list(LAB_SERVER_PROTOCOLS),
            "healthStatuses": list(LAB_HEALTH_STATUSES),
        })

    @blueprint.get("/api/lab/servers")
    def list_lab_servers():
        return jsonify({
            "success": True,
            "items": [decorate_availability(app, item) for item in store.list_lab_servers()],
        })

    @blueprint.post("/api/lab/servers")
    def create_lab_server():
        try:
            item = store.create_lab_server(request.get_json(silent=True) or {})
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": decorate_availability(app, item)}), 201

    @blueprint.get("/api/lab/servers/<int:server_id>")
    def get_lab_server(server_id: int):
        try:
            item = store.get_lab_server(server_id)
        except KeyError:
            return error("Server was not found.", 404)
        return jsonify({"success": True, "item": decorate_availability(app, item)})

    @blueprint.put("/api/lab/servers/<int:server_id>")
    def update_lab_server(server_id: int):
        try:
            item = store.update_lab_server(server_id, request.get_json(silent=True) or {})
        except KeyError:
            return error("Server was not found.", 404)
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": decorate_availability(app, item)})

    @blueprint.post("/api/lab/servers/<int:server_id>/check")
    def check_lab_server(server_id: int):
        try:
            item = health_checker(store, server_id)
        except KeyError:
            return error("Server was not found.", 404)
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": decorate_availability(app, item)})

    @blueprint.post("/api/lab/servers/check-all")
    def check_all_lab_servers():
        items = []
        for server in store.list_lab_servers():
            checked = server if not server["enabled"] else health_checker(store, int(server["id"]))
            items.append(decorate_availability(app, checked))
        return jsonify({"success": True, "items": items})

    @blueprint.get("/api/lab/servers/<int:server_id>/operations")
    def lab_server_operation_history(server_id: int):
        try:
            store.get_lab_server(server_id)
        except KeyError:
            return error("Server was not found.", 404)
        return jsonify({
            "success": True,
            "items": store.list_lab_operations(server_id, limit=int(request.args.get("limit", 20))),
        })

    def execute_operation(server_id: int, action: str):
        payload = request.get_json(silent=True) or {}
        try:
            result = operation_runner(
                app=app,
                store=store,
                server_id=server_id,
                action=action,
                lines=int(payload.get("lines", 200) or 200),
            )
        except KeyError:
            return error("Server was not found.", 404)
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        except LabOperationError as exc:
            try:
                body = json.loads(str(exc))
            except json.JSONDecodeError:
                body = {"operation": None, "output": "", "error": str(exc)}
            return jsonify({"success": False, **body}), 500
        return jsonify({"success": True, **result})

    for action in ("start", "status", "stop", "restart", "smoke", "logs"):
        blueprint.add_url_rule(
            f"/api/lab/servers/<int:server_id>/{action}",
            endpoint=f"{action}_lab_server",
            view_func=lambda server_id, selected=action: execute_operation(server_id, selected),
            methods=["POST"],
        )

    @blueprint.post("/api/lab/servers/smoke-all")
    def smoke_all_lab_servers():
        results = []
        for item in store.list_lab_servers():
            if not item["enabled"]:
                results.append({
                    "server": item,
                    "operation": store.record_lab_operation(
                        item["id"],
                        service_name=item["name"],
                        action="smoke",
                        operator=operator_resolver(),
                        result="skipped",
                        progress=[{"step": "smoke", "status": "skipped"}],
                        error_text="Server is disabled.",
                    ),
                    "output": "",
                    "command": [],
                })
                continue
            try:
                results.append(operation_runner(app=app, store=store, server_id=int(item["id"]), action="smoke"))
            except LabOperationError as exc:
                try:
                    results.append(json.loads(str(exc)))
                except json.JSONDecodeError:
                    results.append({"server": item, "operation": None, "error": str(exc)})
            except SimulatorValidationError as exc:
                results.append({"server": item, "operation": None, "error": str(exc)})
        return jsonify({"success": True, "items": results})

    return blueprint
