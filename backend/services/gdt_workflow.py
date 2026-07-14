"""GDT workflow and bridge coordination independent of Flask request state."""

from __future__ import annotations

import os
import re
from collections.abc import Callable, MutableMapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from backend.domain.gdt import ensure_gdt_bridge_dirs


class GdtRepositoryPort(Protocol):
    def list_gdt_order_records(self) -> list[dict[str, Any]]: ...

    def get_gdt_order_record(self, order_id: int) -> dict[str, Any]: ...

    def create_gdt_order_record(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def list_gdt_workbench(self, *, bridge_inbox: list[dict[str, Any]]) -> dict[str, Any]: ...

    def record_gdt_order_export(self, order_id: int, **values: Any) -> dict[str, Any]: ...

    def create_gdt_demo_result(self, order_id: int) -> dict[str, Any]: ...

    def list_gdt_messages(self) -> list[dict[str, Any]]: ...

    def list_gdt_events(self, order_id: int) -> list[dict[str, Any]]: ...

    def record_gdt_result(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class GdtWatcherPort(Protocol):
    def status(self) -> dict[str, Any]: ...

    def configure(self, *, bridge_root: str | Path | None = None, **values: Any) -> dict[str, Any]: ...

    def start(self) -> dict[str, Any]: ...

    def stop(self) -> dict[str, Any]: ...


class GdtConfigurationConflict(Exception):
    pass


class GdtExportError(Exception):
    def __init__(self, message: str, item: dict[str, Any]) -> None:
        super().__init__(message)
        self.item = item


class GdtWorkflowService:
    def __init__(
        self,
        repository: GdtRepositoryPort,
        configuration: MutableMapping[str, Any],
        watcher: GdtWatcherPort,
        *,
        is_internal_file: Callable[[Path], bool],
        has_supported_extension: Callable[..., bool],
        filename_binding_matches: Callable[..., bool],
        bridge_importer: Callable[..., dict[str, Any]],
    ) -> None:
        self._repository = repository
        self._configuration = configuration
        self._watcher = watcher
        self._is_internal_file = is_internal_file
        self._has_supported_extension = has_supported_extension
        self._filename_binding_matches = filename_binding_matches
        self._bridge_importer = bridge_importer

    def list_orders(self) -> list[dict[str, Any]]:
        return self._repository.list_gdt_order_records()

    def get_order(self, order_id: int) -> dict[str, Any]:
        return self._repository.get_gdt_order_record(order_id)

    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._repository.create_gdt_order_record(payload)

    @staticmethod
    def _file_item(path: Path, status: str = "pending") -> dict[str, Any]:
        stat = path.stat()
        return {
            "name": path.name,
            "path": str(path),
            "status": status,
            "size": stat.st_size,
            "updatedAt": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        }

    def inbox_items(self) -> list[dict[str, Any]]:
        directories = ensure_gdt_bridge_dirs(self._configuration["GDT_BRIDGE_PATH"])
        profile = self._configuration["GDT_BRIDGE_FILENAME_PROFILE"]
        items = (
            [
                self._file_item(path)
                for path in sorted(directories["outbox"].iterdir())
                if path.is_file()
                and not self._is_internal_file(path)
                and self._has_supported_extension(path, profile=profile)
                and self._filename_binding_matches(
                    path,
                    profile=profile,
                    receiver_id=self._configuration["GDT_BRIDGE_RECEIVER_ID"],
                    sender_id=self._configuration["GDT_BRIDGE_SENDER_ID"],
                )
            ]
            if directories["outbox"].is_dir()
            else []
        )
        for status, folder in (("imported", "archive"), ("error", "error")):
            if directories[folder].is_dir():
                items.extend(
                    self._file_item(path, status)
                    for path in sorted(directories[folder].iterdir())
                    if path.is_file()
                    and not self._is_internal_file(path)
                    and self._has_supported_extension(path, profile=profile)
                )
        return items

    def bridge_config(self) -> dict[str, Any]:
        directories = ensure_gdt_bridge_dirs(self._configuration["GDT_BRIDGE_PATH"])
        return {
            "bridgePath": str(directories["root"]),
            "hostPath": os.environ.get("GDT_BRIDGE_HOST_PATH", ""),
            "inboxPath": str(directories["inbox"]),
            "outboxPath": str(directories["outbox"]),
            "archivePath": str(directories["archive"]),
            "errorPath": str(directories["error"]),
            "processingPath": str(directories["processing"]),
            "successMode": self._configuration["GDT_BRIDGE_IMPORT_SUCCESS_MODE"],
            "filenameProfile": self._configuration["GDT_BRIDGE_FILENAME_PROFILE"],
            "receiverId": self._configuration["GDT_BRIDGE_RECEIVER_ID"],
            "senderId": self._configuration["GDT_BRIDGE_SENDER_ID"],
            "watcher": self._watcher.status(),
            "dockerHint": (
                "When running in Docker, set GDT_BRIDGE_HOST_PATH in .env and restart "
                "lab-app to map a Windows folder to /data/gdt-bridge."
            ),
        }

    def update_bridge_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        bridge_path = str(payload.get("bridgePath") or "").strip()
        if not bridge_path:
            raise ValueError("GDT shared folder path is required.")
        if self._watcher.status()["running"]:
            raise GdtConfigurationConflict(
                "Stop automatic GDT import before changing the shared folder path."
            )
        if os.name != "nt" and re.match(r"^[A-Za-z]:[\\/]", bridge_path):
            raise ValueError(
                "Windows paths must be mounted into Docker first. Set GDT_BRIDGE_HOST_PATH "
                "in .env, restart lab-app, then use /data/gdt-bridge here."
            )
        self._configuration["GDT_BRIDGE_PATH"] = bridge_path
        self._watcher.configure(bridge_root=bridge_path)
        return self.bridge_config()

    def workbench(self) -> dict[str, Any]:
        return self._repository.list_gdt_workbench(bridge_inbox=self.inbox_items())

    def write_6302(self, order_id: int) -> tuple[dict[str, Any], str]:
        item = self.get_order(order_id)
        directories = ensure_gdt_bridge_dirs(self._configuration["GDT_BRIDGE_PATH"])
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        target = directories["inbox"] / f"gdtin_{item['localGdtOrderNumber']}_{timestamp}.gdt"
        temp_path = target.with_suffix(".tmp")
        try:
            temp_path.write_bytes(item["rawGdtText"].encode("cp1252"))
            temp_path.replace(target)
            updated = self._repository.record_gdt_order_export(
                order_id, export_path=str(target), status="exported"
            )
        except OSError as exc:
            updated = self._repository.record_gdt_order_export(
                order_id, export_path=str(target), status="error", error_text=str(exc)
            )
            raise GdtExportError(str(exc), updated) from exc
        return updated, str(target)

    def import_bridge_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        filename = Path(str(payload.get("filename") or payload.get("name") or "")).name
        profile = self._configuration["GDT_BRIDGE_FILENAME_PROFILE"]
        if not self._has_supported_extension(Path(filename), profile=profile):
            raise ValueError("A supported GDT outbox filename is required.")
        return self._bridge_importer(
            self._repository,
            self._configuration["GDT_BRIDGE_PATH"],
            filename=filename,
            success_mode=self._configuration["GDT_BRIDGE_IMPORT_SUCCESS_MODE"],
            filename_profile=profile,
            receiver_id=self._configuration["GDT_BRIDGE_RECEIVER_ID"],
            sender_id=self._configuration["GDT_BRIDGE_SENDER_ID"],
        )

    def watcher_status(self) -> dict[str, Any]:
        return self._watcher.status()

    def start_watcher(self) -> dict[str, Any]:
        return self._watcher.start()

    def stop_watcher(self) -> dict[str, Any]:
        return self._watcher.stop()

    def create_demo_result(self, order_id: int) -> dict[str, Any]:
        return self._repository.create_gdt_demo_result(order_id)

    def messages(self) -> list[dict[str, Any]]:
        return self._repository.list_gdt_messages()

    def events(self, order_id: int) -> list[dict[str, Any]]:
        self.get_order(order_id)
        return self._repository.list_gdt_events(order_id)

    def import_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._repository.record_gdt_result(payload)
