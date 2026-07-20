from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class NavigationModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "frontend/static/js/core/navigation.js").read_text(encoding="utf-8")

    def test_initialization_is_idempotent(self):
        self.assertIn("let initialized = false", self.source)
        self.assertIn("if (initialized) return", self.source)
        self.assertIn("initialized = true", self.source)

    def test_navigation_has_no_feature_view_imports(self):
        self.assertIn("export function registerViewActivation", self.source)
        self.assertNotIn("/views/", self.source)

    def test_activation_failure_has_a_diagnostic_boundary(self):
        self.assertIn("healthcare-lab:view-error", self.source)
        self.assertIn("initializationError", self.source)

    def test_feature_initialization_failure_has_an_isolated_diagnostic_boundary(self):
        self.assertIn("export function initializeView(viewId, initialize)", self.source)
        self.assertIn('phase: "initialization"', self.source)
        self.assertIn("return false", self.source)


if __name__ == "__main__":
    unittest.main()
