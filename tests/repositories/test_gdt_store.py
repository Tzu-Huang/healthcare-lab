import unittest

from ._case_support import *

class GdtStoreTests(StoreCaseSupport):
    """Focused assertion owner for GdtStoreTests."""

    def test_gdt_order_creation_persists_fixed_ekg01_order(self):
        patient = self.store.create_patient_record(
            {
                "mode": "gdt",
                "mrn": "MRN-GDT-001",
                "firstName": "Avery",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
            }
        )

        order = self.store.create_gdt_order_record(
            {
                "patientRecordId": patient["id"],
                "requestedAt": "20260706110000",
                "orderingProvider": "1001^WANG^AMY",
                "clinicalIndication": "Resting ECG baseline",
                "attachmentUrl": "http://localhost/reports/demo.pdf",
            }
        )

        self.assertEqual(order["localGdtOrderNumber"], "GDT-ORD-000001")
        self.assertEqual(order["protocolVersion"], "GDT 2.1")
        self.assertEqual(order["messageType"], "6302")
        self.assertEqual(order["status"], "Created")
        self.assertEqual(order["gdtTestField"], "8402")
        self.assertEqual(order["gdtTestCode"], "EKG01")
        self.assertEqual(order["attachmentUrl"], "http://localhost/reports/demo.pdf")
        records = parse_gdt_records(order["payload"])
        self.assertEqual(records["8000"], "6302")
        self.assertEqual(records["8402"], "EKG01")
        self.assertEqual(records["3000"], "GDT-PAT-000001")
        self.assertEqual(records["6200"], "06072026")
        self.assertEqual(records["6330"], "GDT-ORD-000001")
        self.assertEqual(records["6227"], "1001^WANG^AMY | Resting ECG baseline")
        self.assertNotIn("6220", records)
        self.assertNotIn("6228", records)
        self.assertEqual(records["8100"], f"{len(order['payload'].encode('cp1252')):05d}")
        self.assertEqual(order["gdtPatientNumber"], "GDT-PAT-000001")
        self.assertEqual(order["summary"]["mrn"], "MRN-GDT-001")
        self.assertEqual(order["summary"]["gdtPatientNumber"], "GDT-PAT-000001")
        self.assertEqual(order["messages"][0]["messageType"], "6302")
        self.assertEqual(order["messages"][0]["parsedFields"]["8402"], ["EKG01"])
        self.assertEqual(order["messages"][0]["canonical"]["patient"]["mrn"], "MRN-GDT-001")
        self.assertEqual(order["attachments"][0]["url"], "http://localhost/reports/demo.pdf")
        self.assertEqual(order["attachments"][0]["role"], "order-attachment")
        self.assertIn("order-created", {event["eventType"] for event in order["events"]})
        self.assertEqual(self.store.list_gdt_order_records()[0]["id"], order["id"])
        self.assertEqual(self.store.list_gdt_orders()[0]["orderNumber"], "GDT-ORD-000001")

    def test_gdt_patient_number_override_is_snapshotted(self):
        patient = self.store.create_patient_record(
            {
                "mode": "gdt",
                "mrn": "MRN-GDT-OVERRIDE",
                "firstName": "Avery",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
            }
        )

        order = self.store.create_gdt_order_record(
            {
                "patientRecordId": patient["id"],
                "gdtPatientNumberOverride": "MANUAL-3000-01",
            }
        )

        records = parse_gdt_records(order["payload"])
        self.assertEqual(records["3000"], "MANUAL-3000-01")
        self.assertEqual(order["gdtPatientNumber"], "MANUAL-3000-01")
        self.assertEqual(order["patientSnapshot"]["gdtPatientNumber"], "MANUAL-3000-01")
        self.assertIn("patient-number-overridden", {event["eventType"] for event in order["events"]})

    def test_gdt_result_import_persists_canonical_message_attachments_and_events(self):
        patient = self.store.create_patient_record(
            {
                "mode": "gdt",
                "mrn": "MRN-GDT-RESULT",
                "firstName": "Avery",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
            }
        )
        order = self.store.create_gdt_order_record({"patientRecordId": patient["id"]})
        result_payload = render_gdt_message(
            [
                ("3000", order["gdtPatientNumber"]),
                ("8402", "EKG01"),
                ("3101", "Morgan"),
                ("3102", "Avery"),
                ("6330", order["localGdtOrderNumber"]),
                ("8418", "B"),
                ("8410", "HR"),
                ("8420", "75"),
                ("8421", "/min"),
                ("8410", "PR"),
                ("8420", "160"),
                ("8421", "ms"),
                ("6220", "Normal sinus rhythm"),
                ("6227", "Reviewed by device"),
                ("6228", "Automated ECG summary"),
                ("6302", "reports/ecg-result.pdf"),
                ("6303", "application/pdf"),
                ("6304", "reports/ecg-waveform.xml"),
                ("6305", "application/xml"),
            ],
            set_type="6310",
        )

        result = self.store.record_gdt_result(
            {"rawGdtText": result_payload, "sourceFile": "device-result.gdt"}
        )

        self.assertEqual(result["messageType"], "6310")
        self.assertEqual(result["matchStatus"], "order-matched")
        self.assertEqual(result["parsedFields"]["6220"], ["Normal sinus rhythm"])
        self.assertEqual(result["canonical"]["order"]["localGdtOrderNumber"], order["localGdtOrderNumber"])
        self.assertEqual(result["canonical"]["result"]["status"], "B")
        self.assertEqual(result["canonical"]["result"]["measurements"]["HR"]["value"], 75)
        self.assertEqual(result["canonical"]["result"]["measurements"]["PR"]["unit"], "ms")
        self.assertEqual(result["canonical"]["result"]["comments"], ["Reviewed by device"])
        self.assertEqual(result["canonical"]["result"]["formattedText"], ["Automated ECG summary"])
        self.assertEqual(result["canonical"]["validation"], {"errors": [], "warnings": []})
        updated_order = self.store.get_gdt_order_record(order["id"])
        self.assertEqual(updated_order["status"], "Result received")
        by_role = {attachment["role"]: attachment for attachment in updated_order["attachments"]}
        self.assertEqual(by_role["report"]["reference"], "reports/ecg-result.pdf")
        self.assertEqual(by_role["report"]["sourceFile"], "device-result.gdt")
        self.assertEqual(by_role["waveform"]["contentType"], "application/xml")
        self.assertEqual(by_role["waveform"]["path"], "reports/ecg-waveform.xml")
        event_types = {event["eventType"] for event in updated_order["events"]}
        self.assertIn("result-imported", event_types)
        self.assertIn("result-matched", event_types)

    def test_gdt_unmatched_result_is_persisted(self):
        result_payload = render_gdt_message(
            [
                ("3000", "UNKNOWN-GDT-PAT"),
                ("8402", "EKG01"),
                ("8410", "UNKNOWN-ORDER"),
                ("6220", "Unmatched result"),
            ],
            set_type="6310",
        )

        result = self.store.record_gdt_result({"rawGdtText": result_payload})

        self.assertEqual(result["messageType"], "6310")
        self.assertEqual(result["matchStatus"], "unmatched")
        self.assertEqual(result["rawGdtText"], result_payload)

    def test_gdt_result_without_order_identifier_does_not_guess_latest_patient_order(self):
        patient = self.store.create_patient_record(
            {
                "mode": "gdt",
                "mrn": "MRN-GDT-MULTI",
                "firstName": "Avery",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
            }
        )
        first_order = self.store.create_gdt_order_record(
            {"patientRecordId": patient["id"], "clinicalIndication": "First order"}
        )
        second_order = self.store.create_gdt_order_record(
            {"patientRecordId": patient["id"], "clinicalIndication": "Second order"}
        )
        result_payload = render_gdt_message(
            [
                ("3000", first_order["gdtPatientNumber"]),
                ("8402", "EKG01"),
                ("6220", "Result has no usable order identifier"),
            ],
            set_type="6310",
        )

        result = self.store.record_gdt_result({"rawGdtText": result_payload})

        self.assertEqual(result["matchStatus"], "unmatched")
        self.assertIsNone(result["orderRecordId"])
        self.assertEqual(self.store.get_gdt_order_record(first_order["id"])["status"], "Created")
        self.assertEqual(self.store.get_gdt_order_record(second_order["id"])["status"], "Created")

    def test_gdt_order_events_do_not_include_other_order_lifecycle_events(self):
        patient = self.store.create_patient_record(
            {
                "mode": "gdt",
                "mrn": "MRN-GDT-EVENTS",
                "firstName": "Avery",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
            }
        )
        first_order = self.store.create_gdt_order_record(
            {"patientRecordId": patient["id"], "clinicalIndication": "First order"}
        )
        second_order = self.store.create_gdt_order_record(
            {"patientRecordId": patient["id"], "clinicalIndication": "Second order"}
        )

        first_events = self.store.list_gdt_events(first_order["id"])
        first_order_created = [
            event
            for event in first_events
            if event["eventType"] == "order-created"
        ]

        self.assertEqual([event["orderRecordId"] for event in first_order_created], [first_order["id"]])
        self.assertNotIn(
            second_order["id"],
            {
                event["orderRecordId"]
                for event in first_events
                if event["orderRecordId"] is not None
            },
        )
        self.assertIn("patient-number-generated", {event["eventType"] for event in first_events})

    def test_gdt_order_creation_rejects_non_mvp_8402_codes(self):
        patient = self.store.create_patient_record(
            {
                "mrn": "MRN-GDT-002",
                "firstName": "Avery",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
            }
        )

        with self.assertRaises(SimulatorValidationError):
            self.store.create_gdt_order_record({"patientRecordId": patient["id"], "gdtTestCode": "EKG04"})

        with self.assertRaises(SimulatorValidationError):
            self.store.create_gdt_order_record({"patientRecordId": patient["id"], "gdtTestCode": "ERGO01"})


if __name__ == "__main__":
    unittest.main()
