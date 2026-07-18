from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class SettingsFoundationTests(unittest.TestCase):
    def test_zac50_destinations_exist_without_product_controls(self):
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
        self.assertNotIn("password", template.lower())
        self.assertNotIn("managed channel", template.lower())
        self.assertNotIn("delete", template.lower())

    def test_settings_view_has_an_idempotent_initialization_seam(self):
        source = (ROOT / "frontend/static/js/views/settings.js").read_text(encoding="utf-8")
        self.assertIn("export function initializeSettingsView(root)", source)
        self.assertIn("state.initialized", source)
        self.assertNotIn("fetch(", source)


if __name__ == "__main__":
    unittest.main()
