"""dcm4chee connection profile HTTP mapping."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from flask import Blueprint, jsonify


def create_dcm4chee_profile_blueprint(
    config: Mapping[str, Any],
    *,
    profile_builder: Callable[[Mapping[str, Any]], dict[str, Any]],
    profile_validator: Callable[[dict[str, Any]], dict[str, Any]],
) -> Blueprint:
    blueprint = Blueprint("dcm4chee_profile", __name__)

    @blueprint.get("/api/dcm4chee/profile")
    @blueprint.get("/api/dcm4chee/profiles/<profile_name>")
    def get_dcm4chee_profile(profile_name: str | None = None):
        profile = profile_builder(config)
        if profile_name and profile_name != profile["profileName"]:
            return jsonify({"success": False, "error": "dcm4chee profile was not found."}), 404
        return jsonify({
            "success": True,
            "item": profile,
            "diagnostics": profile_validator(profile),
        })

    @blueprint.get("/api/dcm4chee/profile/diagnostics")
    def get_dcm4chee_profile_diagnostics():
        profile = profile_builder(config)
        return jsonify({
            "success": True,
            "profileName": profile["profileName"],
            **profile_validator(profile),
        })

    return blueprint
