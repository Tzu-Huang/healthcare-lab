import unittest

from backend.domain.errors import SimulatorValidationError
from backend.domain.order import account_number, record_number as order_number, validate_payload as validate_order
from backend.domain.patient import record_number as patient_number, validate_payload as validate_patient


class PatientOrderDomainTests(unittest.TestCase):
    def test_patient_validation_normalizes_without_framework_or_database(self):
        values = validate_patient({"firstName": " Avery ", "lastName": " Morgan ", "dob": "1985-04-12", "sex": "f"})
        self.assertEqual((values["first_name"], values["dob"], values["sex"]), ("Avery", "19850412", "F"))
        self.assertEqual(patient_number(7), "PAT-000007")
        with self.assertRaisesRegex(SimulatorValidationError, "firstName is required"):
            validate_patient({"lastName": "Morgan", "dob": "19850412", "sex": "F"})

    def test_order_validation_normalizes_and_formats_identifiers(self):
        values = validate_order({"patientRecordId": "9", "priority": "s", "requestedAt": "2026-07-15 10:30", "scheduledAt": "2026-07-15 11:00"}, timestamp_factory=lambda: "unused")
        self.assertEqual((values["patient_record_id"], values["priority"], values["requested_at"]), (9, "S", "202607151030"))
        self.assertEqual(values["scheduled_at"], "202607151100")
        self.assertEqual(order_number(7), "ORD-000007")
        self.assertEqual(account_number(7), "ACC-ORD-000007")


if __name__ == "__main__":
    unittest.main()
