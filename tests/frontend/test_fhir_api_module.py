from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class FhirApiModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "frontend/static/js/api/fhir.js").read_text(encoding="utf-8")
        cls.view = (ROOT / "frontend/static/js/views/fhir.js").read_text(encoding="utf-8")
        cls.bootstrap = (ROOT / "frontend/static/app.js").read_text(encoding="utf-8")

    def test_fhir_adapter_owns_inventory_preview_report_and_retry_endpoints(self):
        for endpoint in (
            "/api/fhir/inventory",
            "/api/fhir/diagnostic-reports",
            "/api/fhir/records/",
            "/api/fhir/resource-preview",
        ):
            self.assertIn(endpoint, self.source)

    def test_fhir_view_consumes_named_fhir_operations(self):
        for operation in (
            "fetchFhirInventory",
            "fetchFhirDiagnosticReports",
            "fetchFhirRecordPreview",
            "fetchFhirResourcePreview",
            "retryFhirRecordSync",
        ):
            self.assertIn(operation, self.view)
        self.assertNotIn('requestJson("/api/fhir/', self.bootstrap)
        self.assertNotIn("requestJson(`/api/fhir/", self.bootstrap)

    def test_fhir_view_owns_state_rendering_and_idempotent_lifecycle(self):
        for owner in (
            "let medplumInventory = []",
            "let medplumDiagnosticReports = {",
            "function renderMedplumConsole()",
            "function renderMedplumDiagnosticReportRollup(patient)",
            "export async function refreshMedplumInventory()",
            "export function initializeFhirView()",
            "if (initialized) return",
        ):
            self.assertIn(owner, self.view)
        self.assertNotIn("requestJson(", self.view)

    def test_bootstrap_only_initializes_and_activates_fhir_view(self):
        self.assertIn("initializeFhirView();", self.bootstrap)
        self.assertIn('registerViewActivation("medplum-view", "Medplum", refreshMedplumInventory)', self.bootstrap)
        self.assertNotIn("function renderMedplumConsole()", self.bootstrap)


if __name__ == "__main__":
    unittest.main()
