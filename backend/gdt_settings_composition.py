"""Application composition helpers for persisted GDT Bridge settings."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from backend.services.gdt_bridge_diagnostics import (
    diagnose_gdt_bridge_dirs,
    gdt_settings_diagnostics,
    provision_gdt_bridge_dirs,
)


def create_gdt_bridge_watcher(
    settings: Any,
    store: Any,
    importer: Callable[..., dict[str, Any]],
    watcher_factory: Callable[..., Any],
) -> Any:
    profile = settings.get_effective("gdt-bridge")
    return watcher_factory(
        store,
        profile.bridge_path,
        importer,
        poll_seconds=profile.poll_seconds,
        success_mode=profile.success_mode,
        filename_profile=profile.filename_profile,
        receiver_id=profile.receiver_id,
        sender_id=profile.sender_id,
        stable_seconds=profile.stable_seconds,
    )


def gdt_settings_api_operations(
    settings: Any, watcher: Any
) -> dict[str, Callable[[], dict[str, Any]]]:
    effective = lambda: settings.get_effective("gdt-bridge")
    return {
        "gdt_activate": lambda: watcher.apply_profile(effective()),
        "gdt_provision": lambda: provision_gdt_bridge_dirs(
            effective().bridge_path
        ),
        "gdt_diagnostics": lambda: gdt_settings_diagnostics(
            effective().bridge_path, watcher.status()
        ),
        "gdt_deployment": lambda: {
            "applicationPath": "/data/gdt-bridge",
            "hostBindMountSource": os.environ.get("GDT_BRIDGE_HOST_PATH", ""),
        },
    }


def gdt_readiness_diagnostics(settings: Any) -> dict[str, Any]:
    return diagnose_gdt_bridge_dirs(
        settings.get_effective("gdt-bridge").bridge_path
    )


def gdt_run_all_diagnostics(settings: Any, watcher: Any) -> dict[str, Any]:
    return gdt_settings_diagnostics(
        settings.get_effective("gdt-bridge").bridge_path,
        watcher.status(),
    )
