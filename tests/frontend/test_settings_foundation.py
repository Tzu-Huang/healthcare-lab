from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SettingsFoundationTests(unittest.TestCase):
    def setUp(self):
        self.template = (ROOT / "frontend/templates/views/settings.html").read_text(encoding="utf-8")
        self.view = (ROOT / "frontend/static/js/views/settings.js").read_text(encoding="utf-8")
        self.api = (ROOT / "frontend/static/js/api/settings.js").read_text(encoding="utf-8")
        self.sidebar = (ROOT / "frontend/templates/shell/sidebar.html").read_text(encoding="utf-8")
        self.layout = (ROOT / "frontend/static/css/layout.css").read_text(encoding="utf-8")

    def test_complete_workspace_has_one_modular_owner(self):
        for relative in (
            "frontend/static/js/api/settings.js", "frontend/static/js/state/settings.js",
            "frontend/static/js/components/settings-shell.js", "frontend/static/js/views/settings.js",
            "frontend/static/css/views/settings.css", "frontend/templates/views/settings.html",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)
        self.assertIn('id="settings-view"', self.template)
        for heading in ("OIE Connection", "HLAB Result Listener", "Managed Channels", "External — read only"):
            self.assertIn(heading, self.template)
        application = (ROOT / "frontend/static/js/views/application.js").read_text(encoding="utf-8")
        self.assertEqual(1, application.count('from "./settings.js"'))
        self.assertEqual(1, application.count('registerViewActivation("settings-view"'))
        self.assertEqual(1, application.count('initializeView("settings-view"'))

    def test_connection_is_write_only_and_tested_from_saved_settings(self):
        self.assertIn('type="password"', self.template)
        self.assertIn('placeholder="Leave blank to preserve"', self.template)
        self.assertIn("if (replacement) payload.password = replacement", self.view)
        self.assertIn("test-connection", self.api)
        self.assertNotIn("password = management.password", self.view)

    def test_listener_intent_runtime_and_warning_are_separate(self):
        for element_id in ("settings-listener-state", "settings-listener-endpoint", "start-settings-listener", "stop-settings-listener", "retry-settings-listener", "settings-listener-port-warning"):
            self.assertIn(f'id="{element_id}"', self.template)
        self.assertIn("!listenerSettingsMatchStatus(state.profile, runtime.item)", self.view)
        self.assertIn("Save is persistence-only", self.template)
        warning = (ROOT / "frontend/static/js/components/settings-shell.js").read_text(encoding="utf-8")
        for phrase in ("managed ORU route", "Docker/runtime", "firewall", "Retry or restart"):
            self.assertIn(phrase, warning)

    def test_layered_diagnostics_are_safe_and_distinguish_recovery_actions(self):
        for element_id in ("settings-diagnostics-summary", "settings-diagnostics-list", "settings-refresh-diagnostics"):
            self.assertIn(f'id="{element_id}"', self.template)
        self.assertIn("fetchRuntimeDiagnostics", self.api)
        self.assertIn("refreshRuntimeDiagnostics", self.view)
        for phrase in ("Apply/Redeploy", "Retry or lab-app restart", "container recreation"):
            self.assertIn(phrase, self.template)
        self.assertIn('check.state || "unknown"', self.view)

    def test_preview_is_required_and_delete_matches_display_name(self):
        self.assertIn("state.preview?.previewToken", self.view)
        self.assertIn("state.confirmation !== expectedName", self.view)
        self.assertIn("displayedChannelName(selectedItem(), state.preview)", self.view)
        self.assertIn("recreate", self.api)
        combined = (self.api + self.view + self.template).lower()
        for forbidden in ("redeploy-all", "override: true", "force: true", "adopt"):
            self.assertNotIn(forbidden, combined)

    def test_external_cards_have_no_mutation_controls(self):
        external_guard = 'if (item.classification === "external") return card;'
        self.assertIn(external_guard, self.view)
        self.assertLess(self.view.index(external_guard), self.view.index("normalizedActions(item).forEach"))

    def test_editor_exposes_only_bounded_owned_fields(self):
        for field in ("sourceHost", "sourcePort", "destinationHost", "destinationPort", "timeoutSeconds", "queueEnabled", "retryCount", "retryIntervalMs"):
            self.assertIn(field, self.view)
        for forbidden in ("raw xml", "raw json", "transformer", "filter", "script editor"):
            self.assertNotIn(forbidden, (self.view + self.template).lower())
        self.assertIn("Preview Apply before changing OIE", self.view)

    def test_view_initialization_is_idempotent_and_uses_api_module(self):
        self.assertIn("export function initializeSettingsView(root)", self.view)
        self.assertIn("state.initialized", self.view)
        self.assertNotIn("fetch(", self.view)

    def test_settings_navigation_is_semantically_and_visually_separated(self):
        self.assertIn('class="sidebar-settings-group" role="group" aria-label="Application settings"', self.sidebar)
        group_start = self.sidebar.index('class="sidebar-settings-group"')
        self.assertGreater(self.sidebar.index('data-nav-target="settings-view"'), group_start)
        rule = self.layout[self.layout.index(".sidebar-settings-group"):]
        self.assertIn("border-top:", rule)
        self.assertIn("padding-top:", rule)


if __name__ == "__main__":
    unittest.main()
