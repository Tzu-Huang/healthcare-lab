import json
import tempfile
import unittest
from pathlib import Path

from backend.domain.errors import SimulatorValidationError
from backend.application_composition import assemble_application_dependencies
from backend.repositories.oie_settings import OieSettingsRepository


class OieSettingsRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.dependencies = assemble_application_dependencies(Path(self.directory.name) / "lab.db")
        self.repository = self.dependencies.oie_settings_repository

    def tearDown(self):
        self.directory.cleanup()

    @staticmethod
    def settings_payload(**overrides):
        payload = {
            "managementApi": {
                "baseUrl": "http://oie:8080",
                "username": "admin",
                "tlsVerify": False,
                "timeoutSeconds": 10,
            },
            "resultListener": {
                "host": "0.0.0.0",
                "port": 6665,
                "mllpFraming": True,
                "autoStart": True,
            },
            "managedChannels": [],
        }
        payload.update(overrides)
        return payload

    def test_store_exposes_repository_with_seeded_profile(self):
        self.assertIsInstance(self.repository, OieSettingsRepository)
        self.assertEqual("local-oie", self.repository.get()["profileName"])

    def test_profile_seeds_secret_safe_local_defaults(self):
        profile = self.repository.get()

        self.assertEqual(profile["profileName"], "local-oie")
        self.assertEqual(profile["managementApi"]["baseUrl"], "http://oie:8080")
        self.assertEqual(profile["managementApi"]["username"], "admin")
        self.assertTrue(profile["managementApi"]["passwordConfigured"])
        self.assertFalse(profile["managementApi"]["tlsVerify"])
        self.assertEqual(profile["managementApi"]["timeoutSeconds"], 10)
        self.assertEqual(
            profile["resultListener"],
            {
                "host": "0.0.0.0",
                "port": 6665,
                "mllpFraming": True,
                "autoStart": True,
            },
        )
        self.assertNotIn("password", profile["managementApi"])
        self.assertNotIn("Admin", json.dumps(profile))
        with self.dependencies.database.connect() as connection:
            password = connection.execute(
                "SELECT management_api_password FROM oie_settings_profiles"
            ).fetchone()[0]
        self.assertEqual(password, "Admin")

    def test_private_management_configuration_is_separate_from_public_projection(self):
        public_profile = self.repository.get()
        private_configuration = self.repository.get_management_api_configuration()

        self.assertNotIn("password", public_profile["managementApi"])
        self.assertEqual("Admin", private_configuration["password"])
        self.assertEqual(10.0, private_configuration["timeout_seconds"])

    def test_private_listener_configuration_is_narrow_and_persisted(self):
        self.repository.update(self.settings_payload(resultListener={
            "host": "127.0.0.1", "port": 7765,
            "mllpFraming": False, "autoStart": False,
        }))

        configuration = self.repository.get_result_listener_configuration()

        self.assertEqual({
            "host": "127.0.0.1", "port": 7765,
            "mllp_framing": False, "auto_start": False,
        }, configuration)
        self.assertNotIn("password", configuration)
        self.assertNotIn("base_url", configuration)

    def test_update_persists_and_replaces_channel_mappings(self):
        payload = self.settings_payload(
            managementApi={
                "baseUrl": "https://oie.example.test/api",
                "username": "operator",
                "password": "replacement-secret",
                "tlsVerify": True,
                "timeoutSeconds": 12.5,
            },
            resultListener={
                "host": "127.0.0.1",
                "port": 7665,
                "mllpFraming": False,
                "autoStart": False,
            },
            managedChannels=[
                {
                    "logicalType": "HLAB-RESULT",
                    "channelId": "channel-1",
                    "channelName": "HLAB Result",
                    "templateVersion": "1.2.0",
                    "lastKnownRevision": "42",
                }
            ],
        )

        updated = self.repository.update(payload)
        reopened = assemble_application_dependencies(self.dependencies.database.path)
        persisted = reopened.oie_settings_repository.get()

        self.assertEqual(updated, persisted)
        self.assertEqual(persisted["managementApi"]["timeoutSeconds"], 12.5)
        self.assertEqual(persisted["managedChannels"][0]["logicalType"], "hlab-result")
        self.assertEqual(persisted["managedChannels"][0]["channelId"], "channel-1")
        self.assertNotIn("replacement-secret", json.dumps(persisted))

        replacement = self.settings_payload(
            managedChannels=[
                {"logicalType": "order-ingress", "channelName": "Order Ingress"}
            ]
        )
        replaced = reopened.oie_settings_repository.update(replacement)
        self.assertEqual(
            [item["logicalType"] for item in replaced["managedChannels"]],
            ["order-ingress"],
        )
        with reopened.database.connect() as connection:
            password = connection.execute(
                "SELECT management_api_password FROM oie_settings_profiles"
            ).fetchone()[0]
        self.assertEqual(password, "replacement-secret")

    def test_rejects_duplicate_logical_types_atomically(self):
        original = self.repository.update(
            self.settings_payload(
                managedChannels=[
                    {"logicalType": "result", "channelName": "Original Result"}
                ]
            )
        )
        invalid = self.settings_payload(
            managedChannels=[
                {"logicalType": "RESULT", "channelName": "One"},
                {"logicalType": "result", "channelName": "Two"},
            ]
        )

        with self.assertRaisesRegex(SimulatorValidationError, "duplicate logicalType 'result'"):
            self.repository.update(invalid)

        self.assertEqual(self.repository.get(), original)


if __name__ == "__main__":
    unittest.main()
