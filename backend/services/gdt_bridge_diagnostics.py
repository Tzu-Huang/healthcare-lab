"""Bounded, PHI-safe filesystem diagnostics for the GDT bridge."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.domain.errors import SimulatorValidationError


DOCUMENTED_GDT_DIRECTORY_ROLES = (
    "inbox",
    "outbox",
    "processing",
    "archive",
    "error",
    "diagnostic",
)


def confined_gdt_bridge_dirs(base_path: str | Path) -> dict[str, Path]:
    root = Path(base_path).expanduser()
    resolved_root = root.resolve(strict=False)
    directories = {"root": root}
    for role in DOCUMENTED_GDT_DIRECTORY_ROLES:
        candidate = root / role
        try:
            candidate.resolve(strict=False).relative_to(resolved_root)
        except (OSError, ValueError) as exc:
            raise SimulatorValidationError(
                f"GDT bridge directory role '{role}' escapes the configured root."
            ) from exc
        directories[role] = candidate
    return directories


def provision_gdt_bridge_dirs(base_path: str | Path) -> dict[str, Any]:
    directories = confined_gdt_bridge_dirs(base_path)
    created: list[str] = []
    existing: list[str] = []
    for role in DOCUMENTED_GDT_DIRECTORY_ROLES:
        path = directories[role]
        if path.exists():
            if not path.is_dir():
                raise SimulatorValidationError(
                    f"GDT bridge directory role '{role}' is unavailable."
                )
            existing.append(role)
            continue
        try:
            path.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            raise SimulatorValidationError(
                f"GDT bridge directory role '{role}' could not be provisioned."
            ) from exc
        created.append(role)
    return {"created": created, "existing": existing}


def diagnose_gdt_bridge_dirs(base_path: str | Path) -> dict[str, Any]:
    try:
        directories = confined_gdt_bridge_dirs(base_path)
    except SimulatorValidationError:
        return {"state": "failed", "checks": [_result("root", "failed", "path-escape")]}
    checks = [_path_result("root", directories["root"])]
    checks.extend(_path_result(role, directories[role]) for role in DOCUMENTED_GDT_DIRECTORY_ROLES)
    return {
        "state": "healthy" if all(item["state"] == "passed" for item in checks) else "degraded",
        "checks": checks,
    }


def probe_gdt_bridge_write_delete(base_path: str | Path) -> dict[str, str]:
    try:
        diagnostic = confined_gdt_bridge_dirs(base_path)["diagnostic"]
    except SimulatorValidationError:
        return _result("write-delete", "failed", "path-escape")
    if not diagnostic.is_dir():
        return _result("write-delete", "failed", "diagnostic-directory-missing")
    probe = diagnostic / f".health-{uuid4().hex}.probe"
    created = False
    try:
        descriptor = os.open(probe, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        created = True
    except OSError:
        return _result("write-delete", "failed", "write-failed")
    try:
        probe.unlink()
        created = False
    except OSError:
        return _result("write-delete", "failed", "delete-failed")
    finally:
        if created:
            try:
                probe.unlink(missing_ok=True)
            except OSError:
                pass
    return _result("write-delete", "passed", "writable")


def _path_result(role: str, path: Path) -> dict[str, str]:
    if not path.exists():
        return _result(role, "failed", "missing")
    if not path.is_dir():
        return _result(role, "failed", "not-directory")
    if not os.access(path, os.R_OK):
        return _result(role, "failed", "read-denied")
    return _result(role, "passed", "readable")


def _result(role: str, state: str, code: str) -> dict[str, str]:
    return {"role": role, "state": state, "code": code}
