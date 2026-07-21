from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class SettingsFoundationTests(unittest.TestCase):
    def test_settings_destinations_own_listener_controls_without_managed_channels(self):
    def test_managed_channel_settings_surface_is_owned_and_safe(self):
        expected = (
            "frontend/static/js/api/settings.js",
            "frontend/static/js/state/settings.js",
            "frontend/static/js/components/settings-shell.js",
            "frontend/static/js/views/settings.js",
            "frontend/static/css/views/settings.css",
            "frontend/templates/views/settings.html",
        )
        for relative in expected:
            with self.subTest(path=relative):
                self.assertTrue((ROOT / relative).is_file())

        template = (ROOT / "frontend/templates/views/settings.html").read_text(encoding="utf-8")
        self.assertIn('id="settings-view"', template)
        self.assertIn('id="settings-listener-host"', template)
        self.assertIn('id="settings-listener-reload-reminder"', template)
        self.assertIn('id="retry-settings-listener"', template)
        self.assertNotIn("password", template.lower())
        self.assertIn("managed channels", template.lower())
        self.assertIn("external — read only", template.lower())
        self.assertIn("exact logical type", template.lower())
        for forbidden in ("force", "override", "adopt", "redeploy", "select all"):
            self.assertNotIn(forbidden, template.lower())

    def test_settings_view_has_an_idempotent_initialization_seam(self):
        source = (ROOT / "frontend/static/js/views/settings.js").read_text(encoding="utf-8")
        self.assertIn("export function initializeSettingsView(root)", source)
        self.assertIn("state.initialized", source)
        self.assertNotIn("fetch(", source)

    def test_listener_save_reminder_is_driven_by_api_and_runtime_status(self):
        source = (ROOT / "frontend/static/js/views/settings.js").read_text(encoding="utf-8")
        state = (ROOT / "frontend/static/js/state/settings.js").read_text(encoding="utf-8")
        api = (ROOT / "frontend/static/js/api/settings.js").read_text(encoding="utf-8")
        component = (ROOT / "frontend/static/js/components/settings-shell.js").read_text(encoding="utf-8")

        self.assertIn("runtimeReloadRequired", source)
        self.assertIn("!listenerSettingsMatchStatus(state.profile, status.item)", source)
        self.assertIn("listenerSettingsMatchStatus", state)
        self.assertIn("intendedDisabledStateMatches", state)
        self.assertIn("function saveSettings(", api)
        self.assertIn("function retrySettingsListener(", api)
        self.assertIn("Stop and Retry", component)
    def test_api_and_view_require_preview_before_single_target_mutation(self):
        api = (ROOT / "frontend/static/js/api/settings.js").read_text(encoding="utf-8")
        view = (ROOT / "frontend/static/js/views/settings.js").read_text(encoding="utf-8")
        self.assertIn("previewManagedChannel", api)
        self.assertIn("previewToken", api)
        self.assertIn("state.preview?.previewToken", view)
        self.assertIn("state.confirmation !== state.selected", view)
        for forbidden in ("redeploy-all", "override: true", "force: true", "adopt"):
            self.assertNotIn(forbidden, (api + view).lower())


if __name__ == "__main__":
    unittest.main()
