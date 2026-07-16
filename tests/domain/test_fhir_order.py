import re
import unittest

from backend.domain.errors import SimulatorValidationError
from backend.domain.fhir_order import (
    normalize_datetime, storage_priority, validate_payload,
)


class FhirOrderDomainTests(unittest.TestCase):
    def test_validation_preserves_defaults_and_storage_values(self):
        values = validate_payload(
            {"patientRecordId": "7", "fhir": {"priority": "stat", "occurrenceDateTime": "2026-07-08T10:30"}},
            timestamp_factory=lambda: "2026-07-08T09:00:00+00:00",
            storage_timestamp_factory=lambda: "fallback",
        )
        self.assertEqual(7, values["patient_record_id"])
        self.assertEqual(("active", "order", "stat"), (values["status"], values["intent"], values["priority"]))
        self.assertEqual("20260708103000", values["requested_at"])
        self.assertEqual("ECG12", values["order_code"])
        self.assertEqual("S", storage_priority(values["priority"]))
        self.assertRegex(values["occurrence"], r"^2026-07-08T10:30:00(?:Z|[+-]\d{2}:\d{2})$")

    def test_datetime_and_required_patient_validation(self):
        self.assertEqual("2026-07-08", normalize_datetime("20260708"))
        self.assertEqual("not-a-date", normalize_datetime("not-a-date"))
        with self.assertRaisesRegex(SimulatorValidationError, "patientRecordId is required"):
            validate_payload({}, timestamp_factory=lambda: "now", storage_timestamp_factory=lambda: "stamp")


if __name__ == "__main__":
    unittest.main()
