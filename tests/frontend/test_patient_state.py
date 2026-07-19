from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class PatientStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = ROOT / "frontend/static/js/state/patient.js"
        cls.source = cls.path.read_text(encoding="utf-8")
        cls.bootstrap = (ROOT / "frontend/static/app.js").read_text(encoding="utf-8")

    def test_patient_records_have_explicit_state_api(self):
        for operation in ("getPatientRecords", "setPatientRecords", "replacePatientRecord"):
            self.assertIn(f"export function {operation}", self.source)
            self.assertIn(operation, self.bootstrap)
        self.assertNotIn("let patientRecords", self.bootstrap)

    def test_patient_state_replaces_matching_record_without_mutating_input(self):
        module_uri = self.path.as_uri()
        script = f"""
            import {{ getPatientRecords, replacePatientRecord, setPatientRecords }} from {module_uri!r};
            const original = [{{ id: 1, name: "A" }}, {{ id: 2, name: "B" }}];
            setPatientRecords(original);
            replacePatientRecord({{ id: 2, name: "Updated" }});
            const records = getPatientRecords();
            if (records === original || records[1].name !== "Updated" || original[1].name !== "B") process.exit(1);
            setPatientRecords(null);
            if (getPatientRecords().length !== 0) process.exit(2);
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
