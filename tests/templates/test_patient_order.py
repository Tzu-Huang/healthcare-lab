import json
import unittest

from backend.templates.order import build_orm
from backend.templates.patient import build_dicom, build_fhir, build_hl7
from backend.templates.hl7 import escape, escape_composite


VALUES = {
    "mrn": "MRN-1", "first_name": "Avery", "middle_name": "Lee", "last_name": "Morgan",
    "dob": "19850412", "sex": "F", "address": "1 Main", "phone": "123", "email": "a@example.test",
    "fhir_active": True, "address_line": "1 Main", "address_city": "Taipei", "address_state": "",
    "address_postal_code": "100", "address_country": "TW", "managing_organization_reference": "",
    "managing_organization_display": "", "visit_number": "", "patient_class": "O",
    "assigned_location": "CARD^1", "attending_provider": "P1^Doctor", "account_number": "",
}


class PatientOrderTemplateTests(unittest.TestCase):
    def test_shared_hl7_primitives_preserve_delimiters_and_line_breaks(self):
        self.assertEqual(r"A\F\B\S\C\T\D\R\E\E\\.br\F", escape("A|B^C&D~E\\\nF"))
        self.assertEqual(r"A\F\B^C\T\D", escape_composite("A|B^C&D"))

    def test_patient_templates_preserve_representative_payloads(self):
        hl7, visit = build_hl7(VALUES, record_id=1, timestamp="20260715103000")
        self.assertEqual(visit, "VISIT-000001")
        self.assertIn("PID|1||MRN-1^^^HEALTHCARE_LAB^MR", hl7)
        fhir, _ = build_fhir(VALUES, record_id=1)
        self.assertEqual(json.loads(fhir)["identifier"][0]["value"], "MRN-1")
        dicom, _ = build_dicom(VALUES, record_id=1)
        self.assertEqual(json.loads(dicom)["(0010,0020) PatientID"], "MRN-1")

    def test_order_template_preserves_row_derived_identifiers(self):
        payload = build_orm({**VALUES, "local_order_number": "ORD-000001", "filler_order_number": "",
            "visit_id": "VISIT-000001", "priority": "R", "requested_at": "20260715103000", "scheduled_at": "20260715110000",
            "ordering_provider": "1001^WANG^AMY", "clinical_indication": "Chest pain",
            "order_code": "ECG12", "order_code_text": "12 Lead ECG", "alternate_code": "93000",
            "alternate_code_text": "Electrocardiogram", "alternate_code_system": "C4"},
            record_id=1, timestamp="20260715103000")
        self.assertIn("ORC|NW|ORD-000001", payload)
        self.assertIn("OBR|1|ORD-000001", payload)
        segments = {segment.split("|", 1)[0]: segment.split("|") for segment in payload.split("\r")}
        self.assertEqual(segments["TQ1"][7], "20260715110000")
        self.assertEqual(segments["OBR"][36], "20260715110000")


if __name__ == "__main__":
    unittest.main()
