from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class GdtViewModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "frontend/static/js/views/gdt.js").read_text(encoding="utf-8")
        cls.api = (ROOT / "frontend/static/js/api/gdt.js").read_text(encoding="utf-8")

    def test_gdt_owns_state_and_workbench_rendering(self):
        self.assertIn("const state = {", self.source)
        for name in ("workbench", "bridgeConfig", "selectedPatientId", "selectedPayload"):
            self.assertIn(f"{name}:", self.source)
        self.assertIn("function renderGdtPatients()", self.source)
        self.assertIn("function renderGdtPatientOrders(patient)", self.source)
        self.assertIn('["Order", "MRN", "Status", "Created", "Result", "Actions"]', self.source)
        self.assertIn('String(item.exportPath || "").split', self.source)
        self.assertIn("function renderGdtPatientResults(patient)", self.source)
        self.assertIn('["File", "Status", "Updated", "Action"]', self.source)
        self.assertIn("matchingOrder?.exportPath", self.source)

    def test_gdt_initialization_is_idempotent_and_uses_explicit_patient_builder(self):
        self.assertIn("export function initializeGdtView(options = {})", self.source)
        self.assertIn("if (initialized) return", self.source)
        self.assertIn("buildPatientPreviewPayload = options.buildPatientPreviewPayload", self.source)
        self.assertNotIn("views/patient", self.source)

    def test_gdt_uses_feature_api_adapter(self):
        for endpoint in ("bridge/config", "bridge/watcher/start", "bridge/watcher/stop", "workbench", "write-6302", "demo-result"):
            self.assertIn(endpoint, self.api)
        self.assertNotIn("requestJson(", self.source)


if __name__ == "__main__":
    unittest.main()
