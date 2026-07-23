from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class GdtBridgeSettingsTests(unittest.TestCase):
    def setUp(self):
        self.template = (ROOT / "frontend/templates/settings/gdt-bridge.html").read_text(encoding="utf-8")
        self.module = (ROOT / "frontend/static/js/settings/gdt-bridge.js").read_text(encoding="utf-8")
        self.style = (ROOT / "frontend/static/css/settings/gdt-bridge.css").read_text(encoding="utf-8")

    def test_accessible_profile_and_advanced_controls(self):
        for element_id in (
            "gdt-bridge-enabled", "gdt-bridge-receiver-id", "gdt-bridge-sender-id",
            "gdt-bridge-filename-profile", "gdt-bridge-success-mode",
            "gdt-bridge-poll-interval", "gdt-bridge-stable-interval",
            "gdt-bridge-save", "gdt-bridge-provision", "gdt-bridge-run-diagnostics",
        ):
            self.assertIn(f'id="{element_id}"', self.template)
        self.assertIn("<summary>Advanced</summary>", self.template)
        self.assertIn('role="status"', self.template)
        self.assertIn('aria-live="polite"', self.template)

    def test_docker_and_host_paths_are_distinct(self):
        self.assertIn("/data/gdt-bridge", self.template)
        self.assertIn("Host bind-mount source", self.template)
        self.assertIn("read-only", self.template)
        self.assertIn("container recreation", self.template)
        self.assertIn('applicationPath: "/data/gdt-bridge"', self.module)
        self.assertIn('hostBindMountSource || "Unavailable"', self.module)

    def test_owned_api_adapter_has_explicit_mutations(self):
        self.assertIn('"/api/settings/profiles/gdt-bridge"', self.module)
        self.assertIn('"/api/settings/gdt-bridge"', self.module)
        self.assertIn('method: "PUT"', self.module)
        self.assertGreaterEqual(self.module.count('method: "POST"'), 2)
        self.assertIn("/provision", self.module)
        self.assertIn("/diagnostics", self.module)

    def test_validation_maps_to_accessible_controls(self):
        self.assertIn('receiverId: "gdt-bridge-receiver-id"', self.module)
        self.assertIn('pollIntervalSeconds: "gdt-bridge-poll-interval"', self.module)
        self.assertIn('setAttribute("aria-invalid", "true")', self.module)
        self.assertIn('setAttribute("aria-errormessage", message.id)', self.module)

    def test_disabled_readiness_and_activation_are_explicit(self):
        self.assertIn("Disabled (optional); setup remains complete.", self.module)
        self.assertIn('"restart-required"', self.module)
        self.assertIn("Restart is required", self.module)
        self.assertIn("watcher-state", self.template)

    def test_diagnostics_render_only_bounded_server_fields(self):
        self.assertIn("boundedChecks", self.module)
        self.assertIn("check.label || check.role || check.id", self.module)
        render_body = self.module.split("function renderDiagnostics", 1)[1].split(
            "\nfunction setBusy", 1
        )[0]
        self.assertNotIn("check.filename", render_body)
        self.assertNotIn("check.content", render_body)
        self.assertNotIn("response.files", render_body)

    def test_feature_styles_are_responsive_and_owned(self):
        self.assertIn(".gdt-settings", self.style)
        self.assertIn("@media", self.style)


if __name__ == "__main__":
    unittest.main()
