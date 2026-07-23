from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.domain.integration_settings import (
    MEDPLUM_DEFAULT_TIMEOUT_SECONDS,
    MEDPLUM_DEFAULT_WEB_UI_URL,
    TypedSettingsValidationError,
    medplum_bootstrap_candidate,
    preserve_secret,
    remove_secret,
    replace_secret,
    validate_profile,
)
from backend.repositories.database import SQLiteDatabase
from backend.repositories.integration_settings import IntegrationSettingsRepository
from backend.repositories.schema import APPLICATION_MIGRATIONS
from backend.services.integration_settings import IntegrationSettingsService


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
        self.service = IntegrationSettingsService(self.repository)

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
        public = self.service.get_public("medplum")
        private = self.repository.get_private("medplum")
        self.assertEqual({"configured": True}, public["secrets"]["clientSecret"])
        self.assertNotIn("initial-secret", json.dumps(public))
        self.assertEqual("initial-secret", private["secrets"]["clientSecret"])
        self.assertEqual("initial-client", private["fields"]["clientId"])
        self.assertEqual(MEDPLUM_DEFAULT_WEB_UI_URL, private["fields"]["webUiUrl"])
        self.assertEqual(
            MEDPLUM_DEFAULT_TIMEOUT_SECONDS, private["fields"]["timeoutSeconds"]
        )

    def test_profile_normalizes_urls_and_rejects_out_of_range_timeout(self):
        fields = medplum_bootstrap_candidate({}).fields
        profile = validate_profile(
            "medplum",
            {
                **fields,
                "baseUrl": " https://medplum.example/fhir/R4/ ",
                "webUiUrl": " https://medplum.example/app/ ",
                "tokenUrl": " https://medplum.example/oauth/token/ ",
                "timeoutSeconds": 300,
            },
        )
        self.assertEqual("https://medplum.example/fhir/R4", profile.fields["baseUrl"])
        self.assertEqual("https://medplum.example/app", profile.fields["webUiUrl"])
        self.assertEqual(
            "https://medplum.example/oauth/token", profile.fields["tokenUrl"]
        )

        for invalid in (True, 0, 301, 1.5, "10"):
            with self.subTest(timeout=invalid), self.assertRaises(
                TypedSettingsValidationError
            ) as caught:
                validate_profile(
                    "medplum", {**fields, "timeoutSeconds": invalid}
                )
            self.assertEqual(
                "timeoutSeconds",
                next(
                    issue.field
                    for issue in caught.exception.issues
                    if issue.field == "timeoutSeconds"
                ),
            )

    def test_legacy_profile_migration_is_idempotent_and_preserves_secret(self):
        self.seed("migration-secret")
        with self.database.connect() as connection:
            row = connection.execute(
                """SELECT id, public_payload_json
                FROM integration_settings_profiles WHERE profile_type = 'medplum'"""
            ).fetchone()
            fields = json.loads(row["public_payload_json"])
            fields.pop("webUiUrl")
            fields.pop("timeoutSeconds")
            connection.execute(
                """UPDATE integration_settings_profiles
                SET public_payload_json = ? WHERE id = ?""",
                (json.dumps(fields), row["id"]),
            )

        self.assertTrue(self.repository.migrate_medplum_profile())
        self.assertFalse(self.repository.migrate_medplum_profile())
        private = self.repository.get_private("medplum")
        self.assertEqual(MEDPLUM_DEFAULT_WEB_UI_URL, private["fields"]["webUiUrl"])
        self.assertEqual(
            MEDPLUM_DEFAULT_TIMEOUT_SECONDS, private["fields"]["timeoutSeconds"]
        )
        self.assertEqual("migration-secret", private["secrets"]["clientSecret"])

    def test_replace_preserve_and_remove_are_atomic(self):
        self.seed()
        fields = dict(self.repository.get_private("medplum")["fields"])
        fields["clientId"] = "operator-client"
        profile = validate_profile("medplum", fields)
        self.repository.replace(
            profile, secret_mutations={"clientSecret": preserve_secret()}
        )
        preserved = self.service.get_public("medplum")
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
        self.repository.replace(
            profile, secret_mutations={"clientSecret": remove_secret()}
        )
        removed = self.service.get_public("medplum")
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

    def test_no_op_replace_audits_no_changed_fields(self):
        self.seed()
        private = self.repository.get_private("medplum")

        self.repository.replace(
            validate_profile("medplum", private["fields"]),
            secret_mutations={
                "clientSecret": replace_secret(private["secrets"]["clientSecret"])
            },
        )

        self.assertEqual(
            [],
            self.repository.list_audits("medplum")[-1]["changedFields"],
        )

    def test_replace_preserves_secret_whitespace_exactly(self):
        self.seed()
        private = self.repository.get_private("medplum")
        whitespace_sensitive = "  whitespace-sensitive-secret  "

        self.repository.replace(
            validate_profile("medplum", private["fields"]),
            secret_mutations={"clientSecret": replace_secret(whitespace_sensitive)},
        )

        self.assertEqual(
            whitespace_sensitive,
            self.repository.get_private("medplum")["secrets"]["clientSecret"],
        )
