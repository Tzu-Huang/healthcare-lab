from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Dcm4cheeStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = ROOT / "frontend/static/js/state/dcm4chee.js"
        cls.source = cls.path.read_text(encoding="utf-8")
        cls.bootstrap = (ROOT / "frontend/static/app.js").read_text(encoding="utf-8")

    def test_diagnostics_and_expansion_have_feature_state_apis(self):
        for operation in (
            "getDcm4cheeProfileDiagnostics",
            "setDcm4cheeProfileDiagnostics",
            "isDcm4cheePatientExpanded",
            "toggleDcm4cheePatientExpanded",
        ):
            self.assertIn(f"export function {operation}", self.source)
            self.assertIn(operation, self.bootstrap)
        self.assertNotIn("let dcm4cheeProfileDiagnostics", self.bootstrap)
        self.assertNotIn("let expandedDcm4cheePatientIds", self.bootstrap)

    def test_state_round_trips_without_exposing_writable_collections(self):
        script = f"""
            import {{
              getDcm4cheeProfileDiagnostics,
              isDcm4cheePatientExpanded,
              setDcm4cheeProfileDiagnostics,
              toggleDcm4cheePatientExpanded,
            }} from {self.path.as_uri()!r};
            const diagnostics = {{ profileName: "local" }};
            setDcm4cheeProfileDiagnostics(diagnostics);
            if (getDcm4cheeProfileDiagnostics() !== diagnostics) process.exit(1);
            if (isDcm4cheePatientExpanded(63)) process.exit(2);
            if (!toggleDcm4cheePatientExpanded(63) || !isDcm4cheePatientExpanded(63)) process.exit(3);
            if (toggleDcm4cheePatientExpanded(63) || isDcm4cheePatientExpanded(63)) process.exit(4);
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
