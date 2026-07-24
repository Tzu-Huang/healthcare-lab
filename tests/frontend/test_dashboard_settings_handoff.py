from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class DashboardSettingsHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.template = (
            ROOT / "frontend/templates/views/dashboard.html"
        ).read_text(encoding="utf-8")
        cls.dashboard = (
            ROOT / "frontend/static/js/views/dashboard.js"
        ).read_text(encoding="utf-8")
        cls.navigation = (
            ROOT / "frontend/static/js/core/navigation.js"
        ).read_text(encoding="utf-8")
        cls.application = (
            ROOT / "frontend/static/js/views/application.js"
        ).read_text(encoding="utf-8")
        cls.settings = (
            ROOT / "frontend/static/js/views/settings.js"
        ).read_text(encoding="utf-8")
        cls.style = (
            ROOT / "frontend/static/css/views/dashboard.css"
        ).read_text(encoding="utf-8")

    def test_notice_is_accessible_non_blocking_and_keyboard_native(self):
        self.assertIn('id="dashboard-setup-notice"', self.template)
        self.assertIn('aria-labelledby="dashboard-setup-title"', self.template)
        self.assertIn('aria-describedby="dashboard-setup-summary"', self.template)
        self.assertIn('id="dashboard-open-settings"', self.template)
        self.assertIn('type="button"', self.template)
        self.assertIn("dashboard-setup-notice[hidden]", self.style)
        self.assertNotIn('role="dialog"', self.template)

    def test_activation_reads_authoritative_complete_and_next_action(self):
        self.assertIn("fetchSettingsReadiness", self.dashboard)
        self.assertIn("readiness.complete === true", self.dashboard)
        self.assertIn("readiness.nextAction?.sectionId", self.dashboard)
        self.assertIn("void refreshDashboardSetup()", self.dashboard)
        self.assertIn('visible: false', self.dashboard)

    def test_registered_navigation_targets_settings_workspace_section(self):
        self.assertIn(
            'activateView("settings-view", { sectionId: setupDestination })',
            self.dashboard,
        )
        self.assertIn("registration?.activate?.(activation)", self.navigation)
        self.assertIn(
            '({ sectionId } = {}) => refreshSettings(sectionId)',
            self.application,
        )
        self.assertIn(
            "root.settingsWorkspace?.activate(sectionId, true)",
            self.settings,
        )

    def test_unavailable_is_bounded_and_browser_storage_has_no_cursor(self):
        self.assertIn("Setup status unavailable", self.dashboard)
        self.assertIn(
            "Settings remain available while setup status is temporarily unavailable.",
            self.dashboard,
        )
        combined = "\n".join(
            (self.template, self.dashboard, self.navigation, self.settings)
        ).lower()
        self.assertNotIn("localstorage", combined)
        self.assertNotIn("sessionstorage", combined)
        self.assertNotIn("wizardcursor", combined)

    def test_notice_sources_do_not_contain_sensitive_value_canaries(self):
        combined = "\n".join(
            (self.template, self.dashboard, self.navigation, self.settings)
        )
        for canary in (
            "secret-canary",
            "patient-canary",
            "client-secret-canary",
            "patient-name-canary",
        ):
            with self.subTest(canary=canary):
                self.assertNotIn(canary, combined)


if __name__ == "__main__":
    unittest.main()
