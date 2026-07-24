"""HTTP boundary for AP/external-device profiles."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.domain.integration_settings import TypedSettingsValidationError
from backend.repositories.ap_device_profiles import DuplicateAPProfileNameError


def create_ap_device_profiles_blueprint(service) -> Blueprint:
    blueprint = Blueprint("ap_device_profiles", __name__)

    def error(code: str, message: str, status: int, *, fields=None):
        payload = {"code": code, "message": message}
        if fields is not None:
            payload["fields"] = fields
        return jsonify({"success": False, "error": payload}), status

    @blueprint.get("/api/settings/external-devices")
    def list_profiles():
        environment = request.args.get("environment")
        items = service.list(environment)
        return jsonify({"success": True, "items": items})

    @blueprint.post("/api/settings/external-devices")
    def create_profile():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return error("invalid-request", "Profile must be a JSON object.", 400)
        try:
            item = service.create(body)
        except TypedSettingsValidationError as exc:
            return error(
                "settings_validation_failed",
                "Device profile validation failed.",
                400,
                fields=exc.as_dict()["fields"],
            )
        except DuplicateAPProfileNameError:
            return error(
                "duplicate-profile-name",
                "A device profile with this name already exists.",
                409,
                fields=[{"field": "name", "code": "duplicate-profile-name", "reason": "Profile name must be unique."}],
            )
        except ValueError:
            return error("invalid-request", "Device profile was rejected.", 400)
        return jsonify({"success": True, "item": item}), 201

    @blueprint.get("/api/settings/external-devices/<profile_id>")
    def get_profile(profile_id: str):
        try:
            item = service.get(profile_id)
        except KeyError:
            return error("profile-not-found", "Device profile was not found.", 404)
        return jsonify({"success": True, "item": item})

    @blueprint.put("/api/settings/external-devices/<profile_id>")
    def update_profile(profile_id: str):
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return error("invalid-request", "Profile must be a JSON object.", 400)
        try:
            item = service.update(profile_id, body)
        except KeyError:
            return error("profile-not-found", "Device profile was not found.", 404)
        except TypedSettingsValidationError as exc:
            return error(
                "settings_validation_failed",
                "Device profile validation failed.",
                400,
                fields=exc.as_dict()["fields"],
            )
        except (DuplicateAPProfileNameError, ValueError):
            return error("profile-conflict", "Device profile update was rejected.", 409)
        return jsonify({"success": True, "item": item})

    @blueprint.put("/api/settings/external-devices/<profile_id>/default")
    def select_default(profile_id: str):
        if request.get_json(silent=True) not in ({}, None):
            return error("invalid-request", "Default selection accepts no fields.", 400)
        try:
            item = service.select_default(profile_id)
        except KeyError:
            return error("profile-not-found", "Device profile was not found.", 404)
        except ValueError:
            return error("profile-disabled", "A disabled profile cannot be default.", 409)
        return jsonify({"success": True, "item": item})

    @blueprint.post("/api/settings/external-devices/<profile_id>/diagnostics")
    def diagnose(profile_id: str):
        if request.get_json(silent=True) not in ({}, None):
            return error("invalid-request", "Diagnostics accepts no fields.", 400)
        try:
            result = service.diagnose(profile_id)
        except KeyError:
            return error("profile-not-found", "Device profile was not found.", 404)
        return jsonify({"success": True, **result})

    return blueprint
