"""Filesystem health checks for the file-backed GDT bridge repository."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from backend.domain.errors import SimulatorValidationError
from backend.domain.gdt import ensure_gdt_bridge_dirs


def validate_gdt_bridge_dirs(base_path: str | Path) -> dict[str, Path]:
    """Preserve the runtime contract while using an empty, isolated probe."""
    directories = ensure_gdt_bridge_dirs(base_path)
    for role in ("inbox", "outbox"):
        path = directories[role]
        if not path.is_dir():
            raise SimulatorValidationError(f"GDT {role} folder does not exist: {path}")
        probe = path / f".write-test-{uuid4().hex}"
        try:
            descriptor = os.open(probe, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
            probe.unlink()
        except OSError as exc:
            try:
                probe.unlink(missing_ok=True)
            except OSError:
                pass
            raise SimulatorValidationError(f"GDT {role} folder is not writable: {path}") from exc
    return directories
