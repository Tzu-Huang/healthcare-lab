import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.validate_ecg_fixtures import DEFAULT_MANIFEST, validate_manifest


class EcgFixtureManifestValidationTest(unittest.TestCase):
    def test_supplied_local_only_fixtures_match_manifest(self):
        self.assertEqual(validate_manifest(), [])

    def test_hash_drift_is_reported_without_dicom_values(self):
        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        manifest["fixtures"][0]["sha256"] = "0" * 64

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / DEFAULT_MANIFEST.name
            path.write_text(json.dumps(manifest), encoding="utf-8")
            for fixture in manifest["fixtures"]:
                shutil.copy2(DEFAULT_MANIFEST.parent / fixture["path"], Path(directory))
            errors = validate_manifest(path)

        self.assertEqual(
            errors,
            ["12lead_ecg_waveform.dcm: content hash drift"],
        )

    def test_manifest_never_records_identity_values(self):
        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))

        for fixture in manifest["fixtures"]:
            deidentification = fixture["deidentification"]
            self.assertEqual(deidentification["status"], "unresolved")
            self.assertEqual(fixture["handling"]["classification"], "local-only")
            self.assertTrue(fixture["handling"]["excluded_from_source_control"])
            self.assertNotIn("identity_values", deidentification)


if __name__ == "__main__":
    unittest.main()
