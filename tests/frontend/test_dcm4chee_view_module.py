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


if __name__ == "__main__":
    unittest.main()
