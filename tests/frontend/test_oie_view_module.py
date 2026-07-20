from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class OieViewModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "frontend/static/js/views/oie.js").read_text(encoding="utf-8")
        cls.entrypoint = (ROOT / "frontend/static/app.js").read_text(encoding="utf-8")
        cls.template = (ROOT / "frontend/templates/index.html").read_text(encoding="utf-8")

    def test_oie_template_structure_has_a_focused_owner(self):
        for marker in (
            'class="table-wrap oie-patient-table-wrap"',
            'class="lab-panel oie-transmission-panel"',
            'class="compact-output oie-preview-output"',
            'id="oie-selected-order-title"',
            'id="send-selected-oie-order"',
            'Host / IP<input id="oie-send-host"',
            'id="oie-send-host" value="{{ oie_order_host }}"',
            'id="oie-listener-port" value="{{ oie_result_port }}"',
            'id="oie-unmatched-result-list"',
        ):
            self.assertIn(marker, self.template)
        self.assertNotIn('id="oie-order-list"', self.template)

    def test_oie_owns_feature_state_and_rendering(self):
        self.assertIn("const state = {", self.source)
        for owner in ("inventory", "unmatchedResults", "selectedPatientId", "selectedOrderId"):
            self.assertIn(f"{owner}:", self.source)
        self.assertIn("export function renderOieInventory()", self.source)
        self.assertIn("function renderOieTransmission(item)", self.source)

    def test_oie_uses_feature_api_adapters(self):
        api = (ROOT / "frontend/static/js/api/oie.js").read_text(encoding="utf-8")
        for name in (
            "fetchOieWorkbench", "fetchOieListenerStatus", "startOieResultListener",
            "stopOieResultListener", "sendOieLocalOrder",
        ):
            self.assertIn(f"function {name}(", api)
            self.assertIn(name, self.source)
        self.assertNotIn("fetch(", self.source)

    def test_oie_initialization_is_idempotent_and_owns_interactions(self):
        self.assertIn("let initialized = false", self.source)
        self.assertIn("if (initialized) return", self.source)
        for element_id in (
            "refresh-oie-inventory", "copy-oie-payload", "send-selected-oie-order",
            "start-oie-listener", "stop-oie-listener",
        ):
            self.assertIn(f'byId("{element_id}").addEventListener', self.source)

    def test_entrypoint_has_no_oie_compatibility_boundary(self):
        self.assertEqual('import "./js/app.js";\n', self.entrypoint)
        self.assertNotIn("function renderOieTransmission(item)", self.entrypoint)
        self.assertNotIn("async function sendOieOrder", self.entrypoint)


if __name__ == "__main__":
    unittest.main()
