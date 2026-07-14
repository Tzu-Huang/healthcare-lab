"""Automatic GDT bridge inbox watcher lifecycle."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import normalize_gdt_bridge_success_mode, normalize_gdt_filename_profile
from backend.domain.errors import ValidationError
from backend.lab_store import DemoStore, validate_gdt_bridge_dirs

BridgeImporter = Callable[..., dict[str, Any]]


class GdtBridgeInboundWatcher:
    def __init__(
        self,
        store: DemoStore,
        bridge_root: str | Path,
        importer: BridgeImporter,
        *,
        poll_seconds: float = 2.0,
        success_mode: str = "archive",
        filename_profile: str = "permissive",
        receiver_id: str = "",
        sender_id: str = "",
        stable_seconds: float = 1.0,
    ) -> None:
        self.store = store
        self.bridge_root = str(bridge_root)
        self._importer = importer
        self.poll_seconds = max(0.25, float(poll_seconds))
        self.success_mode = normalize_gdt_bridge_success_mode(success_mode)
        self.filename_profile = normalize_gdt_filename_profile(filename_profile)
        self.receiver_id = str(receiver_id or "").strip()
        self.sender_id = str(sender_id or "").strip()
        self.stable_seconds = max(0.0, float(stable_seconds))
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._observations: dict[str, tuple[int, float]] = {}
        self._last_result: dict[str, Any] = {"imported": [], "skipped": [], "failures": [], "processedCount": 0}
        self._last_error = ""
        self._last_run_at = ""

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": bool(self._thread and self._thread.is_alive()),
                "bridgeRoot": self.bridge_root,
                "pollSeconds": self.poll_seconds,
                "successMode": self.success_mode,
                "filenameProfile": self.filename_profile,
                "receiverId": self.receiver_id,
                "senderId": self.sender_id,
                "stableSeconds": self.stable_seconds,
                "lastResult": self._last_result,
                "lastError": self._last_error,
                "lastRunAt": self._last_run_at,
            }

    def configure(
        self,
        *,
        bridge_root: str | Path | None = None,
        success_mode: str | None = None,
        filename_profile: str | None = None,
        receiver_id: str | None = None,
        sender_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise ValidationError("Stop automatic GDT import before changing bridge watcher configuration.")
            if bridge_root is not None:
                self.bridge_root = str(bridge_root)
            if success_mode is not None:
                self.success_mode = normalize_gdt_bridge_success_mode(success_mode)
            if filename_profile is not None:
                self.filename_profile = normalize_gdt_filename_profile(filename_profile)
            if receiver_id is not None:
                self.receiver_id = str(receiver_id or "").strip()
            if sender_id is not None:
                self.sender_id = str(sender_id or "").strip()
            self._observations = {}
            self._last_error = ""
            return self.status()

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return self.status()
            validate_gdt_bridge_dirs(self.bridge_root)
            self._stop_event.clear()
            self._last_error = ""
            self._thread = threading.Thread(target=self._serve, name="gdt-bridge-inbound-watcher", daemon=True)
            self._thread.start()
            return self.status()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self._stop_event.set()
            thread = self._thread
        if thread:
            thread.join(timeout=max(1.0, self.poll_seconds + 0.5))
        with self._lock:
            if self._thread is thread:
                self._thread = None
        return self.status()

    def _serve(self) -> None:
        while not self._stop_event.is_set():
            try:
                with self._lock:
                    arguments = {
                        "success_mode": self.success_mode,
                        "filename_profile": self.filename_profile,
                        "receiver_id": self.receiver_id,
                        "sender_id": self.sender_id,
                        "require_stable": True,
                        "stable_seconds": self.stable_seconds,
                        "observations": self._observations,
                    }
                    bridge_root = self.bridge_root
                result = self._importer(self.store, bridge_root, **arguments)
                with self._lock:
                    self._last_result = result
                    self._last_error = ""
                    self._last_run_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
            except Exception as exc:  # pragma: no cover - defensive watcher boundary
                with self._lock:
                    self._last_error = str(exc)
                    self._last_run_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
            self._stop_event.wait(self.poll_seconds)
