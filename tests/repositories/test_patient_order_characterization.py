import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.domain.errors import SimulatorValidationError
from backend.application_composition import assemble_application_dependencies


class PatientOrderCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "characterization.db"
        self.dependencies = assemble_application_dependencies(self.path)

    def tearDown(self):
        self.directory.cleanup()

    @staticmethod
    def patient(**overrides):
        payload = {
            "firstName": "Avery",
            "lastName": "Morgan",
            "dob": "19850412",
            "sex": "F",
        }
        payload.update(overrides)
        return payload

    def test_mrn_sequence_is_monotonic_skips_collisions_and_survives_restart(self):
        explicit = self.dependencies.patient_repository.create_patient_record(self.patient(mrn="MRN-000001"))
        automatic = self.dependencies.patient_repository.create_patient_record(self.patient(firstName="Blake"))
        self.assertEqual(explicit["summary"]["mrn"], "MRN-000001")
        self.assertEqual(automatic["summary"]["mrn"], "MRN-000002")

        with self.dependencies.database.connect() as connection:
            connection.execute("DELETE FROM local_patient_records WHERE id = ?", (automatic["id"],))

        restarted = assemble_application_dependencies(self.path)
        self.assertEqual(
            restarted.patient_repository.create_patient_record(self.patient(firstName="Casey"))["summary"]["mrn"],
            "MRN-000003",
        )
        with self.assertRaisesRegex(SimulatorValidationError, "already exists"):
            restarted.patient_repository.create_patient_record(self.patient(mrn=" MRN-000001 "))

    def test_patient_payload_failure_rolls_back_row_and_sequence(self):
        with patch.object(self.dependencies.patient_repository, "_build_payload", side_effect=RuntimeError("payload")):
            with self.assertRaisesRegex(RuntimeError, "payload"):
                self.dependencies.patient_repository.create_patient_record(self.patient())

        with self.dependencies.database.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM local_patient_records").fetchone()[0], 0)
            self.assertEqual(
                connection.execute(
                    "SELECT next_value FROM local_identifier_sequences WHERE name = 'patient_mrn'"
                ).fetchone()[0],
                1,
            )

    def test_patient_filters_projection_and_not_found_contract(self):
        hl7 = self.dependencies.patient_repository.create_patient_record(self.patient(mrn="MRN-000501", mode="hl7-v2"))
        self.dependencies.patient_repository.create_patient_record(self.patient(mrn="MRN-000502", mode="fhir"))
        self.assertEqual([row["id"] for row in self.dependencies.patient_repository.list_patient_records("HL7 v2.5.1")], [hl7["id"]])
        self.assertEqual(hl7["summary"]["mrn"], "MRN-000501")
        self.assertIn("patient", hl7)
        self.assertIn("payload", hl7)
        with self.assertRaises(KeyError):
            self.dependencies.patient_repository.get_patient_record(999_999)

    def test_order_identifiers_payload_rollback_filters_and_not_found_contract(self):
        patient = self.dependencies.patient_repository.create_patient_record(self.patient(mrn="MRN-000503"))
        with patch.object(self.dependencies.order_repository, "_build_payload", side_effect=RuntimeError("payload")):
            with self.assertRaisesRegex(RuntimeError, "payload"):
                self.dependencies.order_repository.create_order_record({"patientRecordId": patient["id"]})
        with self.dependencies.database.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM local_order_records").fetchone()[0], 0)

        order = self.dependencies.order_repository.create_order_record({"patientRecordId": patient["id"]})
        self.assertEqual(order["localOrderNumber"], "ORD-000001")
        self.assertEqual(order["placerOrderNumber"], "ORD-000001")
        self.assertIn("ORC|NW|ORD-000001", order["payload"])
        self.assertEqual([row["id"] for row in self.dependencies.order_repository.list_order_records("2.5.1")], [order["id"]])
        with self.assertRaises(KeyError):
            self.dependencies.order_repository.get_order_record(999_999)

    def test_order_send_result_updates_ack_error_and_timestamps(self):
        patient = self.dependencies.patient_repository.create_patient_record(self.patient(mrn="MRN-000504"))
        order = self.dependencies.order_repository.create_order_record({"patientRecordId": patient["id"]})
        accepted = self.dependencies.order_repository.update_order_send_result(
            order["id"], order_status="Accepted", ack_code="AA", ack_control_id="ACK-1", ack_text="OK"
        )
        self.assertEqual(accepted["ack"]["code"], "AA")
        self.assertTrue(accepted["lastSentAt"])
        failed = self.dependencies.order_repository.update_order_send_result(
            order["id"], order_status="Transport error", transport_error="connection refused"
        )
        self.assertEqual(failed["transportError"], "connection refused")
        self.assertTrue(failed["updatedAt"])


if __name__ == "__main__":
    unittest.main()
