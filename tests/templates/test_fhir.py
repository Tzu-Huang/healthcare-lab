import unittest

from backend.domain.errors import SimulatorValidationError
from backend.domain.fhir_order import validate_payload
from backend.templates.fhir import build_service_request


class FhirTemplateTests(unittest.TestCase):
    def values(self, **fhir):
        return validate_payload(
            {"patientRecordId": 3, "fhir": fhir},
            timestamp_factory=lambda: "2026-07-08T09:00:00+00:00",
            storage_timestamp_factory=lambda: "20260708090000",
        )

    def test_service_request_is_deterministic_and_preserves_optional_fields(self):
        resource = build_service_request(
            self.values(
                priority="stat", occurrenceDateTime="2026-07-08T10:30:00Z",
                requester="Practitioner/prac-1", reasonCodeText="Chest pain",
                identifier=["urn:extra|abc"], basedOn="ServiceRequest/prior",
                quantityValue="2.5", quantityUnit="mL", note="Internal note",
            ),
            record_id=9, local_order_number="ORD-000009", patient_reference="Patient/patient-1",
        )
        self.assertEqual("ServiceRequest", resource["resourceType"])
        self.assertEqual("Patient/patient-1", resource["subject"]["reference"])
        self.assertEqual("ORD-0009", resource["identifier"][0]["value"])
        self.assertEqual({"system": "urn:extra", "value": "abc"}, resource["identifier"][1])
        self.assertEqual([{"reference": "ServiceRequest/prior"}], resource["basedOn"])
        self.assertEqual({"value": 2.5, "unit": "mL"}, resource["quantityQuantity"])
        self.assertEqual({"reference": "Practitioner/prac-1"}, resource["requester"])

    def test_invalid_reference_and_quantity_are_rejected(self):
        with self.assertRaisesRegex(SimulatorValidationError, "FHIR reference"):
            build_service_request(
                self.values(encounter="bad"), record_id=1,
                local_order_number="ORD-000001", patient_reference="Patient/1",
            )
        with self.assertRaisesRegex(SimulatorValidationError, "must be numeric"):
            build_service_request(
                self.values(quantityValue="many"), record_id=1,
                local_order_number="ORD-000001", patient_reference="Patient/1",
            )


if __name__ == "__main__":
    unittest.main()
