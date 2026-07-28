import json
import tempfile
import unittest
from pathlib import Path

from tools.validate_ecg_fixtures import DEFAULT_MANIFEST, validate_manifest


def local_fixture_files_available(manifest_path: Path = DEFAULT_MANIFEST) -> bool:
    if not manifest_path.is_file():
        return False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return all(
        (manifest_path.parent / fixture["path"]).is_file()
        for fixture in manifest["fixtures"]
    )


def require_local_fixture_files(manifest_path: Path = DEFAULT_MANIFEST) -> None:
    if not local_fixture_files_available(manifest_path):
        raise unittest.SkipTest("optional local ECG fixtures are not available")


class EcgFixtureManifestValidationTest(unittest.TestCase):
    def test_supplied_local_only_fixtures_match_manifest(self):
        require_local_fixture_files()
        self.assertEqual(validate_manifest(), [])

    def test_hash_drift_is_reported_without_dicom_values(self):
        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        manifest["fixtures"] = manifest["fixtures"][:1]
        manifest["fixtures"][0]["sha256"] = "0" * 64

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / DEFAULT_MANIFEST.name
            path.write_text(json.dumps(manifest), encoding="utf-8")
            (path.parent / manifest["fixtures"][0]["path"]).write_bytes(
                b"synthetic hash-drift sentinel"
            )
            errors = validate_manifest(path)

        self.assertEqual(
            errors,
            ["12lead_ecg_waveform.dcm: content hash drift"],
        )

    def test_manifest_records_synthetic_confirmation_without_identity_values(self):
        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))

        for fixture in manifest["fixtures"]:
            deidentification = fixture["deidentification"]
            self.assertEqual(deidentification["status"], "synthetic-confirmed")
            self.assertFalse(deidentification["contains_real_patient_data"])
            self.assertIn("User confirmation", deidentification["confirmation_source"])
            self.assertEqual(
                fixture["handling"]["classification"], "synthetic-local-test"
            )
            self.assertTrue(fixture["handling"]["excluded_from_source_control"])
            self.assertNotIn("identity_values", deidentification)

    def test_clean_checkout_without_local_fixtures_is_detected_for_skip(self):
        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / DEFAULT_MANIFEST.name
            path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(
                unittest.SkipTest,
                "optional local ECG fixtures are not available",
            ):
                require_local_fixture_files(path)


if __name__ == "__main__":
    unittest.main()
