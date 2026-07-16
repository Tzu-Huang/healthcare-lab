import unittest

from backend.domain import gdt_workflow


class GdtWorkflowDomainTests(unittest.TestCase):
    def test_identifiers_and_order_preparation_are_deterministic(self):
        self.assertEqual("GDT-PAT-000007", gdt_workflow.patient_number(7))
        self.assertEqual("GDT-ORD-000009", gdt_workflow.order_number(9))
        prepared = gdt_workflow.prepare_order_payload(
            demographics={"firstName": "Avery", "lastName": "Morgan", "dob": "19850412", "sex": "F"},
            summary={}, gdt_patient_number="GDT-PAT-000007",
            local_order_number="GDT-ORD-000009", requested_at="20260716120000",
            ordering_provider="1001^WANG^AMY", clinical_indication="Baseline",
            patient_snapshot={"id": 7}, order_snapshot={"id": 9}, test_label="12-lead resting ECG",
        )
        self.assertEqual("12041985", prepared["birthDate"])
        self.assertEqual("2", prepared["sex"])
        self.assertEqual("GDT-ORD-000009", prepared["localGdtOrderNumber"])
