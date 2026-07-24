from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.repositories.ap_device_profiles import (
    APDeviceProfileRepository,
    DuplicateAPProfileNameError,
)
from backend.repositories.database import SQLiteDatabase
from backend.repositories.schema import APPLICATION_MIGRATIONS


class APDeviceProfileRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database = SQLiteDatabase(
            Path(self.temporary.name) / "ap.db", migrations=APPLICATION_MIGRATIONS
        )
        self.database.initialize()
        self.repository = APDeviceProfileRepository(
            self.database.connect, self.database.lock,
            timestamp_factory=lambda: "2026-07-24T00:00:00+00:00",
        )

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def profile(name="ECG AP", **overrides):
        return {
            "profileName": name, "environment": " LAB ", "enabled": True,
            "isDefault": False, "hl7": {"enabled": True, "host": "secret-host"},
            **overrides,
        }

    def test_multiple_profiles_round_trip_and_normalize_environment(self):
        first = self.repository.create(self.profile())
        second = self.repository.create(self.profile("Backup AP"))
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual("lab", first["environment"])
        self.assertEqual(2, len(self.repository.list(environment="LAB")))

    def test_duplicate_normalized_name_is_rejected(self):
        self.repository.create(self.profile("  ECG   AP "))
        with self.assertRaises(DuplicateAPProfileNameError) as caught:
            self.repository.create(self.profile("ecg ap"))
        self.assertEqual("duplicate-profile-name", caught.exception.code)

    def test_default_selection_is_atomic_and_disabled_is_excluded(self):
        one = self.repository.create(self.profile("One", isDefault=True))
        two = self.repository.create(self.profile("Two"))
        selected = self.repository.select_default(two["id"])
        self.assertTrue(selected["isDefault"])
        self.assertFalse(self.repository.get(one["id"])["isDefault"])
        self.assertEqual(two["id"], self.repository.get_effective("lab")["id"])
        self.repository.update(two["id"], {"enabled": False, "isDefault": False})
        self.assertIsNone(self.repository.get_effective("lab"))
        with self.assertRaisesRegex(ValueError, "disabled"):
            self.repository.select_default(two["id"])

    def test_conflicting_default_create_rolls_back(self):
        self.repository.create(self.profile("One", isDefault=True))
        with self.assertRaisesRegex(ValueError, "at most one default"):
            self.repository.create(self.profile("Two", isDefault=True))
        self.assertEqual(["One"], [item["name"] for item in self.repository.list()])

    def test_audit_is_value_free_and_failure_rolls_back(self):
        created = self.repository.create(self.profile())
        serialized = json.dumps(self.repository.list_audits(created["id"]))
        self.assertNotIn("secret-host", serialized)
        with self.database.connect() as connection:
            connection.execute(
                """CREATE TRIGGER reject_ap_audit BEFORE INSERT ON ap_device_profile_audits
                BEGIN SELECT RAISE(ABORT, 'audit unavailable'); END"""
            )
        with self.assertRaisesRegex(Exception, "audit unavailable"):
            self.repository.update(created["id"], {"name": "Rolled Back"})
        self.assertEqual("ECG AP", self.repository.get(created["id"])["name"])

    def test_observations_are_closed_bounded_and_payload_free(self):
        created = self.repository.create(self.profile())
        safe = self.repository.record_observation({
            "profileKey": created["id"], "protocol": "hl7",
            "direction": "inbound", "outcomeCode": "accepted",
            "correlationKey": "transport-42",
        })
        self.assertEqual([safe], self.repository.list_observations(created["id"]))
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            self.repository.record_observation({
                "profileKey": created["id"], "protocol": "hl7",
                "direction": "inbound", "outcomeCode": "accepted",
                "payload": "MSH|patient",
            })
        self.assertNotIn("patient", json.dumps(self.repository.list_observations(created["id"])))


if __name__ == "__main__":
    unittest.main()
