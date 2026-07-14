"""OIE HTTP request and response mapping."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.lab_store import SimulatorValidationError
from backend.services.oie_settings import OieSettingsService


def create_oie_settings_blueprint(service: OieSettingsService) -> Blueprint:
    blueprint = Blueprint("oie_settings", __name__)

    @blueprint.get("/api/oie/settings")
    def get_oie_settings():
        return jsonify({"success": True, "item": service.get_profile()})

    @blueprint.put("/api/oie/settings")
    def update_oie_settings():
        payload = request.get_json(silent=True)
        try:
            item = service.update_profile(payload)
        except SimulatorValidationError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        return jsonify({"success": True, "item": item})

    return blueprint
