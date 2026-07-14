"""Dashboard service hierarchy HTTP mapping."""

from __future__ import annotations

import json
from typing import Any, Protocol

from flask import Blueprint, jsonify, request

from backend.domain.errors import LabOperationError, SimulatorValidationError


class DashboardServicePort(Protocol):
    def snapshot(self) -> dict[str, Any]: ...

    def restart_preview(self, service_id: str) -> dict[str, Any]: ...

    def check_all(self) -> dict[str, Any]: ...

    def run_action(
        self, service_id: str, action: str, *, lines: int = 200
    ) -> dict[str, Any]: ...

    def run_child_action(
        self,
        service_id: str,
        child_id: str,
        action: str,
        *,
        lines: int = 200,
    ) -> dict[str, Any]: ...


def create_dashboard_blueprint(
    service: DashboardServicePort,
) -> Blueprint:
    blueprint = Blueprint("dashboard", __name__)

    def error(message: str, status: int):
        return jsonify({"success": False, "error": message}), status

    @blueprint.get("/api/dashboard/services")
    def dashboard_services():
        return jsonify({"success": True, **service.snapshot()})

    @blueprint.get("/api/dashboard/services/<service_id>/restart-preview")
    def dashboard_restart_preview(service_id: str):
        try:
            item = service.restart_preview(service_id)
        except KeyError:
            return error("Dashboard service id is not supported.", 404)
        return jsonify({"success": True, "item": item})

    @blueprint.post("/api/dashboard/services/check-all")
    def dashboard_check_all():
        return jsonify({"success": True, **service.check_all()})

    @blueprint.post("/api/dashboard/services/<service_id>/<action>")
    def dashboard_service_action(service_id: str, action: str):
        payload = request.get_json(silent=True) or {}
        try:
            result = service.run_action(
                service_id,
                action,
                lines=int(payload.get("lines", 200) or 200),
            )
        except KeyError:
            return error("Dashboard service id is not supported.", 404)
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        except LabOperationError as exc:
            return _operation_error(exc)
        return jsonify({"success": True, **result})

    @blueprint.post("/api/dashboard/services/<service_id>/children/<child_id>/<action>")
    def dashboard_child_service_action(service_id: str, child_id: str, action: str):
        payload = request.get_json(silent=True) or {}
        try:
            result = service.run_child_action(
                service_id,
                child_id,
                action,
                lines=int(payload.get("lines", 200) or 200),
            )
        except KeyError:
            return error("Dashboard child service id is not supported.", 404)
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        except LabOperationError as exc:
            return _operation_error(exc)
        return jsonify({"success": True, **result})

    def _operation_error(exc: LabOperationError):
        try:
            body = json.loads(str(exc))
        except json.JSONDecodeError:
            body = {"operation": None, "output": "", "error": str(exc)}
        return jsonify({"success": False, **body}), 500

    return blueprint
