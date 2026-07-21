from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class PatientViewModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "frontend/static/js/views/patient.js").read_text(encoding="utf-8")
        cls.bootstrap = (ROOT / "frontend/static/js/views/application.js").read_text(encoding="utf-8")

    def test_patient_view_owns_protocol_preview_builders(self):
        for owner in (
            "patientPreviewMrn",
            "buildPatientPreviewPayload",
            "buildPatientFhirPreviewPayload",
            "buildPatientGdtPreviewPayload",
            "buildPatientDicomPreviewPayload",
        ):
            self.assertIn(f"export function {owner}", self.source)
            self.assertNotIn(f"function {owner}", self.bootstrap)

    def test_patient_view_owns_form_and_validation_behavior(self):
        self.assertIn("export const PATIENT_MODE_CONFIG", self.source)
        for owner in (
            "patientDemoPresetForMode",
            "patientFormPayload",
            "setPatientForm",
            "updatePatientModeFields",
            "validatePatientPayload",
            "renderPatientValidation",
        ):
            self.assertIn(f"export function {owner}", self.source)
            self.assertNotIn(f"function {owner}", self.bootstrap)

        self.assertIn('../core/dom.js', self.source)
        self.assertIn("MRN must use canonical format MRN-", self.source)

    def test_patient_view_owns_patient_record_table(self):
        for owner in ("patientStateLabel", "renderPatientRecordList", "renderPatientSummaryFromPayload"):
            self.assertIn(f"export function {owner}", self.source)
            self.assertNotIn(f"function {owner}", self.bootstrap)
        self.assertIn('byId("patient-record-list")', self.source)
        self.assertIn("onSelect(item)", self.source)
        self.assertIn("renderDetailBlock", self.source)

    def test_patient_view_owns_preview_lifecycle(self):
        for owner in ("refreshPatientPreview", "initializePatientView"):
            self.assertIn(f"export function {owner}", self.source)
            self.assertNotIn(f"function {owner}", self.bootstrap)
        for control in (
            "load-patient-demo",
            "refresh-patient-preview",
            "create-patient",
            "refresh-patients",
            "copy-patient-payload",
        ):
            self.assertIn(control, self.source)
        self.assertIn("initializePatientView({", self.bootstrap)
        self.assertIn("let initialized = false", self.source)
        self.assertIn("if (initialized) return", self.source)

    def test_patient_view_owns_async_coordination(self):
        for owner in (
            "configurePatientCoordinator",
            "refreshPatients",
            "createPatientRecord",
            "retryPatientFhirSync",
            "refreshPatientDcm4cheeResults",
        ):
            self.assertIn(f"export {'async ' if owner != 'configurePatientCoordinator' else ''}function {owner}", self.source)
            self.assertNotIn(f"function {owner}", self.bootstrap)
        self.assertIn('../api/patient.js', self.source)
        self.assertIn('../state/patient.js', self.source)
        self.assertIn("configurePatientCoordinator({", self.bootstrap)

    def test_patient_preview_uses_shared_formatting_without_transport(self):
        self.assertIn('../core/formatting.js', self.source)
        self.assertNotIn("requestJson", self.source)
        for contract in (
            "ADT^A04^ADT_A01",
            'resourceType: "Patient"',
            '["8000", "6301"]',
            '"(0010,0020) PatientID"',
        ):
            self.assertIn(contract, self.source)

    def test_bootstrap_consumes_named_patient_preview_exports(self):
        self.assertIn('from "./patient.js"', self.bootstrap)
        self.assertIn("initializeGdtView({ buildPatientPreviewPayload: buildPatientGdtPreviewPayload })", self.bootstrap)


if __name__ == "__main__":
    unittest.main()
