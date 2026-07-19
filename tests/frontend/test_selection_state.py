from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class SelectionStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "frontend/static/js/state/selection.js").read_text(encoding="utf-8")
        cls.bootstrap = (ROOT / "frontend/static/app.js").read_text(encoding="utf-8")

    def test_patient_and_order_context_have_explicit_read_and_update_apis(self):
        for operation in (
            "getSelectedPatientId",
            "setSelectedPatientId",
            "getSelectedOrderId",
            "setSelectedOrderId",
        ):
            self.assertIn(f"export function {operation}", self.source)
            self.assertIn(operation, self.bootstrap)

    def test_shared_selection_state_round_trips_and_clears(self):
        module_uri = (ROOT / "frontend/static/js/state/selection.js").as_uri()
        script = f"""
            import {{
              getSelectedOrderId,
              getSelectedPatientId,
              setSelectedOrderId,
              setSelectedPatientId,
            }} from {module_uri!r};
            setSelectedPatientId(17);
            setSelectedOrderId(29);
            if (getSelectedPatientId() !== 17 || getSelectedOrderId() !== 29) process.exit(1);
            setSelectedPatientId(null);
            setSelectedOrderId(null);
            if (getSelectedPatientId() !== null || getSelectedOrderId() !== null) process.exit(2);
        """
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_feature_owned_state_is_not_duplicated_in_the_bootstrap(self):
        for legacy_global in (
            "dashboardServices",
            "dashboardEvents",
            "gdtWorkbench",
            "selectedGdtPatientId",
            "oieInventory",
            "selectedOiePatientId",
            "selectedDcm4cheePatientId",
            "selectedDcm4cheeOrderId",
        ):
            self.assertNotIn(legacy_global, self.bootstrap)


if __name__ == "__main__":
    unittest.main()
