from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class DashboardViewModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "frontend/static/js/views/dashboard.js").read_text(encoding="utf-8")
        cls.api = (ROOT / "frontend/static/js/api/dashboard.js").read_text(encoding="utf-8")

    def test_dashboard_owns_state_rendering_and_actions(self):
        self.assertIn("const state = {", self.source)
        for name in ("services", "events", "resources", "expandedServiceIds"):
            self.assertIn(f"{name}:", self.source)
        self.assertIn("function renderServices()", self.source)
        self.assertIn("function renderResources()", self.source)
        self.assertIn("function renderEvents()", self.source)

    def test_dashboard_initialization_is_idempotent(self):
        self.assertIn("export function initializeDashboardView()", self.source)
        self.assertIn("if (initialized) return", self.source)
        for element_id in ("refresh-dashboard", "run-all-lab-checks", "dashboard-filter"):
            self.assertIn(f'byId("{element_id}").addEventListener', self.source)

    def test_dashboard_uses_feature_api_adapter(self):
        for name in (
            "fetchDashboardServices", "runDashboardServiceAction",
            "runDashboardChildAction", "checkAllDashboardServices",
        ):
            self.assertIn(f"function {name}(", self.api)
            self.assertIn(name, self.source)
        self.assertNotIn("requestJson(", self.source)


if __name__ == "__main__":
    unittest.main()
