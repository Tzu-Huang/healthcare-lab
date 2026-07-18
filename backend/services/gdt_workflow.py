"""GDT workflow and bridge coordination independent of Flask request state."""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable, MutableMapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from backend.config import normalize_gdt_bridge_success_mode, normalize_gdt_filename_profile
from backend.domain.errors import SimulatorValidationError
from backend.domain.gdt import ensure_gdt_bridge_dirs


class GdtResultImportPort(Protocol):
    def record_gdt_result(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class GdtWorkflowPort(GdtResultImportPort, Protocol):
    def list_gdt_order_records(self) -> list[dict[str, Any]]: ...

    def get_gdt_order_record(self, order_id: int) -> dict[str, Any]: ...

    def create_gdt_order_record(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def list_gdt_workbench(self, *, bridge_inbox: list[dict[str, Any]]) -> dict[str, Any]: ...

    def record_gdt_order_export(
        self, order_id: int, *, export_path: str, status: str, error_text: str = "",
    ) -> dict[str, Any]: ...

    def create_gdt_demo_result(self, order_id: int) -> dict[str, Any]: ...

    def list_gdt_messages(self) -> list[dict[str, Any]]: ...

    def list_gdt_events(self, order_id: int) -> list[dict[str, Any]]: ...


class GdtOrderPort(Protocol):
    def list_gdt_order_records(self) -> list[dict[str, Any]]: ...
    def get_gdt_order_record(self, order_id: int) -> dict[str, Any]: ...
    def create_gdt_order_record(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class GdtBridgePort(GdtResultImportPort, Protocol):
    def get_gdt_order_record(self, order_id: int) -> dict[str, Any]: ...
    def record_gdt_order_export(
        self, order_id: int, *, export_path: str, status: str, error_text: str = "",
    ) -> dict[str, Any]: ...


class GdtResultPort(GdtResultImportPort, Protocol):
    def get_gdt_order_record(self, order_id: int) -> dict[str, Any]: ...
    def list_gdt_workbench(self, *, bridge_inbox: list[dict[str, Any]]) -> dict[str, Any]: ...
    def create_gdt_demo_result(self, order_id: int) -> dict[str, Any]: ...
    def list_gdt_messages(self) -> list[dict[str, Any]]: ...
    def list_gdt_events(self, order_id: int) -> list[dict[str, Any]]: ...


class GdtWatcherPort(Protocol):
    def status(self) -> dict[str, Any]: ...

    def configure(
        self,
        *,
        bridge_root: str | Path | None = None,
        success_mode: str | None = None,
        filename_profile: str | None = None,
        receiver_id: str | None = None,
        sender_id: str | None = None,
    ) -> dict[str, Any]: ...

    def start(self) -> dict[str, Any]: ...

    def stop(self) -> dict[str, Any]: ...


class GdtExtensionMatcher(Protocol):
    def __call__(self, path: Path, *, profile: str) -> bool: ...


class GdtFilenameMatcher(Protocol):
    def __call__(self, path: Path, *, profile: str, receiver_id: str, sender_id: str) -> bool: ...


class GdtBridgeImporter(Protocol):
    def __call__(self, repository: GdtResultImportPort, bridge_root: str | Path, *, filename: str, success_mode: str, filename_profile: str, receiver_id: str, sender_id: str) -> dict[str, Any]: ...


class GdtConfigurationConflict(Exception):
    pass


class GdtExportError(Exception):
    def __init__(self, message: str, item: dict[str, Any]) -> None:
        super().__init__(message)
        self.item = item


class GdtBridgeService:
    def __init__(
        self,
        repository: GdtBridgePort,
        configuration: MutableMapping[str, Any],
        watcher: GdtWatcherPort,
        *,
        is_internal_file: Callable[[Path], bool],
        has_supported_extension: GdtExtensionMatcher,
        filename_binding_matches: GdtFilenameMatcher,
        bridge_importer: GdtBridgeImporter,
    ) -> None:
        self._repository = repository
        self._configuration = configuration
        self._watcher = watcher
        self._is_internal_file = is_internal_file
        self._has_supported_extension = has_supported_extension
        self._filename_binding_matches = filename_binding_matches
        self._bridge_importer = bridge_importer

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

    def write_6302(self, order_id: int) -> tuple[dict[str, Any], str]:
        item = self._repository.get_gdt_order_record(order_id)
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


class GdtResultService:
    def __init__(self, repository: GdtResultPort, *, inbox_items: Callable[[], list[dict[str, Any]]]) -> None:
        self._repository = repository
        self._inbox_items = inbox_items

    def workbench(self) -> dict[str, Any]:
        return self._repository.list_gdt_workbench(bridge_inbox=self._inbox_items())

    def create_demo_result(self, order_id: int) -> dict[str, Any]:
        return self._repository.create_gdt_demo_result(order_id)

    def messages(self) -> list[dict[str, Any]]:
        return self._repository.list_gdt_messages()

    def events(self, order_id: int) -> list[dict[str, Any]]:
        self._repository.get_gdt_order_record(order_id)
        return self._repository.list_gdt_events(order_id)

    def import_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._repository.record_gdt_result(payload)


class GdtWorkflowService:
    """Compatibility façade while callers migrate to focused GDT services."""

    def __init__(
        self,
        repository: GdtWorkflowPort,
        configuration: MutableMapping[str, Any],
        watcher: GdtWatcherPort,
        *,
        is_internal_file: Callable[[Path], bool],
        has_supported_extension: GdtExtensionMatcher,
        filename_binding_matches: GdtFilenameMatcher,
        bridge_importer: GdtBridgeImporter,
    ) -> None:
        self._repository = repository
        self.bridge_service = GdtBridgeService(
            repository, configuration, watcher,
            is_internal_file=is_internal_file,
            has_supported_extension=has_supported_extension,
            filename_binding_matches=filename_binding_matches,
            bridge_importer=bridge_importer,
        )
        self.result_service = GdtResultService(repository, inbox_items=self.bridge_service.inbox_items)

    def list_orders(self) -> list[dict[str, Any]]:
        return self._repository.list_gdt_order_records()

    def get_order(self, order_id: int) -> dict[str, Any]:
        return self._repository.get_gdt_order_record(order_id)

    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._repository.create_gdt_order_record(payload)

    def inbox_items(self) -> list[dict[str, Any]]:
        return self.bridge_service.inbox_items()

    def bridge_config(self) -> dict[str, Any]:
        return self.bridge_service.bridge_config()

    def update_bridge_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.bridge_service.update_bridge_config(payload)

    def workbench(self) -> dict[str, Any]:
        return self.result_service.workbench()

    def write_6302(self, order_id: int) -> tuple[dict[str, Any], str]:
        return self.bridge_service.write_6302(order_id)

    def import_bridge_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.bridge_service.import_bridge_file(payload)

    def watcher_status(self) -> dict[str, Any]:
        return self.bridge_service.watcher_status()

    def start_watcher(self) -> dict[str, Any]:
        return self.bridge_service.start_watcher()

    def stop_watcher(self) -> dict[str, Any]:
        return self.bridge_service.stop_watcher()

    def create_demo_result(self, order_id: int) -> dict[str, Any]:
        return self.result_service.create_demo_result(order_id)

    def messages(self) -> list[dict[str, Any]]:
        return self.result_service.messages()

    def events(self, order_id: int) -> list[dict[str, Any]]:
        return self.result_service.events(order_id)

    def import_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.result_service.import_result(payload)


def gdt_path_status(path: Path, status: str, reason: str = "") -> dict[str, Any]:
    item: dict[str, Any] = {"name": path.name, "path": str(path), "status": status}
    try:
        stat = path.stat()
        item.update(
            {
                "size": stat.st_size,
                "updatedAt": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "createdAt": datetime.fromtimestamp(stat.st_ctime, timezone.utc).isoformat(),
            }
        )
    except OSError:
        item.update({"size": 0, "updatedAt": "", "createdAt": ""})
    if reason:
        item["reason"] = reason
    return item


def gdt_is_internal_or_temp_file(path: Path) -> bool:
    name = path.name
    lowered = name.lower()
    return (
        name.startswith(".")
        or lowered.endswith(".tmp")
        or lowered.endswith(".temp")
        or lowered.endswith(".processing")
        or ".processing." in lowered
    )


def gdt_has_supported_exchange_extension(path: Path, *, profile: str = "permissive") -> bool:
    if path.suffix.lower() == ".gdt":
        return True
    return normalize_gdt_filename_profile(profile) == "gdt21" and bool(re.fullmatch(r"\.\d{3}", path.suffix))


def gdt_filename_binding_matches(
    path: Path,
    *,
    profile: str = "permissive",
    receiver_id: str = "",
    sender_id: str = "",
) -> bool:
    profile = normalize_gdt_filename_profile(profile)
    name = path.name
    upper_name = name.upper()
    receiver = str(receiver_id or "").strip().upper()
    sender = str(sender_id or "").strip().upper()
    if profile == "permissive":
        return path.suffix.lower() == ".gdt"
    if profile == "gdt35":
        if path.suffix.lower() != ".gdt":
            return False
        pattern = r"^([A-Z0-9]+)_([A-Z0-9]+)_([A-Z0-9]+)\.GDT$"
        match = re.match(pattern, upper_name)
        if not match:
            return False
        matched_receiver, matched_sender, _sequence = match.groups()
        if receiver and matched_receiver != receiver:
            return False
        if sender and matched_sender != sender:
            return False
        return True
    stem_upper = path.stem.upper()
    suffix_upper = path.suffix.upper()
    if suffix_upper == ".GDT":
        return (not receiver or stem_upper.startswith(receiver)) and (
            not sender or stem_upper.endswith(sender)
        )
    if re.fullmatch(r"\.\d{3}", suffix_upper):
        return (not receiver or stem_upper.startswith(receiver)) and (
            not sender or stem_upper.endswith(sender)
        )
    return False


def gdt_collision_safe_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    return path.with_name(f"{path.stem}-{timestamp}{path.suffix}")


def gdt_inbound_sort_key(path: Path) -> tuple[float, float, str]:
    try:
        stat = path.stat()
        return (float(stat.st_ctime), float(stat.st_mtime), path.name.lower())
    except OSError:
        return (float("inf"), float("inf"), path.name.lower())


def gdt_file_is_stable(
    path: Path,
    *,
    stable_seconds: float = 1.0,
    observations: dict[str, tuple[int, float]] | None = None,
) -> tuple[bool, str]:
    try:
        stat = path.stat()
    except OSError as exc:
        return False, f"stat failed: {exc}"
    if observations is not None:
        key = str(path)
        current = (int(stat.st_size), float(stat.st_mtime))
        previous = observations.get(key)
        observations[key] = current
        if previous != current:
            return False, "waiting for stable size and timestamp"
    age_seconds = max(0.0, time.time() - float(stat.st_mtime))
    if age_seconds < max(0.0, float(stable_seconds)):
        return False, "waiting for file age threshold"
    return True, ""


def discover_gdt_inbound_candidates(
    bridge_root: str | Path,
    *,
    filename: str = "",
    filename_profile: str = "permissive",
    receiver_id: str = "",
    sender_id: str = "",
    require_stable: bool = False,
    stable_seconds: float = 1.0,
    observations: dict[str, tuple[int, float]] | None = None,
) -> tuple[list[Path], list[dict[str, Any]], dict[str, Path]]:
    directories = ensure_gdt_bridge_dirs(bridge_root)
    inbound = directories["outbox"]
    skipped: list[dict[str, Any]] = []
    if not inbound.is_dir():
        raise SimulatorValidationError(f"GDT outbox folder does not exist: {inbound}")
    if filename:
        paths = [inbound / Path(filename).name]
    else:
        paths = [path for path in inbound.iterdir() if path.is_file()]
    candidates: list[Path] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            skipped.append(gdt_path_status(path, "skipped", "not found"))
            continue
        if gdt_is_internal_or_temp_file(path):
            skipped.append(gdt_path_status(path, "skipped", "temporary or internal file"))
            continue
        if not gdt_has_supported_exchange_extension(path, profile=filename_profile):
            skipped.append(gdt_path_status(path, "skipped", "unsupported extension"))
            continue
        if not gdt_filename_binding_matches(
            path,
            profile=filename_profile,
            receiver_id=receiver_id,
            sender_id=sender_id,
        ):
            skipped.append(gdt_path_status(path, "skipped", "filename binding mismatch"))
            continue
        if require_stable:
            stable, reason = gdt_file_is_stable(
                path,
                stable_seconds=stable_seconds,
                observations=observations,
            )
            if not stable:
                skipped.append(gdt_path_status(path, "skipped", reason))
                continue
        candidates.append(path)
    return sorted(candidates, key=gdt_inbound_sort_key), skipped, directories


def import_gdt_bridge_files(
    store: GdtResultImportPort,
    bridge_root: str | Path,
    *,
    filename: str = "",
    success_mode: str = "archive",
    filename_profile: str = "permissive",
    receiver_id: str = "",
    sender_id: str = "",
    require_stable: bool = False,
    stable_seconds: float = 1.0,
    observations: dict[str, tuple[int, float]] | None = None,
) -> dict[str, Any]:
    success_mode = normalize_gdt_bridge_success_mode(success_mode)
    filename_profile = normalize_gdt_filename_profile(filename_profile)
    candidates, skipped, directories = discover_gdt_inbound_candidates(
        bridge_root,
        filename=filename,
        filename_profile=filename_profile,
        receiver_id=receiver_id,
        sender_id=sender_id,
        require_stable=require_stable,
        stable_seconds=stable_seconds,
        observations=observations,
    )
    processing_dir = directories["processing"]
    imported: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for source_path in candidates:
        processing_path = gdt_collision_safe_path(processing_dir / source_path.name)
        try:
            source_path.replace(processing_path)
        except OSError as exc:
            skipped.append(gdt_path_status(source_path, "skipped", f"claim failed: {exc}"))
            continue
        try:
            raw_gdt_text = processing_path.read_bytes().decode("cp1252")
            item = store.record_gdt_result(
                {
                    "rawGdtText": raw_gdt_text,
                    "bridgeRoot": str(directories["root"]),
                    "sourceFile": source_path.name,
                    "sourcePath": str(source_path),
                }
            )
        except (SimulatorValidationError, UnicodeDecodeError, OSError) as exc:
            error_target = gdt_collision_safe_path(directories["error"] / source_path.name)
            try:
                if processing_path.exists():
                    processing_path.replace(error_target)
            except OSError:
                pass
            failures.append(
                {
                    "name": source_path.name,
                    "sourcePath": str(source_path),
                    "path": str(error_target),
                    "error": str(exc),
                }
            )
            continue
        disposition_error = ""
        target_path: Path | None = None
        try:
            if success_mode == "delete":
                processing_path.unlink()
                target_path = processing_path
                final_status = "deleted"
            else:
                target_path = gdt_collision_safe_path(directories["archive"] / source_path.name)
                processing_path.replace(target_path)
                final_status = "imported"
        except OSError as exc:
            final_status = "imported-warning"
            target_path = processing_path
            disposition_error = str(exc)
        imported_item = {
            "item": item,
            "name": source_path.name,
            "sourcePath": str(source_path),
            "path": "" if success_mode == "delete" and not disposition_error else str(target_path),
            "status": final_status,
            "successMode": success_mode,
        }
        if disposition_error:
            imported_item["dispositionError"] = disposition_error
        imported.append(imported_item)
    return {
        "imported": imported,
        "skipped": skipped,
        "failures": failures,
        "processedCount": len(imported) + len(failures),
        "successMode": success_mode,
        "filenameProfile": filename_profile,
        "receiverId": receiver_id,
        "senderId": sender_id,
    }
