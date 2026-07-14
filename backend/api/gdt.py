"""GDT order, bridge, watcher, and result HTTP mapping."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, Flask, jsonify, request

from backend.domain.errors import ValidationError
from backend.lab_store import DemoStore, SimulatorValidationError, ensure_gdt_bridge_dirs


def create_gdt_blueprint(
    app: Flask,
    store: DemoStore,
    *,
    is_internal_file: Callable[[Path], bool],
    has_supported_extension: Callable[..., bool],
    filename_binding_matches: Callable[..., bool],
    bridge_importer: Callable[..., dict[str, Any]],
) -> Blueprint:
    blueprint = Blueprint("gdt", __name__)

    def error(message: str, status: int):
        return jsonify({"success": False, "error": message}), status

    def order_or_error(order_id: int):
        try:
            return store.get_gdt_order_record(order_id), None
        except KeyError:
            return None, error("GDT order was not found.", 404)

    def file_item(path: Path, status: str = "pending") -> dict[str, Any]:
        stat = path.stat()
        return {
            "name": path.name, "path": str(path), "status": status, "size": stat.st_size,
            "updatedAt": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        }

    def inbox_items() -> list[dict[str, Any]]:
        dirs = ensure_gdt_bridge_dirs(app.config["GDT_BRIDGE_PATH"])
        profile = app.config["GDT_BRIDGE_FILENAME_PROFILE"]
        items = [
            file_item(path) for path in sorted(dirs["outbox"].iterdir())
            if path.is_file() and not is_internal_file(path)
            and has_supported_extension(path, profile=profile)
            and filename_binding_matches(
                path, profile=profile, receiver_id=app.config["GDT_BRIDGE_RECEIVER_ID"],
                sender_id=app.config["GDT_BRIDGE_SENDER_ID"],
            )
        ] if dirs["outbox"].is_dir() else []
        for status, folder in (("imported", "archive"), ("error", "error")):
            if dirs[folder].is_dir():
                items.extend(
                    file_item(path, status) for path in sorted(dirs[folder].iterdir())
                    if path.is_file() and not is_internal_file(path)
                    and has_supported_extension(path, profile=profile)
                )
        return items

    def config_payload() -> dict[str, Any]:
        dirs = ensure_gdt_bridge_dirs(app.config["GDT_BRIDGE_PATH"])
        return {
            "bridgePath": str(dirs["root"]), "hostPath": os.environ.get("GDT_BRIDGE_HOST_PATH", ""),
            "inboxPath": str(dirs["inbox"]), "outboxPath": str(dirs["outbox"]),
            "archivePath": str(dirs["archive"]), "errorPath": str(dirs["error"]),
            "processingPath": str(dirs["processing"]),
            "successMode": app.config["GDT_BRIDGE_IMPORT_SUCCESS_MODE"],
            "filenameProfile": app.config["GDT_BRIDGE_FILENAME_PROFILE"],
            "receiverId": app.config["GDT_BRIDGE_RECEIVER_ID"], "senderId": app.config["GDT_BRIDGE_SENDER_ID"],
            "watcher": app.extensions["gdt_bridge_watcher"].status(),
            "dockerHint": "When running in Docker, set GDT_BRIDGE_HOST_PATH in .env and restart lab-app to map a Windows folder to /data/gdt-bridge.",
        }

    @blueprint.get("/api/gdt/orders")
    def list_orders():
        return jsonify({"success": True, "items": store.list_gdt_order_records()})

    @blueprint.get("/api/gdt/orders/<int:order_id>")
    def get_order(order_id: int):
        item, failure = order_or_error(order_id)
        return failure or jsonify({"success": True, "item": item})

    @blueprint.post("/api/gdt/orders")
    def create_order():
        try:
            item = store.create_gdt_order_record(request.get_json(silent=True) or {})
        except KeyError:
            return error("Patient record was not found.", 404)
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    @blueprint.get("/api/gdt/bridge/config")
    def get_config():
        return jsonify({"success": True, "item": config_payload()})

    @blueprint.put("/api/gdt/bridge/config")
    def update_config():
        bridge_path = str((request.get_json(silent=True) or {}).get("bridgePath") or "").strip()
        if not bridge_path:
            return error("GDT shared folder path is required.", 400)
        watcher = app.extensions["gdt_bridge_watcher"]
        if watcher.status()["running"]:
            return error("Stop automatic GDT import before changing the shared folder path.", 409)
        if os.name != "nt" and re.match(r"^[A-Za-z]:[\\/]", bridge_path):
            return error(
                "Windows paths must be mounted into Docker first. Set GDT_BRIDGE_HOST_PATH in .env, restart lab-app, then use /data/gdt-bridge here.", 400
            )
        app.config["GDT_BRIDGE_PATH"] = bridge_path
        watcher.configure(bridge_root=bridge_path)
        return jsonify({"success": True, "item": config_payload()})

    @blueprint.get("/api/gdt/workbench")
    def workbench():
        return jsonify({"success": True, **store.list_gdt_workbench(bridge_inbox=inbox_items())})

    @blueprint.post("/api/gdt/orders/<int:order_id>/write-6302")
    def write_6302(order_id: int):
        item, failure = order_or_error(order_id)
        if failure:
            return failure
        dirs = ensure_gdt_bridge_dirs(app.config["GDT_BRIDGE_PATH"])
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        target = dirs["inbox"] / f"gdtin_{item['localGdtOrderNumber']}_{timestamp}.gdt"
        temp_path = target.with_suffix(".tmp")
        try:
            temp_path.write_bytes(item["rawGdtText"].encode("cp1252"))
            temp_path.replace(target)
            updated = store.record_gdt_order_export(order_id, export_path=str(target), status="exported")
        except OSError as exc:
            updated = store.record_gdt_order_export(order_id, export_path=str(target), status="error", error_text=str(exc))
            return jsonify({"success": False, "item": updated, "error": str(exc)}), 500
        return jsonify({"success": True, "item": updated, "path": str(target)})

    @blueprint.get("/api/gdt/bridge/inbox")
    def bridge_inbox():
        return jsonify({"success": True, "items": inbox_items()})

    @blueprint.post("/api/gdt/bridge/import")
    def import_bridge_file():
        payload = request.get_json(silent=True) or {}
        filename = Path(str(payload.get("filename") or payload.get("name") or "")).name
        profile = app.config["GDT_BRIDGE_FILENAME_PROFILE"]
        if not has_supported_extension(Path(filename), profile=profile):
            return error("A supported GDT outbox filename is required.", 400)
        result = bridge_importer(
            store, app.config["GDT_BRIDGE_PATH"], filename=filename,
            success_mode=app.config["GDT_BRIDGE_IMPORT_SUCCESS_MODE"], filename_profile=profile,
            receiver_id=app.config["GDT_BRIDGE_RECEIVER_ID"], sender_id=app.config["GDT_BRIDGE_SENDER_ID"],
        )
        if result["imported"]:
            first = result["imported"][0]
            return jsonify({"success": True, "item": first["item"], "path": first["path"], "result": result}), 201
        if result["failures"]:
            first = result["failures"][0]
            return jsonify({"success": False, "error": first["error"], "path": first["path"], "result": result}), 400
        reason = result["skipped"][0].get("reason", "GDT outbox file was not found.") if result["skipped"] else "GDT outbox file was not found."
        return error(reason, 404)

    @blueprint.get("/api/gdt/bridge/watcher/status")
    def watcher_status():
        return jsonify({"success": True, "item": app.extensions["gdt_bridge_watcher"].status()})

    @blueprint.post("/api/gdt/bridge/watcher/start")
    def watcher_start():
        try:
            item = app.extensions["gdt_bridge_watcher"].start()
        except (ValidationError, SimulatorValidationError) as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item})

    @blueprint.post("/api/gdt/bridge/watcher/stop")
    def watcher_stop():
        return jsonify({"success": True, "item": app.extensions["gdt_bridge_watcher"].stop()})

    @blueprint.post("/api/gdt/orders/<int:order_id>/demo-result")
    def demo_result(order_id: int):
        try:
            item = store.create_gdt_demo_result(order_id)
        except KeyError:
            return error("GDT order was not found.", 404)
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    @blueprint.get("/api/gdt/messages")
    def messages():
        return jsonify({"success": True, "items": store.list_gdt_messages()})

    @blueprint.get("/api/gdt/orders/<int:order_id>/events")
    def events(order_id: int):
        _item, failure = order_or_error(order_id)
        return failure or jsonify({"success": True, "items": store.list_gdt_events(order_id)})

    @blueprint.post("/api/gdt/results")
    def import_result():
        try:
            item = store.record_gdt_result(request.get_json(silent=True) or {})
        except SimulatorValidationError as exc:
            return error(str(exc), 400)
        return jsonify({"success": True, "item": item}), 201

    return blueprint
