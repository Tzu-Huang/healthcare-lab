import unittest

from backend.mappers import gdt


class GdtMapperTests(unittest.TestCase):
    def test_snapshot_and_attachment_filename_preserve_shapes(self):
        patient = {"id": 7, "patient": {"mrn": "MRN-7", "firstName": "Avery"},
                   "summary": {"visitNumber": "VISIT-7"}}
        self.assertEqual(
            {"patientRecordId": 7, "mrn": "MRN-7", "gdtPatientNumber": "GDT-PAT-000007",
             "firstName": "Avery", "middleName": "", "lastName": "", "dob": "", "sex": "",
             "visitNumber": "VISIT-7"},
            gdt.patient_snapshot(patient, "GDT-PAT-000007"),
        )
        self.assertEqual("report.pdf", gdt.attachment_filename("", r"reports\report.pdf"))

    def test_message_projection_decodes_json_without_persistence(self):
        row = {"id": 1, "order_record_id": 2, "patient_context_id": 3,
               "direction": "inbound", "message_type": "6310", "raw_gdt_text": "raw",
               "parsed_fields_json": '{"8000":["6310"]}', "canonical_json": "{}",
               "parse_status": "accepted", "match_status": "order-matched", "error_text": "",
               "generated_at": "", "received_at": "now", "created_at": "now", "updated_at": "now"}
        self.assertEqual({"8000": ["6310"]}, gdt.project_message(row)["parsedFields"])
