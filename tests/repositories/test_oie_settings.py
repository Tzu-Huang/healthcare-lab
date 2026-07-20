import json
import tempfile
import unittest
from pathlib import Path

from backend.domain.errors import SimulatorValidationError
from backend.application_composition import assemble_application_dependencies
from backend.repositories.oie_settings import OieMappingConflictError, OieSettingsRepository


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

    @staticmethod
    def audit(operation_id="operation-1", **overrides):
        event = {
            "operation_id": operation_id,
            "actor": "local-operator",
            "operation": "update",
            "logical_type": "hlab-orm-to-ap",
            "channel_id": "channel-1",
            "before_revision": "7",
            "after_revision": "8",
            "classification": "drifted",
            "outcome": "success",
            "error_category": "",
            "changed_owned_fields": ["destination.port"],
        }
        event.update(overrides)
        return event

    def seed_mappings(self):
        self.repository.update(self.settings_payload(managedChannels=[
            {"logicalType": "hlab-orm-to-ap", "channelId": "channel-1",
             "channelName": "HLAB_ORM_TO_AP", "templateVersion": "1",
             "lastKnownRevision": "7"},
            {"logicalType": "hlab-oru-to-hlab", "channelId": "channel-2",
             "channelName": "HLAB_ORU_TO_HLAB", "templateVersion": "1",
             "lastKnownRevision": "3"},
        ]))

    def test_targeted_update_preserves_profile_and_unrelated_mapping(self):
        self.seed_mappings()
        before = self.repository.get()

        updated = self.repository.compare_and_update_managed_channel_mapping(
            logical_type="hlab-orm-to-ap", expected_channel_id="channel-1",
            expected_revision="7", channel_id="channel-1",
            channel_name="HLAB_ORM_TO_AP", template_version="1", revision="8",
            audit_event=self.audit(),
        )

        after = self.repository.get()
        self.assertEqual("8", updated["lastKnownRevision"])
        self.assertEqual(before["managementApi"], after["managementApi"])
        self.assertEqual(before["resultListener"], after["resultListener"])
        self.assertEqual(before["managedChannels"][1], after["managedChannels"][1])
        self.assertEqual("operation-1", self.repository.list_managed_channel_lifecycle_audits()[0]["operation_id"])

    def test_stale_mapping_update_rolls_back_audit(self):
        self.seed_mappings()
        for field, value in (("expected_channel_id", "stale"), ("expected_revision", "6")):
            arguments = dict(
                logical_type="hlab-orm-to-ap", expected_channel_id="channel-1",
                expected_revision="7", channel_id="channel-1",
                channel_name="HLAB_ORM_TO_AP", template_version="1", revision="8",
                audit_event=self.audit(f"stale-{field}"),
            )
            arguments[field] = value
            with self.assertRaises(OieMappingConflictError):
                self.repository.compare_and_update_managed_channel_mapping(**arguments)
        self.assertEqual([], self.repository.list_managed_channel_lifecycle_audits())
        self.assertEqual("7", self.repository.get()["managedChannels"][0]["lastKnownRevision"])

    def test_clear_retains_template_identity_and_writes_audit(self):
        self.seed_mappings()
        cleared = self.repository.compare_and_clear_managed_channel_mapping(
            logical_type="hlab-orm-to-ap", expected_channel_id="channel-1",
            expected_revision="7", audit_event=self.audit(operation_id="delete-1", operation="delete",
                after_revision="", outcome="success"),
        )
        self.assertEqual("", cleared["channelId"])
        self.assertEqual("", cleared["lastKnownRevision"])
        self.assertEqual("HLAB_ORM_TO_AP", cleared["channelName"])
        self.assertEqual("1", cleared["templateVersion"])

    def test_duplicate_audit_rolls_back_mapping_change(self):
        self.seed_mappings()
        self.repository.append_managed_channel_lifecycle_audit(self.audit())
        with self.assertRaises(OieMappingConflictError):
            self.repository.compare_and_update_managed_channel_mapping(
                logical_type="hlab-orm-to-ap", expected_channel_id="channel-1",
                expected_revision="7", channel_id="channel-1",
                channel_name="HLAB_ORM_TO_AP", template_version="1", revision="8",
                audit_event=self.audit(),
            )
        self.assertEqual("7", self.repository.get()["managedChannels"][0]["lastKnownRevision"])

    def test_audit_allowlist_rejects_sensitive_and_arbitrary_content(self):
        for forbidden in ("password", "cookie", "authorization", "payload", "hl7", "patient_mrn"):
            with self.assertRaisesRegex(ValueError, "unsupported fields"):
                self.repository.append_managed_channel_lifecycle_audit(
                    self.audit(**{forbidden: "sensitive-value"})
                )
        self.assertEqual([], self.repository.list_managed_channel_lifecycle_audits())

    def test_nonempty_channel_id_cannot_be_claimed_twice(self):
        self.repository.update(self.settings_payload(managedChannels=[
            {"logicalType": "hlab-orm-to-ap", "channelName": "HLAB_ORM_TO_AP"},
            {"logicalType": "hlab-oru-to-hlab", "channelName": "HLAB_ORU_TO_HLAB"},
        ]))
        self.repository.compare_and_update_managed_channel_mapping(
            logical_type="hlab-orm-to-ap", expected_channel_id="", expected_revision="",
            channel_id="same-channel", channel_name="HLAB_ORM_TO_AP",
            template_version="1", revision="1",
        )
        with self.assertRaises(OieMappingConflictError):
            self.repository.compare_and_update_managed_channel_mapping(
                logical_type="hlab-oru-to-hlab", expected_channel_id="", expected_revision="",
                channel_id="same-channel", channel_name="HLAB_ORU_TO_HLAB",
                template_version="1", revision="1",
            )


if __name__ == "__main__":
    unittest.main()
