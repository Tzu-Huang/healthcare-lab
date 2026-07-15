import json
import tempfile
import unittest
from pathlib import Path

from backend.lab_store import DemoStore


class ExtractedPatientOrderRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = DemoStore(Path(self.directory.name) / "repositories.db")

    def tearDown(self):
        self.directory.cleanup()

    def test_repositories_share_database_lock_and_facade_delegates(self):
        self.assertIs(self.store.patient_repository.lock, self.store.database.lock)
        self.assertIs(self.store.order_repository.lock, self.store.database.lock)
        patient = self.store.patient_repository.create_patient_record({"firstName": "Avery", "lastName": "Morgan", "dob": "19850412", "sex": "F"})
        self.assertEqual(self.store.get_patient_record(patient["id"]), patient)
        order = self.store.order_repository.create_order_record({"patientRecordId": patient["id"]})
        self.assertEqual(self.store.get_order_record(order["id"]), order)

    def test_existing_database_can_be_reopened_without_schema_change(self):
        patient = self.store.create_patient_record({"mrn": "EXTERNAL-1", "firstName": "Avery", "lastName": "Morgan", "dob": "19850412", "sex": "F"})
        reopened = DemoStore(self.store.path)
        self.assertEqual(reopened.patient_repository.get_patient_record(patient["id"])["summary"]["mrn"], "EXTERNAL-1")

    def test_latest_empty_dicom_refresh_snapshot_remains_authoritative(self):
        patient = self.store.create_patient_record({
            "firstName": "Avery", "lastName": "Morgan", "dob": "19850412", "sex": "F"
        })
        with self.store.connect() as connection:
            connection.execute(
                """INSERT INTO local_dcm4chee_result_refresh_runs (
                    patient_record_id, refresh_generation, started_at, completed_at,
                    results_snapshot_json
                ) VALUES (?, 'older', '1', '1', ?)""",
                (patient["id"], json.dumps([{"marker": "stale"}])),
            )
            connection.execute(
                """INSERT INTO local_dcm4chee_result_refresh_runs (
                    patient_record_id, refresh_generation, started_at, completed_at,
                    results_snapshot_json
                ) VALUES (?, 'latest', '2', '2', '[]')""",
                (patient["id"],),
            )

        projected = self.store.get_patient_record(patient["id"])

        self.assertEqual(projected["dcm4chee"]["dicomResults"], [])
        self.assertEqual(projected["dcm4chee"]["resultCount"], 0)


if __name__ == "__main__":
    unittest.main()
