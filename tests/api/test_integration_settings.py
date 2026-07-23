from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app_factory import create_app


class IntegrationSettingsApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.app = create_app(
            str(Path(self.temporary.name) / "settings.db"),
            activate_runtime=False,
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temporary.cleanup()

    def test_medplum_read_is_typed_and_secret_safe(self):
        response = self.client.get("/api/settings/profiles/medplum")
        body = response.get_json()
        self.assertEqual(200, response.status_code)
        self.assertEqual("medplum", body["item"]["profileType"])
        self.assertIn("configured", body["item"]["secrets"]["clientSecret"])
        self.assertNotIn("MEDPLUM_CLIENT_SECRET", response.get_data(as_text=True))

    def test_replace_uses_blank_secret_as_preserve(self):
        service = self.app.extensions["integration_settings_service"]
        before = service.get_effective("medplum").client_secret
        fields = service.get_public("medplum")["fields"]
        fields["clientId"] = "api-client"
        response = self.client.put(
            "/api/settings/profiles/medplum",
            json={"fields": fields, "secrets": {"clientSecret": ""}},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(before, service.get_effective("medplum").client_secret)

    def test_explicit_remove_is_distinct_and_value_free(self):
        response = self.client.delete(
            "/api/settings/profiles/medplum/secrets/clientSecret", json={}
        )
        self.assertEqual(200, response.status_code)
        self.assertFalse(
            response.get_json()["item"]["secrets"]["clientSecret"]["configured"]
        )

    def test_invalid_profile_returns_stable_field_errors_without_values(self):
        canary = "secret-url-canary"
        response = self.client.put(
            "/api/settings/profiles/medplum",
            json={
                "fields": {
                    "baseUrl": canary,
                    "clientId": "",
                    "scope": "",
                    "tokenUrl": "",
                    "authGraceSeconds": 300,
                    "enabled": True,
                }
            },
        )
        body = response.get_json()
        self.assertEqual(400, response.status_code)
        self.assertEqual("settings_validation_failed", body["error"]["code"])
        self.assertEqual("baseUrl", body["error"]["fields"][0]["field"])
        self.assertNotIn(canary, response.get_data(as_text=True))

    def test_unknown_request_fields_are_rejected(self):
        response = self.client.put(
            "/api/settings/profiles/medplum",
            json={"fields": {}, "arbitrary": "canary"},
        )
        self.assertEqual(400, response.status_code)
        self.assertEqual("invalid_settings_request", response.get_json()["error"]["code"])

    def test_oie_adapter_preserves_existing_endpoint_shape_and_private_secret(self):
        service = self.app.extensions["integration_settings_service"]
        fields = service.get_public("oie")["fields"]
        service.replace(
            "oie",
            fields,
            secret_replacements={"managementApi.password": "oie-secret-canary"},
        )
        shared = self.client.get("/api/settings/profiles/oie")
        existing = self.client.get("/api/oie/settings")
        self.assertEqual(200, shared.status_code)
        self.assertEqual(200, existing.status_code)
        self.assertEqual("oie", shared.get_json()["item"]["profileType"])
        self.assertIn("passwordConfigured", existing.get_json()["item"]["managementApi"])
        self.assertNotIn("oie-secret-canary", shared.get_data(as_text=True))
        self.assertNotIn("oie-secret-canary", existing.get_data(as_text=True))
        effective = self.app.extensions["integration_settings_service"].get_effective("oie")
        self.assertEqual("oie-secret-canary", effective["managementApi"]["password"])
