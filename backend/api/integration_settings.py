"""Stable HTTP boundary for typed integration settings profiles."""

from __future__ import annotations

from typing import Any, Callable, Protocol

from flask import Blueprint, jsonify, request

from backend.domain.integration_settings import TypedSettingsValidationError
from backend.domain.errors import SimulatorValidationError


class IntegrationSettingsPort(Protocol):
    def get_public(self, profile_type: str) -> dict[str, Any]: ...

    def replace(
        self,
        profile_type: str,
        fields: dict[str, Any],
        *,
        secret_replacements: dict[str, Any] | None = None,
        actor: str = "local-operator",
    ) -> dict[str, Any]: ...

    def remove_secret(
        self,
        profile_type: str,
        field: str,
        *,
        actor: str = "local-operator",
    ) -> dict[str, Any]: ...


def create_integration_settings_blueprint(
    settings: IntegrationSettingsPort,
    *,
    medplum_diagnostics: Callable[[], dict[str, Any]] | None = None,
) -> Blueprint:
    blueprint = Blueprint("integration_settings", __name__)

    def validation_error(exc: TypedSettingsValidationError):
        return jsonify({"success": False, "error": exc.as_dict()}), 400

    def bounded_error(code: str, message: str, status: int):
        return jsonify(
            {"success": False, "error": {"code": code, "message": message}}
        ), status

    @blueprint.get("/api/settings/profiles/<profile_type>")
    def get_profile(profile_type: str):
        try:
            item = settings.get_public(profile_type)
        except KeyError:
            return bounded_error(
                "settings_profile_not_found", "Settings profile was not found.", 404
            )
        return jsonify({"success": True, "item": item})

    @blueprint.put("/api/settings/profiles/<profile_type>")
    def replace_profile(profile_type: str):
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or set(body) - {"fields", "secrets"}:
            return bounded_error(
                "invalid_settings_request",
                "Request must contain only fields and optional secrets.",
                400,
            )
        fields = body.get("fields")
        secrets = body.get("secrets", {})
        if not isinstance(fields, dict) or not isinstance(secrets, dict):
            return bounded_error(
                "invalid_settings_request",
                "Settings fields and secrets must be JSON objects.",
                400,
            )
        try:
            item = settings.replace(
                profile_type, fields, secret_replacements=secrets
            )
        except TypedSettingsValidationError as exc:
            return validation_error(exc)
        except KeyError:
            return bounded_error(
                "settings_profile_not_found", "Settings profile was not found.", 404
            )
        except SimulatorValidationError:
            return bounded_error(
                "settings_validation_failed",
                "Integration settings validation failed.",
                400,
            )
        except ValueError:
            return bounded_error(
                "invalid_settings_request", "Settings request was rejected.", 400
            )
        return jsonify({"success": True, "item": item})

    @blueprint.post("/api/settings/profiles/medplum/save-and-test")
    def save_and_test_medplum():
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or set(body) - {"fields", "secrets"}:
            return bounded_error(
                "invalid_settings_request",
                "Request must contain only fields and optional secrets.",
                400,
            )
        fields = body.get("fields")
        secrets = body.get("secrets", {})
        if not isinstance(fields, dict) or not isinstance(secrets, dict):
            return bounded_error(
                "invalid_settings_request",
                "Settings fields and secrets must be JSON objects.",
                400,
            )
        try:
            item = settings.replace(
                "medplum", fields, secret_replacements=secrets
            )
        except TypedSettingsValidationError as exc:
            return validation_error(exc)
        except (KeyError, ValueError, SimulatorValidationError):
            return bounded_error(
                "settings_save_rejected", "Medplum settings were not saved.", 400
            )
        diagnostics = (
            medplum_diagnostics()
            if medplum_diagnostics is not None
            else {"state": "unavailable", "stages": []}
        )
        return jsonify(
            {
                "success": True,
                "saved": True,
                "item": item,
                "diagnostics": diagnostics,
            }
        )

    @blueprint.delete(
        "/api/settings/profiles/<profile_type>/secrets/<path:field>"
    )
    def remove_profile_secret(profile_type: str, field: str):
        body = request.get_json(silent=True)
        if body not in (None, {}):
            return bounded_error(
                "invalid_settings_request",
                "Secret removal accepts no request fields.",
                400,
            )
        try:
            item = settings.remove_secret(profile_type, field)
        except TypedSettingsValidationError as exc:
            return validation_error(exc)
        except KeyError:
            return bounded_error(
                "settings_profile_not_found", "Settings profile was not found.", 404
            )
        except ValueError:
            return bounded_error(
                "secret_removal_rejected",
                "The requested secret cannot be removed.",
                400,
            )
        return jsonify({"success": True, "item": item})

    return blueprint
