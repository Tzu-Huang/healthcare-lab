"""Stable HTTP boundary for the Settings readiness projection."""

from __future__ import annotations

from typing import Any, Protocol

from flask import Blueprint, jsonify


class SettingsReadinessPort(Protocol):
    def get_readiness(self) -> dict[str, Any]: ...
    def run_checks(self) -> dict[str, Any]: ...


def create_settings_readiness_blueprint(
    readiness: SettingsReadinessPort,
) -> Blueprint:
    blueprint = Blueprint("settings_readiness", __name__)

    @blueprint.get("/api/settings/readiness")
    def get_settings_readiness():
        try:
            item = readiness.get_readiness()
        except Exception:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {
                            "code": "settings_readiness_unavailable",
                            "message": "Settings readiness is temporarily unavailable.",
                        },
                    }
                ),
                503,
            )
        return jsonify({"success": True, "item": item})

    @blueprint.post("/api/settings/readiness/checks")
    def run_settings_readiness_checks():
        try:
            item = readiness.run_checks()
        except Exception:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {
                            "code": "settings_checks_unavailable",
                            "message": "Settings checks are temporarily unavailable.",
                        },
                    }
                ),
                503,
            )
        return jsonify({"success": True, "item": item})

    return blueprint
