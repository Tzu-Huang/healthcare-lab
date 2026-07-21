"""Composition seams that ZAC-62 must preserve while decomposing services."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_FACTORY = ROOT / "backend" / "app_factory.py"


class Zac62CompositionBaselineTests(unittest.TestCase):
    def test_zac46_oie_management_wiring_is_retained(self):
        source = APP_FACTORY.read_text(encoding="utf-8")

        self.assertIn("client_provider=lambda: create_oie_management_client(", source)
        self.assertIn("dependencies.oie_settings_repository", source)

    def test_workflow_extensions_are_registered_before_blueprint_composition(self):
        source = APP_FACTORY.read_text(encoding="utf-8")
        tree = ast.parse(source)
        create_app = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "create_app"
        )
        function_source = ast.get_source_segment(source, create_app) or ""

        required_seams = (
            'app.extensions["oie_result_listener"]',
            'app.extensions["gdt_bridge_watcher"]',
            'app.extensions["oie_settings_service"]',
            'app.extensions["oie_channel_lifecycle_service"]',
            'app.extensions["oie_workflow_service"]',
        )
        positions = [function_source.index(seam) for seam in required_seams]
        self.assertEqual(sorted(positions), positions)
        self.assertLess(positions[-1], function_source.index("create_oie_blueprint("))
        self.assertLess(
            function_source.index('app.extensions["gdt_bridge_watcher"]'),
            function_source.index("create_gdt_blueprint("),
        )


if __name__ == "__main__":
    unittest.main()
