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


if __name__ == "__main__":
    unittest.main()
