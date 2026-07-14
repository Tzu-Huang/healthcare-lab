import unittest

from backend.domain.fhir import (
    attachment_reference_values,
    fhir_bundle_resources,
    normalize_fhir_reference,
    operation_outcome_from_error,
)


class FhirDomainTest(unittest.TestCase):
    def test_reference_and_bundle_mapping(self):
        self.assertEqual("Patient/123", normalize_fhir_reference(" Patient/123 ", "Patient"))
        bundle = {"resourceType": "Bundle", "entry": [{"resource": {"resourceType": "Patient", "id": "123"}}]}
        self.assertEqual("123", fhir_bundle_resources(bundle, "Patient")[0]["id"])

    def test_nested_attachment_references_are_unique(self):
        value = [{"url": "Binary/1", "nested": {"url": "Binary/1"}}, {"url": "DocumentReference/2"}]
        self.assertEqual(["Binary/1", "DocumentReference/2"], attachment_reference_values(value))

    def test_operation_outcome_is_extracted_from_upstream_error(self):
        outcome = operation_outcome_from_error('Medplum returned HTTP 400: {"resourceType":"OperationOutcome"}')
        self.assertEqual("OperationOutcome", outcome["resourceType"])


if __name__ == "__main__":
    unittest.main()
