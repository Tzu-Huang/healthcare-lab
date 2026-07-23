from __future__ import annotations

import copy
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

    def test_lab_inventory_cannot_mutate_typed_medplum_base_url(self):
        servers = self.client.get("/api/lab/servers").get_json()["items"]
        medplum = next(item for item in servers if item["name"] == "Medplum")
        before = self.app.extensions["integration_settings_service"].get_effective(
            "medplum"
        ).base_url

        response = self.client.put(
            f"/api/lab/servers/{medplum['id']}",
            json={"baseUrl": "https://competing-owner.example/fhir/R4"},
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual(
            "Medplum baseUrl is owned by the typed Settings profile.",
            response.get_json()["error"],
        )
        self.assertEqual(
            before,
            self.app.extensions["integration_settings_service"].get_effective(
                "medplum"
            ).base_url,
        )

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

    def test_lab_inventory_projects_canonical_medplum_urls(self):
        service = self.app.extensions["integration_settings_service"]
        fields = dict(service.get_public("medplum")["fields"])
        fields["baseUrl"] = "https://canonical.example/fhir/R4"
        fields["webUiUrl"] = "https://canonical.example/app"
        service.replace("medplum", fields)

        servers = self.client.get("/api/lab/servers").get_json()["items"]
        medplum = next(item for item in servers if item["name"] == "Medplum")

        self.assertEqual("https://canonical.example/fhir/R4", medplum["baseUrl"])
        self.assertEqual("https://canonical.example/app", medplum["webUiUrl"])
        self.assertEqual("medplum", medplum["settingsProfile"])

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
                    "webUiUrl": "http://127.0.0.1:3000",
                    "clientId": "",
                    "scope": "",
                    "tokenUrl": "",
                    "authGraceSeconds": 300,
                    "timeoutSeconds": 10,
                    "enabled": True,
                }
            },
        )
        body = response.get_json()
        self.assertEqual(400, response.status_code)
        self.assertEqual("settings_validation_failed", body["error"]["code"])
        self.assertEqual("baseUrl", body["error"]["fields"][0]["field"])
        self.assertNotIn(canary, response.get_data(as_text=True))

    def test_auth_grace_rejects_booleans_and_accepts_integer(self):
        fields = self.app.extensions["integration_settings_service"].get_public(
            "medplum"
        )["fields"]
        for value in (True, False):
            invalid = dict(fields)
            invalid["authGraceSeconds"] = value
            response = self.client.put(
                "/api/settings/profiles/medplum", json={"fields": invalid}
            )
            self.assertEqual(400, response.status_code)
            self.assertEqual(
                "authGraceSeconds",
                response.get_json()["error"]["fields"][0]["field"],
            )

        valid = dict(fields)
        valid["authGraceSeconds"] = 45
        response = self.client.put(
            "/api/settings/profiles/medplum", json={"fields": valid}
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(45, response.get_json()["item"]["fields"]["authGraceSeconds"])

    def test_save_and_test_persists_profile_and_returns_independent_stages(self):
        service = self.app.extensions["integration_settings_service"]
        fields = dict(service.get_public("medplum")["fields"])
        fields["enabled"] = False

        response = self.client.post(
            "/api/settings/profiles/medplum/save-and-test",
            json={"fields": fields, "secrets": {"clientSecret": ""}},
        )

        self.assertEqual(200, response.status_code)
        body = response.get_json()
        self.assertTrue(body["saved"])
        self.assertFalse(service.get_effective("medplum").enabled)
        self.assertEqual(
            ["metadata", "oauth", "authenticated-read"],
            [stage["stage"] for stage in body["diagnostics"]["stages"]],
        )
        self.assertTrue(
            all(
                stage["state"] == "disabled"
                for stage in body["diagnostics"]["stages"]
            )
        )

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

    def test_oie_rejects_unknown_secret_with_stable_field_error(self):
        fields = self.app.extensions["integration_settings_service"].get_public("oie")[
            "fields"
        ]
        response = self.client.put(
            "/api/settings/profiles/oie",
            json={"fields": fields, "secrets": {"arbitrary": "canary"}},
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual(
            "secrets.arbitrary",
            response.get_json()["error"]["fields"][0]["field"],
        )
        self.assertNotIn("canary", response.get_data(as_text=True))

    def test_oie_rejects_unknown_fields_at_every_schema_level(self):
        original = self.app.extensions["integration_settings_service"].get_public(
            "oie"
        )["fields"]
        cases = (
            ("arbitrary", lambda fields: fields.__setitem__("arbitrary", "value-canary")),
            (
                "managementApi.arbitrary",
                lambda fields: fields["managementApi"].__setitem__(
                    "arbitrary", "value-canary"
                ),
            ),
            (
                "resultListener.arbitrary",
                lambda fields: fields["resultListener"].__setitem__(
                    "arbitrary", "value-canary"
                ),
            ),
            (
                "managedChannels[0].arbitrary",
                lambda fields: fields["managedChannels"][0].__setitem__(
                    "arbitrary", "value-canary"
                ),
            ),
        )
        for expected_path, mutate in cases:
            with self.subTest(field=expected_path):
                fields = copy.deepcopy(original)
                mutate(fields)
                response = self.client.put(
                    "/api/settings/profiles/oie", json={"fields": fields}
                )

                self.assertEqual(400, response.status_code)
                issue = response.get_json()["error"]["fields"][0]
                self.assertEqual(expected_path, issue["field"])
                self.assertEqual("unknown_field", issue["code"])
                self.assertNotIn("value-canary", response.get_data(as_text=True))

    def test_oie_validation_returns_stable_field_path(self):
        fields = self.app.extensions["integration_settings_service"].get_public("oie")[
            "fields"
        ]
        fields["managementApi"]["baseUrl"] = "private-value-canary"
        response = self.client.put(
            "/api/settings/profiles/oie", json={"fields": fields}
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual(
            "managementApi.baseUrl",
            response.get_json()["error"]["fields"][0]["field"],
        )
        self.assertNotIn("private-value-canary", response.get_data(as_text=True))

    def test_oie_password_can_be_explicitly_removed(self):
        service = self.app.extensions["integration_settings_service"]
        fields = service.get_public("oie")["fields"]
        service.replace(
            "oie",
            fields,
            secret_replacements={"managementApi.password": "configured-canary"},
        )

        response = self.client.delete(
            "/api/settings/profiles/oie/secrets/managementApi.password", json={}
        )

        self.assertEqual(200, response.status_code)
        self.assertFalse(
            response.get_json()["item"]["secrets"]["managementApi.password"][
                "configured"
            ]
        )
        self.assertEqual(
            "",
            service.get_effective("oie")["managementApi"]["password"],
        )
        existing = self.client.get("/api/oie/settings")
        self.assertEqual(200, existing.status_code)
        self.assertFalse(
            existing.get_json()["item"]["managementApi"]["passwordConfigured"]
        )
