import tempfile
import unittest
from pathlib import Path

from backend.application_composition import assemble_application_dependencies
from backend.domain.errors import ValidationError


class OieRepositoryCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.dependencies = assemble_application_dependencies(Path(self.directory.name) / "oie.db")
        self.repository = self.dependencies.oie_repository

    def tearDown(self):
        self.directory.cleanup()

    def test_success_duplicate_unmatched_and_error_projections(self):
        parsed = {
            "messageControlId": "ORU-1", "messageType": "ORU^R01",
            "patientMrn": "UNKNOWN", "placerOrderNumber": "ORD-1",
            "fillerOrderNumber": "",
        }
        accepted = self.repository.record_oie_result("MSH|accepted", parsed)
        self.assertEqual(accepted["matchStatus"], "unmatched-patient")
        self.assertEqual(accepted["parseStatus"], "accepted")
        duplicate = self.repository.record_oie_result("MSH|duplicate", parsed)
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(duplicate["duplicateOfId"], accepted["id"])
        error = self.repository.record_oie_result_error(
            "invalid", "ADT^A04", "unsupported"
        )
        self.assertEqual(error["parseStatus"], "error")
        self.assertEqual(error["error"], "unsupported")
        self.assertEqual([item["id"] for item in self.repository.list_oie_results()],
                         [error["id"], accepted["id"]])

    def test_patient_and_order_matching(self):
        patient = self.dependencies.patient_repository.create_patient_record(
            {"mrn": "MRN-400002", "firstName": "Avery", "lastName": "Morgan",
             "dob": "19850412", "sex": "F", "mode": "hl7-v2"}
        )
        order = self.dependencies.order_repository.create_order_record({"patientRecordId": patient["id"]})
        patient_only = self.repository.record_oie_result(
            "patient", {"messageControlId": "ORU-P", "messageType": "ORU^R01",
                        "patientMrn": "MRN-400002", "placerOrderNumber": "missing",
                        "fillerOrderNumber": ""}
        )
        matched = self.repository.record_oie_result(
            "matched", {"messageControlId": "ORU-O", "messageType": "ORU^R01",
                        "patientMrn": "MRN-400002",
                        "placerOrderNumber": order["placerOrderNumber"],
                        "fillerOrderNumber": ""}
        )
        self.assertEqual(patient_only["matchStatus"], "patient-only")
        self.assertEqual(matched["matchStatus"], "order-matched")
        self.assertEqual(matched["matchedOrderRecordId"], order["id"])

    def test_rejects_missing_message_control_id_without_inserting(self):
        with self.assertRaisesRegex(ValidationError, "MSH-10"):
            self.repository.record_oie_result(
                "MSH|missing-control-id",
                {"messageControlId": "  ", "messageType": "ORU^R01"},
            )

        self.assertEqual([], self.repository.list_oie_results())

    def test_store_and_database_share_write_lock(self):
        self.assertIs(self.dependencies.database.lock, self.dependencies.database.lock)
        self.assertIs(self.repository.lock, self.dependencies.database.lock)

    def test_store_compatibility_delegates_match_direct_repository(self):
        self.assertEqual(self.dependencies.oie_repository.list_oie_results(), self.repository.list_oie_results())


if __name__ == "__main__":
    unittest.main()
