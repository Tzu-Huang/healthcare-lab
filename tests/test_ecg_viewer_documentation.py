"""Stable contract checks for the ECG Viewer operator guide."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "ecg-viewer-verification.md"


class EcgViewerDocumentationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.guide = GUIDE.read_text(encoding="utf-8")
        cls.requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        cls.dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    def test_declares_supported_sop_classes_and_fixture_invariants(self):
        for uid in (
            "1.2.840.10008.5.1.4.1.1.9.1.1",
            "1.2.840.10008.5.1.4.1.1.9.1.2",
        ):
            self.assertIn(uid, self.guide)
        for contract in ("10,000", "1,000 Hz", "10 seconds", "12"):
            self.assertIn(contract, self.guide)

    def test_documents_reproducible_dependency_paths(self):
        self.assertIn("python -m pip install -r requirements.txt", self.guide)
        self.assertIn("pydicom>=3.0,<4.0", self.guide)
        self.assertIn("matplotlib>=3.11,<3.12", self.guide)
        self.assertIn("python -m pip install --no-cache-dir -r requirements.txt", self.dockerfile)
        self.assertIn("pydicom>=3.0,<4.0", self.requirements)
        self.assertIn("matplotlib>=3.11,<3.12", self.requirements)

    def test_marks_manual_evidence_pending_and_protects_fixture_data(self):
        self.assertIn("pending / environment-dependent", self.guide)
        for phrase in (
            "confirmed synthetic fixture",
            "explicit synthetic-data",
            "outside the repository",
            "Do not upload real patient data",
            "never attach the DICOM payload",
        ):
            self.assertIn(phrase, self.guide)

    def test_covers_safe_operation_troubleshooting_and_limitations(self):
        for phrase in (
            "View ECG Graph",
            "DCM4CHEE_WADO_RS_URL",
            "demonstration-only",
            "non-diagnostic",
            "Zoom",
            "calipers",
            "annotations",
            "print layout",
            "export",
        ):
            self.assertIn(phrase, self.guide)
        for forbidden_instruction in (
            "paste upstream bodies",
            "embedding a secret",
        ):
            self.assertIn(forbidden_instruction, self.guide)


if __name__ == "__main__":
    unittest.main()
