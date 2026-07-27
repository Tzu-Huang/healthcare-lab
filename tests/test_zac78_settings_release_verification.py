from __future__ import annotations

import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from backend.application_composition import assemble_application_dependencies
from backend.domain.integration_settings import TypedSettingsValidationError
from backend.repositories.database import SQLiteDatabase
from backend.repositories.schema import APPLICATION_MIGRATIONS
from backend.services.dcm4chee_diagnostics import diagnose_dcm4chee
from backend.services.gdt_bridge_diagnostics import (
    diagnose_gdt_bridge_dirs,
    probe_gdt_bridge_write_delete,
    provision_gdt_bridge_dirs,
)
from backend.settings_readiness_composition import create_settings_readiness_service
from tests.zac78_verification import (
    LEGACY_SCHEMA_PROVENANCE,
    LEGACY_SCHEMA_VERSION,
    SYNTHETIC_CANARIES,
    assert_bounded_evidence,
    create_canonical_legacy_database,
    project_bounded_failure,
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

    def test_builtin_defaults_and_optional_disable_flows_are_release_safe(self):
        dependencies = assemble_application_dependencies(
            self.root / "defaults.db", configuration={}
        )
        settings = dependencies.integration_settings_service
        dcm4chee = settings.get_public("dcm4chee")
        gdt = settings.get_public("gdt-bridge")

        self.assertTrue(dcm4chee["fields"]["enabled"])
        self.assertEqual("http://127.0.0.1:8082/dcm4chee-arc/ui2", dcm4chee["fields"]["webUiUrl"])
        self.assertFalse(dcm4chee["fields"]["security"]["tlsEnabled"])
        self.assertFalse(dcm4chee["fields"]["security"]["tlsVerify"])
        self.assertFalse(gdt["fields"]["enabled"])
        ap_profiles = dependencies.ap_device_profile_service.list()
        self.assertEqual(1, len(ap_profiles))
        self.assertFalse(ap_profiles[0]["enabled"])
        self.assertFalse(ap_profiles[0]["isDefault"])
        self.assertIsNone(dependencies.ap_device_profile_service.effective())

        gdt_fields = dict(gdt["fields"])
        gdt_fields["enabled"] = False
        settings.replace("gdt-bridge", gdt_fields)
        self.assertFalse(settings.get_effective("gdt-bridge").enabled)

        readiness = create_settings_readiness_service(
            settings,
            listener_status=lambda: {"running": True},
            oie_diagnostics=lambda: {"state": "healthy"},
            dcm4chee_diagnostics=lambda: {"state": "healthy", "checks": []},
        ).get_readiness()
        integrations = {item["id"]: item for item in readiness["sections"]}
        self.assertEqual("restart-required", integrations["oie"]["state"])
        self.assertEqual("ready", integrations["dcm4chee"]["state"])
        self.assertEqual("disabled", integrations["gdt-bridge"]["state"])
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

    def test_upgraded_database_keeps_representative_application_workflows_available(self):
        path = self.root / "workflow-upgrade.db"
        create_canonical_legacy_database(path)
        dependencies = assemble_application_dependencies(
            path,
            configuration={
                "MEDPLUM_CLIENT_ID": "legacy-client",
                "MEDPLUM_CLIENT_SECRET": SYNTHETIC_CANARIES["secret"],
            },
        )

        # Resolve each workflow-facing dependency after the complete migration
        # chain. This catches a schema upgrade that succeeds while leaving the
        # assembled patient/order, GDT, DICOM, or FHIR paths unusable.
        for dependency_name in (
            "patient_repository",
            "order_repository",
            "gdt_workflow",
            "dcm4chee_workflow_coordinator",
            "patient_fhir",
            "order_fhir",
        ):
            with self.subTest(dependency=dependency_name):
                self.assertIsNotNone(getattr(dependencies, dependency_name))

        with SQLiteDatabase(path, migrations=APPLICATION_MIGRATIONS).connect() as connection:
            applied = [
                row[0]
                for row in connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                )
            ]
        self.assertEqual(list(range(1, len(APPLICATION_MIGRATIONS) + 1)), applied)

    def test_gdt_missing_and_unwritable_paths_are_bounded_and_non_mutating(self):
        missing = self.root / SYNTHETIC_CANARIES["phi"] / "missing-bridge"
        missing_report = diagnose_gdt_bridge_dirs(missing)
        self.assertEqual("degraded", missing_report["state"])
        self.assertFalse(missing.exists())
        assert_bounded_evidence(missing_report)

        bridge = self.root / "bridge"
        provision_gdt_bridge_dirs(bridge)
        with patch(
            "backend.services.gdt_bridge_diagnostics.os.open",
            side_effect=OSError(SYNTHETIC_CANARIES["upstream_body"]),
        ):
            unwritable_report = probe_gdt_bridge_write_delete(bridge)
        self.assertEqual(
            {"role": "write-delete", "state": "failed", "code": "write-failed"},
            unwritable_report,
        )
        self.assertEqual([], list((bridge / "diagnostic").iterdir()))
        assert_bounded_evidence(unwritable_report)

    def test_dcm4chee_ap_oie_and_partial_availability_fail_independently(self):
        dcm4chee = diagnose_dcm4chee(
            {
                "webUiUrl": "http://unreachable.invalid/archive",
                "dicomweb": {"qidoRsUrl": "http://unreachable.invalid/rs"},
                "hl7": {"host": "unreachable.invalid", "port": 2575},
                "dimse": {"host": "unreachable.invalid", "port": 11112},
            },
            http_probe=lambda *_args: (_ for _ in ()).throw(
                OSError(SYNTHETIC_CANARIES["upstream_body"])
            ),
            tcp_probe=lambda *_args: (_ for _ in ()).throw(
                OSError(SYNTHETIC_CANARIES["raw_message"])
            ),
        )
        self.assertEqual("degraded", dcm4chee["state"])
        self.assertEqual(
            ["unreachable", "unreachable", "unreachable", "unreachable"],
            [item["code"] for item in dcm4chee["checks"]],
        )
        assert_bounded_evidence(dcm4chee)

        dependencies = assemble_application_dependencies(
            self.root / "partial.db", configuration={}
        )
        invalid_ap = {
            "id": "invalid-ap",
            "name": "Invalid AP",
            "environment": "lab",
            "enabled": True,
            "isDefault": False,
            "metadata": {},
            "hl7": {"enabled": False},
            "gdt": {"enabled": False},
            "dicom": {
                "enabled": True,
                "aeTitle": "BAD\\AE",
                "host": "ap.invalid",
                "port": 11112,
                "mwlCallingAETitle": "ECG_AP",
                "scheduledStationAETitle": "ECG_AP",
                "resultDeliveryRole": "scu",
            },
        }
        with self.assertRaises(TypedSettingsValidationError) as caught:
            dependencies.ap_device_profile_service.create(invalid_ap)
        self.assertEqual(
            "invalid_ae_title",
            caught.exception.as_dict()["fields"][0]["code"],
        )

        readiness_service = create_settings_readiness_service(
            dependencies.integration_settings_service,
            listener_status=lambda: {"running": False},
            oie_diagnostics=lambda: {
                "state": "degraded",
                "probes": [
                    {"layer": "management-api", "state": "unavailable"},
                    {"layer": "hlab-listener", "state": "healthy"},
                ],
            },
            dcm4chee_diagnostics=lambda: dcm4chee,
        )
        checks = {
            item["id"]: item for item in readiness_service.run_checks()["results"]
        }
        self.assertEqual("degraded", checks["oie"]["state"])
        self.assertEqual("degraded", checks["dcm4chee"]["state"])
        assert_bounded_evidence(checks)

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

    def test_api_ui_wrapper_log_and_screenshot_evidence_share_the_canary_gate(self):
        surfaces = ("api", "ui", "wrapper", "selectedLog", "screenshotOcr")
        for surface in surfaces:
            with self.subTest(surface=surface):
                for category, canary in SYNTHETIC_CANARIES.items():
                    with self.assertRaisesRegex(AssertionError, category):
                        assert_bounded_evidence({surface: canary})

        retained = {
            "api": {"state": "degraded", "category": "connection-failure"},
            "ui": {"label": "Connection failed", "recovery": "Review Settings"},
            "wrapper": {"state": "healthy"},
            "selectedLog": {"code": "dependency-unavailable"},
            "screenshotOcr": "Synthetic configuration; no credentials displayed.",
        }
        self.assertTrue(assert_bounded_evidence(retained))

    def test_required_failure_matrix_projects_bounded_recovery_actions(self):
        failures = (
            ("medplum", "metadata", "connection-failure"),
            ("medplum", "oauth", "authorization-failure"),
            ("medplum", "authenticated-read", "oauth-unavailable"),
            ("gdt-bridge", "inbox", "missing"),
            ("gdt-bridge", "write-delete", "write-failed"),
            ("dcm4chee", "web-ui-http", "unreachable"),
            ("dcm4chee", "qido-rs", "invalid-response"),
            ("dcm4chee", "hl7-tcp", "timed-out"),
            ("ap-device", "dicom.aeTitle", "invalid_ae_title"),
            ("ap-device", "hl7-transport", "unreachable"),
            ("oie", "management-api", "connection"),
            ("oie", "port-contract", "port-conflict"),
            ("oie", "managed-channel", "not-deployed"),
            ("oie", "delivery-state", "destination-errors"),
        )
        projected = [
            project_bounded_failure(integration, layer, category)
            for integration, layer, category in failures
        ]

        self.assertEqual(len(failures), len(projected))
        self.assertTrue(all(item["layer"] for item in projected))
        self.assertTrue(all(item["category"] for item in projected))
        self.assertTrue(all(item["recovery"] for item in projected))
        assert_bounded_evidence(projected)

        with self.assertRaisesRegex(ValueError, "Unsupported ZAC-78"):
            project_bounded_failure("dcm4chee", "qido-rs", "arbitrary-upstream")

    def test_operator_handbooks_track_verified_v111_release_image_gate(self):
        handbooks = (
            Path("docs/handbook/USER_HANDBOOK.en.md"),
            Path("docs/handbook/USER_HANDBOOK.zh-TW.md"),
        )
        for path in handbooks:
            source = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn(
                    "ghcr.io/tzu-huang/healthcare-lab:1.1.1",
                    source,
                )
                self.assertIn(
                    "54e60d0e69d25c256474d9d0a5c790b1d9b7599e",
                    source,
                )
                self.assertIn("30242203066", source)
                self.assertNotIn(
                    "ghcr.io/tzu-huang/healthcare-lab:1.0.0",
                    source,
                )
                self.assertNotIn(
                    "v1.0.0 operational release gate",
                    source,
                )
                self.assertNotIn(
                    "`false`, `true` | Enables TLS behavior",
                    source,
                )
                self.assertNotIn(
                    "`false`、`true` | TLS behavior",
                    source,
                )
                self.assertIn("`false`", source)

        word_editions = (
            Path("docs/handbook/USER_HANDBOOK.en.docx"),
            Path("docs/handbook/USER_HANDBOOK.zh-TW.docx"),
        )
        for path in word_editions:
            with zipfile.ZipFile(path) as archive:
                document_xml = archive.read("word/document.xml").decode("utf-8")
            with self.subTest(path=path):
                self.assertIn(
                    "ghcr.io/tzu-huang/healthcare-lab:1.1.1",
                    document_xml,
                )
                self.assertIn("30242203066", document_xml)
                self.assertNotIn(
                    "ghcr.io/tzu-huang/healthcare-lab:1.0.0",
                    document_xml,
                )
                self.assertNotIn(
                    "v1.0.0 operational release gate",
                    document_xml,
                )
                tls_start = document_xml.index("DCM4CHEE_TLS_ENABLED")
                tls_contract = document_xml[tls_start : tls_start + 5000]
                self.assertNotIn(">true<", tls_contract)
                self.assertGreaterEqual(tls_contract.count(">false<"), 2)

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
