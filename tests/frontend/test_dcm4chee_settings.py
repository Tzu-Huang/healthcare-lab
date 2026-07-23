from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Dcm4cheeSettingsTests(unittest.TestCase):
    def setUp(self):
        self.template = (ROOT / "frontend/templates/settings/dcm4chee.html").read_text(encoding="utf-8")
        self.module = (ROOT / "frontend/static/js/settings/dcm4chee.js").read_text(encoding="utf-8")
        self.style = (ROOT / "frontend/static/css/settings/dcm4chee.css").read_text(encoding="utf-8")

    def test_common_profile_is_accessible_and_optional(self):
        for element_id in (
            "dcm4chee-enabled", "dcm4chee-display-name", "dcm4chee-environment-name",
            "dcm4chee-web-ui-url", "dcm4chee-profile-name", "dcm4chee-dimse-host",
            "dcm4chee-dimse-port", "dcm4chee-called-ae-title", "dcm4chee-calling-ae-title",
            "dcm4chee-mwl-ae-title", "dcm4chee-scheduled-station-ae-title",
            "dcm4chee-save", "dcm4chee-run-diagnostics",
        ):
            self.assertIn(f'id="{element_id}"', self.template)
        self.assertIn("may remain disabled", self.template)
        self.assertIn('role="status"', self.template)
        self.assertIn('aria-live="polite"', self.template)

    def test_advanced_disclosure_contains_protocol_identity_and_security(self):
        self.assertIn("<summary>Advanced</summary>", self.template)
        for element_id in (
            "dcm4chee-dicomweb-base-url", "dcm4chee-qido-rs-url", "dcm4chee-wado-rs-url",
            "dcm4chee-stow-rs-url", "dcm4chee-viewer-template", "dcm4chee-uid-root",
            "dcm4chee-hl7-host", "dcm4chee-hl7-port", "dcm4chee-patient-assigning-authority",
            "dcm4chee-auth-mode", "dcm4chee-tls-enabled", "dcm4chee-tls-verify",
            "dcm4chee-certificate-path", "dcm4chee-private-key-path",
        ):
            self.assertIn(f'id="{element_id}"', self.template)
        self.assertIn("browser-facing", self.template.lower())
        self.assertIn("application-facing", self.template.lower())

    def test_owned_adapter_uses_profile_and_diagnostics_endpoints(self):
        self.assertIn('"/api/settings/profiles/dcm4chee"', self.module)
        self.assertIn('"/api/settings/dcm4chee/diagnostics"', self.module)
        self.assertIn('method: "PUT"', self.module)
        self.assertIn('method: "POST"', self.module)
        self.assertIn("requestJsonAllowBusinessFailure", self.module)

    def test_secrets_are_write_only_and_blank_preserves_them(self):
        self.assertGreaterEqual(self.template.count('type="password"'), 3)
        self.assertGreaterEqual(self.template.count('placeholder="Leave blank to preserve"'), 3)
        self.assertIn('find(root, "dcm4chee-password").value = ""', self.module)
        self.assertIn('find(root, "dcm4chee-token").value = ""', self.module)
        self.assertIn('find(root, "dcm4chee-client-secret").value = ""', self.module)
        self.assertIn("if (password) secrets.password = password", self.module)
        self.assertIn("if (token) secrets.token = token", self.module)
        self.assertIn("if (clientSecret) secrets.clientSecret = clientSecret", self.module)
        self.assertIn('find(root, "dcm4chee-certificate-path").value = ""', self.module)
        self.assertIn('find(root, "dcm4chee-private-key-path").value = ""', self.module)
        self.assertNotIn("security.password ||", self.module)
        self.assertNotIn("security.token ||", self.module)

    def test_references_and_diagnostics_use_bounded_projections(self):
        self.assertIn("Configured and readable", self.module)
        self.assertIn("Configured reference is not readable", self.module)
        self.assertIn("boundedChecks", self.module)
        render_body = self.module.split("function renderDiagnostics", 1)[1].split(
            "\nfunction setBusy", 1
        )[0]
        for forbidden in ("check.content", "check.payload", "check.exception", "check.url"):
            self.assertNotIn(forbidden, render_body)

    def test_validation_maps_nested_fields_to_accessible_controls(self):
        self.assertIn('"dimse.port": "dcm4chee-dimse-port"', self.module)
        self.assertIn('"hl7.patientAssigningAuthority": "dcm4chee-patient-assigning-authority"', self.module)
        self.assertIn('"security.privateKeyPath": "dcm4chee-private-key-path"', self.module)
        self.assertIn('setAttribute("aria-invalid", "true")', self.module)
        self.assertIn('setAttribute("aria-errormessage", message.id)', self.module)

    def test_save_activation_and_diagnostics_are_distinct(self):
        for element_id in (
            "dcm4chee-save-result", "dcm4chee-activation-result",
            "dcm4chee-diagnostics-summary", "dcm4chee-diagnostics",
        ):
            self.assertIn(f'id="{element_id}"', self.template)
        self.assertIn('"Profile saved."', self.module)
        self.assertIn("Saved settings apply to subsequent operations.", self.module)
        self.assertIn("Running bounded diagnostics", self.module)

    def test_feature_styles_are_owned_and_responsive(self):
        self.assertIn(".dcm4chee-settings", self.style)
        self.assertIn(".dcm4chee-reference-state", self.style)
        self.assertIn("@media", self.style)


if __name__ == "__main__":
    unittest.main()
