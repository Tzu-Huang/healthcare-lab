import ast
import unittest
from collections import defaultdict
from pathlib import Path

from backend.mappers.fhir import project_sync_attempt
from backend.mappers.order import project as project_order
from backend.mappers.patient import project as project_patient


ROOT = Path(__file__).resolve().parents[2]


class PatientOrderFhirMapperTests(unittest.TestCase):
    def test_patient_projection_preserves_defaults_and_nested_shapes(self):
        row = defaultdict(str, id=1, mrn="MRN-1", first_name="Avery",
                          last_name="Morgan", fhir_active=1,
                          validation_messages_json='["ok"]')
        projected = project_patient(row)

        self.assertEqual("Avery Morgan", projected["summary"]["name"])
        self.assertEqual({"status": "", "messages": ["ok"]}, projected["validation"])
        self.assertEqual({"dicomResults": [], "resultCount": 0}, projected["dcm4chee"])
        self.assertIsNone(projected["fhir"])

    def test_order_projection_preserves_ack_and_protocol_specific_defaults(self):
        row = defaultdict(str, id=2, protocol_version="HL7 v2.5.1",
                          validation_messages_json="[]", ack_code="AA")
        projected = project_order(row)

        self.assertEqual("AA", projected["ack"]["code"])
        self.assertIsNone(projected["fhir"])
        self.assertIsNone(projected["dcm4chee"])
        self.assertTrue(projected["localOnly"])

    def test_fhir_attempt_projection_preserves_exact_json_contract(self):
        projected = project_sync_attempt({
            "id": 3, "fhir_record_id": 4, "method": "POST",
            "request_url": "https://example.invalid/fhir",
            "request_payload_json": '{"resourceType":"Patient"}',
            "http_status": 201, "response_payload_json": '{"id":"remote-1"}',
            "operation_outcome_json": "{}", "error_text": "",
            "attempted_at": "2026-07-16T10:00:00+00:00",
        })

        self.assertEqual({
            "id": 3, "fhirRecordId": 4, "method": "POST",
            "requestUrl": "https://example.invalid/fhir",
            "requestPayload": {"resourceType": "Patient"},
            "httpStatus": 201, "responsePayload": {"id": "remote-1"},
            "operationOutcome": {}, "error": "",
            "attemptedAt": "2026-07-16T10:00:00+00:00",
        }, projected)

    def test_projectors_have_only_mapper_implementation_owners(self):
        expected = {
            "backend/domain/patient.py": set(),
            "backend/domain/order.py": set(),
            "backend/domain/fhir_ledger.py": set(),
            "backend/mappers/patient.py": {"project"},
            "backend/mappers/order.py": {"project"},
            "backend/mappers/fhir.py": {"project_workflow_record", "project_sync_attempt"},
        }
        for relative_path, names in expected.items():
            tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
            actual = {
                node.name for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("project")
            }
            with self.subTest(path=relative_path):
                self.assertEqual(names, actual)


if __name__ == "__main__":
    unittest.main()
