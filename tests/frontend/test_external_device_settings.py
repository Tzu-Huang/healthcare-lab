from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ExternalDeviceSettingsTests(unittest.TestCase):
    def setUp(self):
        self.template = (
            ROOT / "frontend/templates/settings/external-devices.html"
        ).read_text(encoding="utf-8")
        self.controller = (
            ROOT / "frontend/static/js/settings/external-devices.js"
        ).read_text(encoding="utf-8")
        self.css = (
            ROOT / "frontend/static/css/settings/external-devices.css"
        ).read_text(encoding="utf-8")

    def test_module_owns_template_api_state_and_style(self):
        self.assertIn('data-integration-owner="external-devices"', self.template)
        self.assertIn('"/api/settings/external-devices"', self.controller)
        self.assertIn("const state =", self.controller)
        self.assertIn(".external-device-settings", self.css)
        self.assertIn("initializeExternalDeviceSettingsSection", self.controller)
        self.assertIn("refreshExternalDeviceSettings", self.controller)

    def test_accessible_multi_profile_and_environment_controls(self):
        for element_id in (
            "external-device-profile-list",
            "external-device-environment-filter",
            "external-device-enabled",
            "external-device-default",
            "external-device-set-default",
        ):
            self.assertIn(f'id="{element_id}"', self.template)
        self.assertIn('aria-label="AP device profiles"', self.template)
        self.assertIn('aria-current', self.controller)
        self.assertIn("createExternalDeviceProfile", self.controller)
        self.assertIn("updateExternalDeviceProfile", self.controller)
        self.assertIn("selectExternalDeviceDefault", self.controller)

    def test_protocol_fields_are_conditional_and_direction_is_explicit(self):
        for protocol in ("hl7", "gdt", "dicom"):
            self.assertIn(f'data-protocol="{protocol}"', self.template)
            self.assertIn(
                f'aria-controls="external-device-{protocol}-fields"', self.template
            )
        for phrase in (
            "Healthcare Lab / OIE → AP endpoint",
            "Healthcare Lab ↔ GDT Bridge ↔ AP",
            "AP ↔ dcm4chee archive",
            "AP MLLP host",
            "AP DICOM host",
            "archive endpoint and called AE remain dcm4chee-owned",
        ):
            self.assertIn(phrase, self.template)
        self.assertIn("setProtocolVisibility", self.controller)

    def test_validation_diagnostics_and_readiness_are_value_safe(self):
        for element_id in (
            "external-device-readiness",
            "external-device-diagnostics",
            "external-device-last-interaction",
            "external-device-activation-guidance",
        ):
            self.assertIn(f'id="{element_id}"', self.template)
        self.assertIn('role="status"', self.template)
        self.assertIn('aria-live="polite"', self.template)
        self.assertIn("aria-invalid", self.controller)
        self.assertIn("aria-errormessage", self.controller)
        self.assertIn("transport-reachable", self.template)
        self.assertIn('"apply-required"', self.controller)
        self.assertIn("Preview → Apply", self.template)
        for safe_key in ("protocol", "direction", "timestamp", "outcomeCode"):
            self.assertIn(f'data-observation="{safe_key}"', self.template)
        forbidden = ("patientName", "patientId", "orderId", "rawPayload", "messagePayload")
        for field in forbidden:
            self.assertNotIn(field, self.template + self.controller)

    def test_responsive_owned_styles_exist(self):
        self.assertIn("@media", self.css)
        self.assertIn(".external-device-layout", self.css)
        self.assertIn(".external-device-protocol", self.css)


if __name__ == "__main__":
    unittest.main()
