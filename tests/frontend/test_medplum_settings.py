from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class MedplumSettingsTests(unittest.TestCase):
    def setUp(self):
        self.template = (ROOT / "frontend/templates/views/settings.html").read_text(encoding="utf-8")
        self.view = (ROOT / "frontend/static/js/settings/medplum.js").read_text(encoding="utf-8")
        self.api = (ROOT / "frontend/static/js/api/settings.js").read_text(encoding="utf-8")

    def test_form_exposes_complete_accessible_profile(self):
        for element_id in (
            "medplum-enabled", "medplum-fhir-url", "medplum-web-ui-url", "medplum-client-id",
            "medplum-client-secret", "medplum-scope", "medplum-token-url",
            "medplum-auth-grace", "medplum-timeout", "medplum-save-and-test",
        ):
            self.assertIn(f'id="{element_id}"', self.template)
        self.assertIn('placeholder="Leave blank to preserve"', self.template)
        self.assertIn('type="password"', self.template)

    def test_api_uses_profile_save_test_and_secret_removal_routes(self):
        self.assertIn('"/api/settings/profiles/medplum"', self.api)
        self.assertIn("save-and-test", self.api)
        self.assertIn('method: "DELETE"', self.api)
        self.assertIn("requestJsonAllowBusinessFailure", self.api)

    def test_secret_is_write_only_and_blank_preserves_existing_value(self):
        self.assertIn(
            "secrets: replacement ? { clientSecret: replacement } : {}",
            self.view,
        )
        self.assertIn('element("medplum-client-secret").value = ""', self.view)
        self.assertNotIn("profile.clientSecret ||", self.view)
        self.assertIn("clientSecretConfigured", self.view)

    def test_save_and_test_reports_save_separately_from_three_stages(self):
        self.assertIn("Medplum profile saved.", self.view)
        self.assertIn("normalizedStages", self.view)
        for label in ("FHIR metadata", "OAuth token", "Authenticated FHIR read"):
            self.assertIn(label, self.view)
        self.assertIn('id="medplum-save-result"', self.template)
        self.assertIn('id="medplum-test-results"', self.template)


if __name__ == "__main__":
    unittest.main()
