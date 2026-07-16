import unittest

from backend.domain.errors import SimulatorValidationError
from backend.domain.fhir_ledger import (
    identifier_token, identifier_value, list_resource_mappings,
    mapping_for_resource_type, normalize_record_payload,
)


class FhirLedgerDomainTests(unittest.TestCase):
    def test_mapping_identifier_and_normalization_preserve_contract(self):
        mappings = {item["resourceType"]: item for item in list_resource_mappings()}
        self.assertEqual(
            set(mappings),
            {"Patient", "ServiceRequest", "Binary", "Observation", "DocumentReference", "DiagnosticReport", "Provenance"},
        )
        self.assertEqual(["Patient"], mappings["ServiceRequest"]["dependsOn"])
        self.assertEqual(70, mappings["DiagnosticReport"]["dependencyOrder"])
        self.assertEqual("a-b-record", f"{identifier_token('A B')}-{identifier_token('')}")
        self.assertEqual(
            "local-order-records-42",
            identifier_value("ServiceRequest", "local_order_records", 42),
        )
        values = normalize_record_payload({
            "localSourceId": "42",
            "resource": {"resourceType": "ServiceRequest", "status": "active"},
        })
        self.assertEqual("local_order_records", values["local_source_type"])
        self.assertIn('"value": "local-order-records-42"', values["resource_json"])

    def test_validation_rejects_unsupported_resources_and_bad_json(self):
        with self.assertRaisesRegex(SimulatorValidationError, "must be one of"):
            mapping_for_resource_type("Task")
        with self.assertRaisesRegex(SimulatorValidationError, "JSON is invalid"):
            normalize_record_payload({"localSourceId": "1", "resourceJson": "{"})
        with self.assertRaisesRegex(SimulatorValidationError, "dependencies must be a list"):
            normalize_record_payload({
                "localSourceId": "1", "resource": {"resourceType": "Patient"},
                "dependencies": "Patient",
            })


if __name__ == "__main__":
    unittest.main()
