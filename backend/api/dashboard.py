"""Dashboard service hierarchy HTTP mapping."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from flask import Blueprint, Flask, jsonify, request

from backend.dashboard_services import (
    LAB_DASHBOARD_SERVICE_GROUPS,
    collect_dashboard_resource_snapshot,
    dashboard_action_for_group,
    dashboard_child_for_group,
    dashboard_operation_services,
    dashboard_servers_for_group,
    dashboard_summary,
)
from backend.lab_operations import LabOperationError
from backend.lab_store import DemoStore, SimulatorValidationError


def create_dashboard_blueprint(
    app: Flask,
    store: DemoStore,
    *,
    all_items: Callable[[Flask, DemoStore], list[dict[str, Any]]],
    group_item: Callable[[Flask, DemoStore, str], dict[str, Any]],
    child_item: Callable[[Flask, dict[str, Any]], dict[str, Any]],
    health_check: Callable[[DemoStore, str], list[dict[str, Any]]],
    event_builder: Callable[[DemoStore, list[dict[str, Any]], dict[str, Any]], list[dict[str, Any]]],
    operation_runner_provider: Callable[[], Callable[..., dict[str, Any]]],
) -> Blueprint:
    blueprint = Blueprint("dashboard", __name__)

    def error(message: str, status: int):
        return jsonify({"success": False, "error": message}), status

    def snapshot_payload(items: list[dict[str, Any]], resources: dict[str, Any]) -> dict[str, Any]:
        return {
            "items": items,
            "summary": dashboard_summary(items, resources),
            "resources": resources,
            "events": event_builder(store, items, resources),
        }

    @blueprint.get("/api/dashboard/services")
    def dashboard_services():
        resources = collect_dashboard_resource_snapshot()
        items = all_items(app, store)
        return jsonify({"success": True, **snapshot_payload(items, resources)})

    @blueprint.get("/api/dashboard/services/<service_id>/restart-preview")
    def dashboard_restart_preview(service_id: str):
        try:
            item = group_item(app, store, service_id)
        except KeyError:
            return error("Dashboard service id is not supported.", 404)
        return jsonify({"success": True, "item": item["restartPreview"]})

    @blueprint.post("/api/dashboard/services/check-all")
    def dashboard_check_all():
        results = []
        for service_id in LAB_DASHBOARD_SERVICE_GROUPS:
            try:
                results.append({"serviceId": service_id, "servers": health_check(store, service_id)})
            except (KeyError, SimulatorValidationError, LabOperationError) as exc:
                results.append({"serviceId": service_id, "error": str(exc)})
        resources = collect_dashboard_resource_snapshot()
        items = all_items(app, store)
        return jsonify({"success": True, "results": results, **snapshot_payload(items, resources)})

    @blueprint.post("/api/dashboard/services/<service_id>/<action>")
    def dashboard_service_action(service_id: str, action: str):
        payload = request.get_json(silent=True) or {}
        try:
            group, servers = dashboard_servers_for_group(store, service_id)
            primary = next((server for server in servers if server["name"] == group["primary"]), servers[0])
            if action.strip().lower() == "check":
                checked = health_check(store, service_id)
                return jsonify({
                    "success": True,
                    "service": group_item(app, store, service_id),
                    "servers": checked,
                    "output": json.dumps(checked, indent=2),
                })
            operation_action = dashboard_action_for_group(group, action)
            result = operation_runner_provider()(
                app=app,
                store=store,
                server_id=int(primary["id"]),
                action=operation_action,
                lines=int(payload.get("lines", 200) or 200),
                backing_services=dashboard_operation_services(group, operation_action),
            )
        except KeyError:
            return error("Dashboard service id is not supported.", 404)
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        except LabOperationError as exc:
            return _operation_error(exc)
        return jsonify({
            "success": True,
            "service": group_item(app, store, service_id),
            "operation": result["operation"],
            "output": result["output"],
        })

    @blueprint.post("/api/dashboard/services/<service_id>/children/<child_id>/<action>")
    def dashboard_child_service_action(service_id: str, child_id: str, action: str):
        payload = request.get_json(silent=True) or {}
        try:
            group, servers = dashboard_servers_for_group(store, service_id)
            child = dashboard_child_for_group(group, child_id)
            primary = next((server for server in servers if server["name"] == group["primary"]), servers[0])
            if action.strip().lower() == "check":
                return jsonify({
                    "success": True,
                    "service": group_item(app, store, service_id),
                    "child": child_item(app, child),
                })
            operation_action = dashboard_action_for_group(group, action)
            result = operation_runner_provider()(
                app=app,
                store=store,
                server_id=int(primary["id"]),
                action=operation_action,
                lines=int(payload.get("lines", 200) or 200),
                backing_services=[str(child["service"])],
                operation_service_name=str(child["displayName"]),
                refresh_health=False,
            )
        except KeyError:
            return error("Dashboard child service id is not supported.", 404)
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        except LabOperationError as exc:
            return _operation_error(exc)
        return jsonify({
            "success": True,
            "service": group_item(app, store, service_id),
            "child": child_item(app, child),
            "operation": result["operation"],
            "output": result["output"],
        })

    def _operation_error(exc: LabOperationError):
        try:
            body = json.loads(str(exc))
        except json.JSONDecodeError:
            body = {"operation": None, "output": "", "error": str(exc)}
        return jsonify({"success": False, **body}), 500

    return blueprint
