from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from backend.api.integration_settings import create_integration_settings_blueprint
from backend.api.settings_readiness import create_settings_readiness_blueprint
from backend.app_factory import create_app
from backend.settings_readiness_composition import create_settings_readiness_service


def _diagnostic(state: str) -> dict:
    if state == "healthy":
        stages = [
            {"stage": "metadata", "state": "passed", "category": "reachable"},
            {"stage": "oauth", "state": "passed", "category": "authorized"},
            {
                "stage": "authenticated-read",
                "state": "passed",
                "category": "readable",
            },
        ]
    else:
        stages = [
            {"stage": "metadata", "state": "passed", "category": "reachable"},
            {
                "stage": "oauth",
                "state": "failed",
                "category": "authorization-failure",
            },
            {
                "stage": "authenticated-read",
                "state": "skipped",
                "category": "oauth-unavailable",
            },
        ]
    return {
        "state": state,
        "stages": stages,
    }


class _PersistedSettings:
    """Small persistent port used to exercise HTTP and readiness composition."""

    def __init__(self) -> None:
        self.fields = {
            "enabled": True,
            "baseUrl": "https://medplum.example/fhir/R4",
            "webUiUrl": "https://medplum.example/app",
            "clientId": "client",
            "scope": "openid",
            "tokenUrl": "https://medplum.example/oauth/token",
            "authGraceSeconds": 300,
            "timeoutSeconds": 10,
        }
        self.revision = 1
        self.verification = None

    def get_public(self, profile_type):
        if profile_type == "medplum":
            return {
                "profileType": "medplum",
                "fields": copy.deepcopy(self.fields),
                "secrets": {"clientSecret": {"configured": True}},
            }
        if profile_type in ("gdt-bridge", "dcm4chee"):
            return {"fields": {"enabled": False}}
        if profile_type == "oie":
            return {
                "fields": {
                    "managementApi": {
                        "baseUrl": "http://oie",
                        "username": "operator",
                    },
                    "resultListener": {"autoStart": False},
                },
                "secrets": {"managementApi.password": {"configured": True}},
            }
        raise KeyError(profile_type)

    def has_operator_configuration(self, profile_type):
        return profile_type == "medplum"

    def replace(self, profile_type, fields, *, secret_replacements=None, actor=None):
        if profile_type != "medplum":
            raise KeyError(profile_type)
        self.fields = copy.deepcopy(fields)
        self.revision += 1
        return self.get_public(profile_type)

    def get_medplum_configuration_revision(self):
        return self.revision

    def record_medplum_verification(self, configuration_revision, report):
        if configuration_revision != self.revision:
            return False
        self.verification = {
            "configurationRevision": configuration_revision,
            "state": report["state"],
            "stages": copy.deepcopy(report["stages"]),
        }
        return True

    def get_medplum_verification(self):
        return copy.deepcopy(self.verification)


def _readiness(settings):
    return create_settings_readiness_service(
        settings,
        listener_status=lambda: {"running": False},
        oie_diagnostics=lambda: {"state": "healthy"},
        gdt_watcher_status=lambda: {"running": False},
        gdt_activation_status=lambda: {
            "state": "effective",
            "activation": "immediate",
        },
        gdt_diagnostics=lambda: {"state": "disabled"},
        gdt_check_diagnostics=lambda: {"state": "disabled"},
        dcm4chee_diagnostics=lambda: {"state": "disabled", "checks": []},
    )


def _section(client):
    payload = client.get("/api/settings/readiness").get_json()["item"]
    return payload, next(
        item for item in payload["sections"] if item["id"] == "medplum"
    )


