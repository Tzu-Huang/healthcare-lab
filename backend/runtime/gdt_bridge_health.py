"""Filesystem health checks for the GDT bridge runtime."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from backend.domain.errors import SimulatorValidationError
from backend.domain.gdt import ensure_gdt_bridge_dirs


def validate_gdt_bridge_dirs(base_path: str | Path) -> dict[str, Path]:
    """Ensure the bridge folders exist and its transfer endpoints are writable."""
    directories = ensure_gdt_bridge_dirs(base_path)
    probe_name = f".write-test-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    for name in ("inbox", "outbox"):
        if not directories[name].is_dir():
            raise SimulatorValidationError(
                f"GDT {name} folder does not exist: {directories[name]}"
            )
        probe_path = directories[name] / probe_name
        try:
            probe_path.write_text("ok", encoding="utf-8")
            probe_path.unlink()
        except OSError as exc:
            raise SimulatorValidationError(
                f"GDT {name} folder is not writable: {directories[name]}"
            ) from exc
    return directories
