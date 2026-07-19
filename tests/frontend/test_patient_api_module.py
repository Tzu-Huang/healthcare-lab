from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class PatientApiModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "frontend/static/js/api/patient.js").read_text(encoding="utf-8")
        cls.bootstrap = (ROOT / "frontend/static/app.js").read_text(encoding="utf-8")

    def test_patient_adapter_owns_list_create_fhir_retry_and_dcm4chee_refresh(self):
        for operation in (
            "fetchPatients",
            "createPatient",
            "retryPatientFhirSync",
            "refreshPatientDcm4cheeResults",
        ):
            self.assertIn(f"export function {operation}", self.source)
            self.assertIn(operation, self.bootstrap)
        for endpoint in (
            "/api/patients",
            "/fhir-sync",
            "/dcm4chee-results-refresh",
        ):
            self.assertIn(endpoint, self.source)

    def test_bootstrap_has_no_direct_patient_transport(self):
        self.assertNotIn('requestJson("/api/patients', self.bootstrap)
        self.assertNotIn('requestJson(`/api/patients', self.bootstrap)
        self.assertNotIn('requestJsonAllowBusinessFailure(`/api/patients', self.bootstrap)


if __name__ == "__main__":
    unittest.main()
