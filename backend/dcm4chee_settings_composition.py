"""Composition helpers for persisted dcm4chee settings and diagnostics."""

from __future__ import annotations

from typing import Any, Callable

from backend.services.dcm4chee_diagnostics import diagnose_dcm4chee


def dcm4chee_settings_operations(
    settings: Any,
) -> tuple[Callable[..., dict[str, Any]], Callable[[], dict[str, Any]]]:
    def profile(_configuration=None) -> dict[str, Any]:
        return settings.get_effective("dcm4chee").profile

    def diagnostics() -> dict[str, Any]:
        current = profile()
        if not current.get("enabled"):
            return {"state": "disabled", "checks": []}
        return diagnose_dcm4chee(current)

    return profile, diagnostics
