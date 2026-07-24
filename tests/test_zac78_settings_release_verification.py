from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.application_composition import assemble_application_dependencies
from backend.repositories.database import SQLiteDatabase
from backend.repositories.schema import APPLICATION_MIGRATIONS
from backend.settings_readiness_composition import create_settings_readiness_service
from tests.zac78_verification import (
    LEGACY_SCHEMA_PROVENANCE,
    LEGACY_SCHEMA_VERSION,
    SYNTHETIC_CANARIES,
    assert_bounded_evidence,
    create_canonical_legacy_database,
)


class Zac78SettingsReleaseVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_canonical_fixture_is_versioned_pre_unified_settings_schema(self):
        path = self.root / "canonical-pre-settings-v8.db"
        create_canonical_legacy_database(path)
        connection = sqlite3.connect(path)
        try:
            versions = [
                row[0]
                for row in connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                )
            ]
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        finally:
            connection.close()
        self.assertEqual(list(range(1, LEGACY_SCHEMA_VERSION + 1)), versions)
        # The migration-1 initializer is intentionally forward-compatible and
        # creates current tables. The v8 ledger is the authoritative historical
        # boundary used by the existing migration contract.
        self.assertIn("schema_migrations", tables)
        self.assertIn("add-typed-integration-settings", LEGACY_SCHEMA_PROVENANCE)

    def test_legacy_upgrade_is_atomic_bootstraps_once_and_preserves_ui_authority(self):
        path = self.root / "upgrade.db"
        create_canonical_legacy_database(path)
        legacy = {
            "MEDPLUM_CLIENT_ID": "legacy-client",
            "MEDPLUM_CLIENT_SECRET": SYNTHETIC_CANARIES["secret"],
            "GDT_BRIDGE_RECEIVER_ID": "LEGACY_RECEIVER",
        }
        upgraded = assemble_application_dependencies(path, configuration=legacy)
        service = upgraded.integration_settings_service
        public = service.get_public("medplum")
        self.assertTrue(public["secrets"]["clientSecret"]["configured"])
        fields = dict(public["fields"])
        fields["clientId"] = "operator-client"
        service.replace(
            "medplum",
            fields,
            secret_replacements={"clientSecret": "operator-replacement"},
        )

        restarted = assemble_application_dependencies(
            path,
            configuration={
                "MEDPLUM_CLIENT_ID": "conflicting-legacy-client",
                "MEDPLUM_CLIENT_SECRET": "conflicting-legacy-secret",
            },
        )
        effective = restarted.integration_settings_service.get_effective("medplum")
        self.assertEqual("operator-client", effective.client_id)
        self.assertEqual("operator-replacement", effective.client_secret)
        audits = restarted.integration_settings_repository.list_audits("medplum")
        self.assertEqual(1, sum(item["operation"] == "bootstrap" for item in audits))
        assert_bounded_evidence(
            {
                "public": restarted.integration_settings_service.get_public("medplum"),
                "audits": audits,
            }
        )
        with SQLiteDatabase(path, migrations=APPLICATION_MIGRATIONS).connect() as connection:
            self.assertEqual(
                len(APPLICATION_MIGRATIONS),
                connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0],
            )

    def test_clean_defaults_project_required_and_optional_setup_without_secrets(self):
        path = self.root / "fresh.db"
        dependencies = assemble_application_dependencies(path, configuration={})
        service = dependencies.integration_settings_service
        medplum = service.get_public("medplum")
        dcm4chee = service.get_public("dcm4chee")
        gdt = service.get_public("gdt-bridge")
        self.assertFalse(medplum["secrets"]["clientSecret"]["configured"])
        self.assertTrue(dcm4chee["fields"]["enabled"])
        self.assertFalse(gdt["fields"]["enabled"])

        readiness = create_settings_readiness_service(
            service,
            listener_status=lambda: {"running": False},
            oie_diagnostics=lambda: {"state": "healthy"},
            dcm4chee_diagnostics=lambda: {"state": "healthy", "checks": []},
        ).get_readiness()
        self.assertFalse(readiness["complete"])
        self.assertIsNotNone(readiness["nextAction"])
        assert_bounded_evidence(readiness)

    def test_completed_operator_configuration_survives_dependency_recreation(self):
        path = self.root / "retained-storage.db"
        first = assemble_application_dependencies(path, configuration={})
        service = first.integration_settings_service
        fields = dict(service.get_public("medplum")["fields"])
        fields.update(
            enabled=True,
            baseUrl="https://synthetic.invalid/fhir/R4",
            clientId="synthetic-client",
        )
        service.replace(
            "medplum",
            fields,
            secret_replacements={"clientSecret": "synthetic-secret"},
        )
        recreated = assemble_application_dependencies(path, configuration={})
        public = recreated.integration_settings_service.get_public("medplum")
        effective = recreated.integration_settings_service.get_effective("medplum")
        self.assertEqual("https://synthetic.invalid/fhir/R4", effective.base_url)
        self.assertTrue(public["secrets"]["clientSecret"]["configured"])
        self.assertNotIn("synthetic-secret", repr(public))

    def test_evidence_gate_rejects_every_sensitive_category_and_accepts_bounded_output(self):
        self.assertEqual(
            '{"code": "authentication_failed", "recovery": "replace credential"}',
            assert_bounded_evidence(
                {"code": "authentication_failed", "recovery": "replace credential"}
            ),
        )
        for category, canary in SYNTHETIC_CANARIES.items():
            with self.subTest(category=category):
                with self.assertRaisesRegex(AssertionError, category):
                    assert_bounded_evidence({"selectedLog": canary})

    def test_settings_web_authority_has_no_compose_writer_or_docker_executor(self):
        settings_sources = [
            Path("backend/api/integration_settings.py"),
            Path("backend/services/integration_settings.py"),
            Path("backend/api/settings_readiness.py"),
            Path("backend/services/settings_readiness.py"),
        ]
        forbidden = (
            "docker compose",
            "docker.exe",
            "subprocess.",
            "compose.yaml",
            "compose.yml",
        )
        for path in settings_sources:
            source = path.read_text(encoding="utf-8").lower()
            with self.subTest(path=path):
                for token in forbidden:
                    self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
