"""Lab server metadata, CRUD, health, and history HTTP mapping."""

from __future__ import annotations

import json
from typing import Any, Protocol

from flask import Blueprint, jsonify, request

from backend.domain.errors import LabOperationError, SimulatorValidationError


class LabRegistryPort(Protocol):
    def metadata(self) -> dict[str, list[str]]: ...

    def list_servers(self) -> list[dict[str, Any]]: ...

    def create_server(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def get_server(self, server_id: int) -> dict[str, Any]: ...

    def update_server(self, server_id: int, payload: dict[str, Any]) -> dict[str, Any]: ...

class LabHealthPort(Protocol):
    def check_server(self, server_id: int) -> dict[str, Any]: ...

    def check_all_servers(self) -> list[dict[str, Any]]: ...

class LabOperationPort(Protocol):
    def operation_history(self, server_id: int, *, limit: int = 20) -> list[dict[str, Any]]: ...

    def execute_operation(
        self, server_id: int, action: str, *, lines: int = 200
    ) -> dict[str, Any]: ...

class LabSmokePort(Protocol):
    def smoke_all_servers(self) -> list[dict[str, Any]]: ...


def create_lab_servers_blueprint(
    registry: LabRegistryPort,
    health: LabHealthPort,
    operations: LabOperationPort,
    smoke: LabSmokePort,
) -> Blueprint:
    blueprint = Blueprint("lab_servers", __name__)

    def error(message: str, status: int):
        return jsonify({"success": False, "error": message}), status

    @blueprint.get("/api/lab/server-metadata")
    def lab_server_metadata():
        return jsonify({"success": True, **registry.metadata()})

    @blueprint.get("/api/lab/servers")
    def list_lab_servers():
        return jsonify({"success": True, "items": registry.list_servers()})

    @blueprint.post("/api/lab/servers")
    def create_lab_server():
        try:
            item = registry.create_server(request.get_json(silent=True) or {})
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    @blueprint.get("/api/lab/servers/<int:server_id>")
    def get_lab_server(server_id: int):
        try:
            item = registry.get_server(server_id)
        except KeyError:
            return error("Server was not found.", 404)
        return jsonify({"success": True, "item": item})

    @blueprint.put("/api/lab/servers/<int:server_id>")
    def update_lab_server(server_id: int):
        try:
            item = registry.update_server(server_id, request.get_json(silent=True) or {})
        except KeyError:
            return error("Server was not found.", 404)
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item})

    @blueprint.post("/api/lab/servers/<int:server_id>/check")
    def check_lab_server(server_id: int):
        try:
            item = health.check_server(server_id)
        except KeyError:
            return error("Server was not found.", 404)
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item})

    @blueprint.post("/api/lab/servers/check-all")
    def check_all_lab_servers():
        return jsonify({"success": True, "items": health.check_all_servers()})

    @blueprint.get("/api/lab/servers/<int:server_id>/operations")
    def lab_server_operation_history(server_id: int):
        try:
            items = operations.operation_history(
                server_id, limit=int(request.args.get("limit", 20))
            )
        except KeyError:
            return error("Server was not found.", 404)
        return jsonify({"success": True, "items": items})

    def execute_operation(server_id: int, action: str):
        payload = request.get_json(silent=True) or {}
        try:
            result = operations.execute_operation(
                server_id,
                action,
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
        return jsonify({"success": True, "items": smoke.smoke_all_servers()})

    return blueprint
