from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.application_composition import assemble_application_dependencies
from backend.app_factory import create_app
from backend.domain.integration_settings import TypedSettingsValidationError


class IntegrationSettingsServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "settings.db"

    def tearDown(self):
        self.temporary.cleanup()

    def test_clean_install_bootstraps_legacy_environment_and_inventory_once(self):
        dependencies = assemble_application_dependencies(
            self.path,
            configuration={
                "MEDPLUM_CLIENT_ID": "legacy-client",
                "MEDPLUM_CLIENT_SECRET": "legacy-secret",
                "MEDPLUM_SCOPE": "openid",
                "MEDPLUM_TOKEN_URL": "http://legacy-medplum/oauth2/token",
                "MEDPLUM_AUTH_GRACE_SECONDS": 45,
                "MEDPLUM_WEB_UI_URL": "http://localhost:3000/",
                "MEDPLUM_TIMEOUT_SECONDS": 12,
            },
        )
        effective = dependencies.integration_settings_service.get_effective("medplum")
        self.assertEqual("http://127.0.0.1:8103/fhir/R4", effective.base_url)
        self.assertEqual("legacy-client", effective.client_id)
        self.assertEqual("legacy-secret", effective.client_secret)
        self.assertEqual("http://localhost:3000", effective.web_ui_url)
        self.assertEqual(12, effective.timeout_seconds)
        self.assertNotIn("legacy-secret", repr(effective))

    def test_restart_does_not_overwrite_persisted_operator_values(self):
        first = assemble_application_dependencies(
            self.path,
            configuration={
                "MEDPLUM_CLIENT_ID": "legacy-client",
                "MEDPLUM_CLIENT_SECRET": "legacy-secret",
            },
        )
        fields = dict(first.integration_settings_service.get_public("medplum")["fields"])
        fields["baseUrl"] = "https://operator.example/fhir/R4"
        fields["clientId"] = "operator-client"
        first.integration_settings_service.replace(
            "medplum",
            fields,
            secret_replacements={"clientSecret": "operator-secret"},
        )

        restarted = assemble_application_dependencies(
            self.path,
            configuration={
                "MEDPLUM_CLIENT_ID": "changed-environment",
                "MEDPLUM_CLIENT_SECRET": "changed-secret",
                "MEDPLUM_FHIR_BASE_URL": "https://changed.example/fhir/R4",
            },
        )
        effective = restarted.integration_settings_service.get_effective("medplum")
        self.assertEqual("https://operator.example/fhir/R4", effective.base_url)
        self.assertEqual("operator-client", effective.client_id)
        self.assertEqual("operator-secret", effective.client_secret)
        self.assertTrue(
            restarted.integration_settings_service.has_operator_configuration(
                "medplum"
            )
        )

    def test_bootstrap_profile_is_not_operator_confirmed(self):
        dependencies = assemble_application_dependencies(self.path)
        self.assertFalse(
            dependencies.integration_settings_service.has_operator_configuration(
                "medplum"
            )
        )

    def test_blank_secret_replacement_preserves_and_explicit_remove_clears(self):
        dependencies = assemble_application_dependencies(
            self.path,
            configuration={"MEDPLUM_CLIENT_SECRET": "saved-secret"},
        )
        service = dependencies.integration_settings_service
        fields = service.get_public("medplum")["fields"]
        service.replace(
            "medplum", fields, secret_replacements={"clientSecret": " "}
        )
        self.assertEqual(
            "saved-secret", service.get_effective("medplum").client_secret
        )
        removed = service.remove_secret("medplum", "clientSecret")
        self.assertFalse(removed["secrets"]["clientSecret"]["configured"])

    def test_invalid_bootstrap_does_not_create_partial_profile(self):
        with self.assertRaises(TypedSettingsValidationError):
            assemble_application_dependencies(
                self.path,
                configuration={"MEDPLUM_AUTH_GRACE_SECONDS": "invalid"},
            )
        dependencies = assemble_application_dependencies(self.path)
        audits = dependencies.integration_settings_repository.list_audits("medplum")
        self.assertEqual(1, len(audits))
        self.assertEqual("bootstrap", audits[0]["operation"])

    def test_application_composes_one_reader_for_http_and_background_workflows(self):
        captured = []
        app = create_app(
            str(self.path),
            dependency_receiver=captured.append,
            activate_runtime=False,
        )
        service = captured[0].integration_settings_service
        self.assertIs(service, app.extensions["integration_settings_service"])
        fields = dict(service.get_public("medplum")["fields"])
        fields["baseUrl"] = "https://persisted.example/fhir/R4"
        service.replace("medplum", fields)
        self.assertEqual(
            "https://persisted.example/fhir/R4",
            app.extensions["integration_settings_service"]
            .get_effective("medplum")
            .base_url,
        )

    def test_dcm4chee_bootstrap_is_persisted_once_and_effective_is_redacted(self):
        first = assemble_application_dependencies(
            self.path,
            configuration={
                "DCM4CHEE_DIMSE_HOST": "archive-one",
                "DCM4CHEE_HL7_HOST": "archive-one",
                "DCM4CHEE_PASSWORD": "password-canary",
                "DCM4CHEE_AUTH_MODE": "basic",
                "DCM4CHEE_USERNAME": "operator",
            },
        )
        effective = first.integration_settings_service.get_effective("dcm4chee")
        self.assertEqual("archive-one", effective.profile["dimse"]["host"])
        self.assertEqual("password-canary", effective.secrets["password"])
        self.assertNotIn("password-canary", repr(effective))

        fields = dict(first.integration_settings_service.get_public("dcm4chee")["fields"])
        fields["displayName"] = "Operator archive"
        first.integration_settings_service.replace("dcm4chee", fields)

        restarted = assemble_application_dependencies(
            self.path,
            configuration={"DCM4CHEE_DIMSE_HOST": "archive-two"},
        )
        persisted = restarted.integration_settings_service.get_effective("dcm4chee")
        self.assertEqual("archive-one", persisted.profile["dimse"]["host"])
        self.assertEqual("Operator archive", persisted.profile["displayName"])

    def test_dcm4chee_identity_change_is_blocked_when_records_depend_on_it(self):
        dependencies = assemble_application_dependencies(self.path)
        service = dependencies.integration_settings_service
        dependencies.integration_settings_repository.has_dcm4chee_dependencies = (
            lambda: True
        )
        fields = service.get_public("dcm4chee")["fields"]
        fields["profileName"] = "renamed-archive"

        with self.assertRaises(TypedSettingsValidationError) as raised:
            service.replace("dcm4chee", fields)

        self.assertEqual(
            "identity_migration_required", raised.exception.issues[0].code
        )
