from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Dcm4cheeViewModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "frontend/static/js/views/dcm4chee.js").read_text(encoding="utf-8")
        cls.bootstrap = (ROOT / "frontend/static/app.js").read_text(encoding="utf-8")

    def test_view_owns_result_grouping_and_nested_rendering(self):
        for owner in (
            "groupDcm4cheeResultsForBrowser",
            "countDcm4cheeResults",
            "summarizeDcm4cheeResultGroup",
            "renderDcm4cheeInstanceTable",
            "renderDcm4cheeSeriesDetails",
            "renderDcm4cheeStudyDetails",
            "renderDcm4cheeResultGroup",
            "renderPatientDcm4cheeResults",
            "renderDcm4cheeResultsBrowser",
        ):
            self.assertIn(f"export function {owner}", self.source)
            self.assertNotIn(f"function {owner}", self.bootstrap)

    def test_result_presentation_uses_core_helpers_without_transport(self):
        self.assertIn('../core/dom.js', self.source)
        self.assertIn('../core/formatting.js', self.source)
        self.assertNotIn("requestJson", self.source)
        self.assertIn('../api/dcm4chee.js', self.source)
        self.assertNotIn('/api/dcm4chee/', self.source)

    def test_patient_order_table_uses_clinical_summary_columns(self):
        self.assertIn(
            '["Accession #", "MRN", "Status", "Created", "Action"]',
            self.source,
        )
        self.assertIn("cell.colSpan = 5", self.source)
        self.assertIn('wrap.classList.add("dcm4chee-order-table-wrap")', self.source)
        action_helper = self.source.split("export function dcm4cheeOrderActionButtons", 1)[1].split("export function", 1)[0]
        self.assertIn('createElement("button", "Send", "small-button")', action_helper)
        for hidden_action in ('"Inspect"', '"Retry"', '"Verify"'):
            self.assertNotIn(hidden_action, action_helper)

    def test_view_owns_selection_actions_attempts_and_lifecycle(self):
        for owner in (
            "selectedDcm4cheePatient",
            "selectedDcm4cheeOrder",
            "selectDcm4cheePatient",
            "selectDcm4cheeOrder",
            "renderDcm4cheeConsole",
            "refreshDcm4cheeConsole",
            "renderDcm4cheeAttemptHistory",
            "loadDcm4cheeAttemptHistory",
            "initializeDcm4cheeView",
        ):
            self.assertIn(f"function {owner}", self.source)
            self.assertNotIn(f"function {owner}", self.bootstrap)
        self.assertIn("let initialized = false", self.source)
        self.assertIn("if (initialized) return", self.source)
        self.assertNotIn('/views/patient.js', self.source)
        self.assertNotIn('/views/order.js', self.source)
        self.assertIn('"DICOM Patient ID"', self.source)
        self.assertIn('"Patient ID Issuer"', self.source)

    def test_selected_order_omits_sync_verification_and_attempt_sections(self):
        selected_order = self.source.split("export function renderDcm4cheeSelectedOrder", 1)[1].split("export function", 1)[0]
        self.assertNotIn('dcm4cheeDetailBlock("MWL Sync"', selected_order)
        self.assertNotIn('dcm4cheeDetailBlock("MWL Verification"', selected_order)
        self.assertNotIn('"dcm4chee Attempts"', selected_order)
        self.assertNotIn("loadDcm4cheeAttemptHistory", selected_order)

        order_actions = self.source.split("export function renderDcm4cheeOrderActions", 1)[1].split("export function", 1)[0]
        for removed_action in ("Verify MWL Query", "Refresh PACS Results", "Simulate AP PDF", "Simulate AP DICOM"):
            self.assertNotIn(removed_action, order_actions)


if __name__ == "__main__":
    unittest.main()
