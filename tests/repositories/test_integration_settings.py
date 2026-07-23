from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.domain.integration_settings import (
    medplum_bootstrap_candidate,
    preserve_secret,
    remove_secret,
    replace_secret,
    validate_profile,
)
from backend.repositories.database import SQLiteDatabase
from backend.repositories.integration_settings import IntegrationSettingsRepository
from backend.repositories.schema import APPLICATION_MIGRATIONS


class IntegrationSettingsRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database = SQLiteDatabase(
            Path(self.temporary.name) / "settings.db",
            migrations=APPLICATION_MIGRATIONS,
        )
        self.database.initialize()
        self.repository = IntegrationSettingsRepository(
            self.database.connect,
            self.database.lock,
            timestamp_factory=lambda: "2026-07-23T00:00:00+00:00",
        )

    def tearDown(self):
        self.temporary.cleanup()

    def seed(self, secret="initial-secret"):
        return self.repository.create_if_missing(
            medplum_bootstrap_candidate({"MEDPLUM_CLIENT_ID": "initial-client"}),
            secrets={"clientSecret": secret},
            bootstrap_source="environment",
        )

    def test_create_and_public_private_round_trip(self):
        self.assertTrue(self.seed())
        self.assertFalse(self.seed("must-not-overwrite"))
        public = self.repository.get_public("medplum")
        private = self.repository.get_private("medplum")
        self.assertEqual({"configured": True}, public["secrets"]["clientSecret"])
        self.assertNotIn("initial-secret", json.dumps(public))
        self.assertEqual("initial-secret", private["secrets"]["clientSecret"])
        self.assertEqual("initial-client", private["fields"]["clientId"])

    def test_replace_preserve_and_remove_are_atomic(self):
        self.seed()
        fields = dict(self.repository.get_private("medplum")["fields"])
        fields["clientId"] = "operator-client"
        profile = validate_profile("medplum", fields)
        preserved = self.repository.replace(
            profile, secret_mutations={"clientSecret": preserve_secret()}
        )
        self.assertTrue(preserved["secrets"]["clientSecret"]["configured"])
        self.assertEqual(
            "initial-secret",
            self.repository.get_private("medplum")["secrets"]["clientSecret"],
        )
        self.repository.replace(
            profile, secret_mutations={"clientSecret": replace_secret("replacement-canary")}
        )
        self.assertEqual(
            "replacement-canary",
            self.repository.get_private("medplum")["secrets"]["clientSecret"],
        )
        removed = self.repository.replace(
            profile, secret_mutations={"clientSecret": remove_secret()}
        )
        self.assertFalse(removed["secrets"]["clientSecret"]["configured"])

    def test_audits_are_allowlisted_and_value_free(self):
        self.seed("audit-secret-canary")
        fields = dict(self.repository.get_private("medplum")["fields"])
        fields["clientId"] = "audit-client-canary"
        self.repository.replace(
            validate_profile("medplum", fields),
            secret_mutations={"clientSecret": replace_secret("replacement-canary")},
        )
        serialized = json.dumps(self.repository.list_audits("medplum"))
        self.assertIn("clientSecret", serialized)
        for forbidden in (
            "audit-secret-canary",
            "audit-client-canary",
            "replacement-canary",
            "http://medplum",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_audit_failure_rolls_back_profile_and_secret(self):
        self.seed()
        before = self.repository.get_private("medplum")
        with self.database.connect() as connection:
            connection.execute(
                """
                CREATE TRIGGER reject_settings_audit
                BEFORE INSERT ON integration_settings_mutation_audits
                BEGIN SELECT RAISE(ABORT, 'audit unavailable'); END
                """
            )
        fields = dict(before["fields"])
        fields["clientId"] = "must-roll-back"
        with self.assertRaisesRegex(Exception, "audit unavailable"):
            self.repository.replace(
                validate_profile("medplum", fields),
                secret_mutations={"clientSecret": replace_secret("must-roll-back-secret")},
            )
        self.assertEqual(before, self.repository.get_private("medplum"))

    def test_unknown_secret_field_is_rejected_before_write(self):
        self.seed()
        profile = validate_profile(
            "medplum", self.repository.get_private("medplum")["fields"]
        )
        with self.assertRaisesRegex(ValueError, "Unsupported secret field"):
            self.repository.replace(
                profile,
                secret_mutations={"arbitrary": replace_secret("canary")},
            )
