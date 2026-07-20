from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class CrossViewCoordinationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bootstrap = (ROOT / "frontend/static/app.js").read_text(encoding="utf-8")
        cls.dashboard = (ROOT / "frontend/static/js/views/dashboard.js").read_text(encoding="utf-8")
        cls.patient = (ROOT / "frontend/static/js/views/patient.js").read_text(encoding="utf-8")
        cls.order = (ROOT / "frontend/static/js/views/order.js").read_text(encoding="utf-8")

    def test_dashboard_to_gdt_order_navigation_uses_bootstrap_coordinator(self):
        self.assertIn('byId("create-gdt-ecg-order").addEventListener("click", openGdtOrderFlow)', self.bootstrap)
        self.assertIn('selector.value = "gdt"', self.bootstrap)
        self.assertIn('setActiveView("order-view")', self.bootstrap)
        self.assertNotIn('/views/order.js', self.dashboard)

    def test_patient_to_order_selection_uses_shared_state_without_view_imports(self):
        self.assertIn('../state/selection.js', self.patient)
        self.assertIn('../state/selection.js', self.order)
        self.assertNotIn('/views/order.js', self.patient)
        self.assertNotIn('/views/patient.js', self.order)

        selection_uri = (ROOT / "frontend/static/js/state/selection.js").as_uri()
        script = f"""
            import {{ getSelectedPatientId, setSelectedPatientId }} from {selection_uri!r};
            setSelectedPatientId(63);
            if (getSelectedPatientId() !== 63) process.exit(1);
        """
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