class Zac80MedplumReadinessTests(unittest.TestCase):
    def _client(self, settings, diagnostics):
        app = Flask(__name__)
        app.register_blueprint(
            create_integration_settings_blueprint(
                settings, medplum_diagnostics=diagnostics
            )
        )
        app.register_blueprint(create_settings_readiness_blueprint(_readiness(settings)))
        return app.test_client()

    def _save_and_test(self, client, settings):
        return client.post(
            "/api/settings/profiles/medplum/save-and-test",
            json={"fields": settings.fields, "secrets": {"clientSecret": ""}},
        )

    def test_matching_success_is_ready_and_readiness_does_not_probe_network(self):
        settings = _PersistedSettings()
        calls = []

        def diagnostics():
            calls.append("explicit-check")
            return _diagnostic("healthy")

        client = self._client(settings, diagnostics)
        self.assertEqual(200, self._save_and_test(client, settings).status_code)
        payload, section = _section(client)

        self.assertEqual("ready", section["state"])
        self.assertTrue(payload["complete"])
        self.assertEqual(["explicit-check"], calls)

    def test_matching_failure_is_degraded_and_later_success_replaces_it(self):
        settings = _PersistedSettings()
        reports = iter((_diagnostic("degraded"), _diagnostic("healthy")))
        client = self._client(settings, lambda: next(reports))

        self._save_and_test(client, settings)
        payload, section = _section(client)
        self.assertEqual("degraded", section["state"])
        self.assertFalse(payload["complete"])

        self._save_and_test(client, settings)
        payload, section = _section(client)
        self.assertEqual("ready", section["state"])
        self.assertTrue(payload["complete"])

    def test_missing_and_stale_evidence_need_setup_and_stale_check_cannot_win(self):
        settings = _PersistedSettings()
        client = self._client(settings, lambda: _diagnostic("healthy"))
        _, section = _section(client)
        self.assertEqual("needs-setup", section["state"])

        settings.verification = {
            "configurationRevision": settings.revision - 1,
            "state": "healthy",
            "stages": _diagnostic("healthy")["stages"],
        }
        _, section = _section(client)
        self.assertEqual("needs-setup", section["state"])

        checked_revision = settings.get_medplum_configuration_revision()
        settings.revision += 1
        self.assertFalse(
            settings.record_medplum_verification(
                checked_revision, _diagnostic("healthy")
            )
        )
        _, section = _section(
            self._client(settings, lambda: self.fail("network probe"))
        )
        self.assertEqual("needs-setup", section["state"])

    def test_failed_verification_survives_real_app_reconstruction_on_same_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "app.db")
            first = create_app(database, activate_runtime=False)
            settings = first.extensions["integration_settings_service"]
            fields = dict(settings.get_public("medplum")["fields"])
            fields.update(
                {
                    "enabled": True,
                    "baseUrl": "https://medplum.example/fhir/R4",
                    "clientId": "client",
                }
            )
            settings.replace(
                "medplum",
                fields,
                secret_replacements={"clientSecret": "synthetic-secret"},
            )
            revision = settings.get_medplum_configuration_revision()
            self.assertTrue(
                settings.record_medplum_verification(
                    revision, _diagnostic("degraded")
                )
            )

            restarted = create_app(database, activate_runtime=False)
            payload = restarted.test_client().get(
                "/api/settings/readiness"
            ).get_json()["item"]
            section = next(
                item for item in payload["sections"] if item["id"] == "medplum"
            )

            self.assertEqual("degraded", section["state"])
            self.assertFalse(payload["complete"])

    def test_inconsistent_healthy_evidence_cannot_authorize_real_app_readiness(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(
                str(Path(directory) / "app.db"),
                activate_runtime=False,
            )
            settings = app.extensions["integration_settings_service"]
            fields = dict(settings.get_public("medplum")["fields"])
            fields.update(
                {
                    "enabled": True,
                    "baseUrl": "https://medplum.example/fhir/R4",
                    "clientId": "client",
                }
            )
            settings.replace(
                "medplum",
                fields,
                secret_replacements={"clientSecret": "synthetic-secret"},
            )
            revision = settings.get_medplum_configuration_revision()

            with self.assertRaises(ValueError):
                settings.record_medplum_verification(
                    revision,
                    {
                        **_diagnostic("degraded"),
                        "state": "healthy",
                    },
                )

            payload = app.test_client().get(
                "/api/settings/readiness"
            ).get_json()["item"]
            section = next(
                item for item in payload["sections"] if item["id"] == "medplum"
            )
            self.assertEqual("needs-setup", section["state"])
            self.assertFalse(payload["complete"])


if __name__ == "__main__":
    unittest.main()
