import tempfile
import unittest
import json
from pathlib import Path

from backend.lab_store import DemoStore, SimulatorValidationError, render_gdt_message


def parse_gdt_records(payload):
    raw = payload.encode("cp1252")
    records = {}
    offset = 0
    while offset < len(raw):
        length = int(raw[offset : offset + 3].decode("ascii"))
        record = raw[offset : offset + length]
        assert record.endswith(b"\r\n")
        assert len(record) == length
        code = record[3:7].decode("ascii")
        value = record[7:-2].decode("cp1252")
        records[code] = value
        offset += length
    assert offset == len(raw)
    return records


class HealthcareLabStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = DemoStore(Path(self.directory.name) / "lab.db")

    def tearDown(self):
        self.directory.cleanup()

    def test_lab_server_operation_metadata_is_seeded_non_destructively(self):
        oie = next(item for item in self.store.list_lab_servers() if item["name"] == "OIE")
        self.assertEqual(oie["operation"]["controlType"], "docker-compose")
        self.assertEqual(oie["operation"]["backingService"], "oie")
        self.assertIn("restart", oie["operation"]["supportedActions"])
        self.assertEqual(oie["operation"]["smokeProfile"], "oie")

        self.store.update_lab_server(
            oie["id"],
            {"host": "10.10.10.10", "baseUrl": "http://10.10.10.10:18080"},
        )
        reopened = DemoStore(self.store.path)
        updated = reopened.get_lab_server(oie["id"])

        self.assertEqual(updated["host"], "10.10.10.10")
        self.assertEqual(updated["baseUrl"], "http://10.10.10.10:18080")
        self.assertEqual(updated["operation"]["backingService"], "oie")

    def test_lab_server_custom_operation_metadata_can_be_persisted(self):
        created = self.store.create_lab_server(
            {
                "name": "Custom Lab Tool",
                "serverType": "Test Tool",
                "protocol": "HTTP",
                "baseUrl": "http://127.0.0.1:9000",
                "operation": {
                    "controlType": "external",
                    "backingService": "custom-tool",
                    "supportedActions": ["status", "smoke"],
                    "timeoutSeconds": 30,
                    "smokeProfile": "custom",
                },
            }
        )

        self.assertEqual(created["operation"]["controlType"], "external")
        self.assertEqual(created["operation"]["backingService"], "custom-tool")
        self.assertEqual(created["operation"]["supportedActions"], ["status", "smoke"])
        self.assertEqual(created["operation"]["timeoutSeconds"], 30)
        self.assertEqual(created["operation"]["smokeProfile"], "custom")

        with self.assertRaisesRegex(SimulatorValidationError, "Unsupported lab operation action"):
            self.store.update_lab_server(
                created["id"],
                {"operation": {"supportedActions": ["purge"]}},
            )

    def test_lab_operation_history_persists_progress_and_errors(self):
        medplum = next(item for item in self.store.list_lab_servers() if item["name"] == "Medplum")

        operation = self.store.record_lab_operation(
            medplum["id"],
            service_name="Medplum",
            action="restart",
            operator="tester",
            result="failed",
            duration_ms=1250,
            progress=[
                {"step": "stop", "status": "completed"},
                {"step": "start", "status": "failed"},
            ],
            error_text="container failed",
        )

        self.assertEqual(operation["serviceName"], "Medplum")
        self.assertEqual(operation["action"], "restart")
        self.assertEqual(operation["operator"], "tester")
        self.assertEqual(operation["durationMs"], 1250)
        self.assertEqual(operation["progress"][1]["status"], "failed")
        self.assertEqual(operation["error"], "container failed")
        self.assertEqual(self.store.list_lab_operations(medplum["id"])[0]["id"], operation["id"])

        with self.assertRaisesRegex(SimulatorValidationError, "Unsupported lab operation action"):
            self.store.record_lab_operation(
                medplum["id"],
                service_name="Medplum",
                action="purge",
                operator="tester",
                result="failed",
            )

    def test_local_order_record_persists_orm_payload(self):
        patient = self.store.create_patient_record(
            {
                "mrn": "MRN-A04-001",
                "firstName": "Avery",
                "middleName": "Lee",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
                "patientClass": "O",
                "assignedLocation": "CARDIOLOGY^ROOM1",
                "attendingProvider": "P123^Rivera^Elena",
                "accountNumber": "",
            }
        )

        order = self.store.create_order_record(
            {
                "patientRecordId": patient["id"],
                "priority": "R",
                "requestedAt": "20260703103000",
                "orderingProvider": "1001^WANG^AMY",
                "clinicalIndication": "Chest pain evaluation",
            }
        )

        self.assertEqual(order["status"], "Ready to send")
        self.assertEqual(order["localOrderNumber"], "ORD-000001")
        self.assertEqual(order["visitId"], patient["visitNumber"])
        self.assertEqual(order["accountNumber"], "ACC-ORD-000001")
        self.assertIn("MSH|^~\\&|HEALTHCARE_LAB|DASHBOARD|OIE|HL7LAB|", order["payload"])
        self.assertIn("ORM^O01", order["payload"])
        self.assertIn("PID|1||MRN-A04-001^^^HEALTHCARE_LAB^MR", order["payload"])
        self.assertIn("PV1|1|O|CARDIOLOGY^ROOM1", order["payload"])
        self.assertIn("ORC|NW|ORD-000001", order["payload"])
        self.assertIn(
            "ECG12^12 Lead ECG^L^93000^Electrocardiogram, routine ECG with at least 12 leads^C4",
            order["payload"],
        )
        self.assertEqual(self.store.list_order_records()[0]["id"], order["id"])

    def test_local_patient_modes_generate_protocol_specific_payloads(self):
        base_payload = {
            "mrn": "MRN-MODE-001",
            "firstName": "Avery",
            "middleName": "Lee",
            "lastName": "Morgan",
            "dob": "19850412",
            "sex": "F",
            "phone": "555-0100",
            "address": "100 Main St",
        }

        fhir = self.store.create_patient_record({**base_payload, "mode": "fhir"})
        self.assertEqual(fhir["protocolVersion"], "FHIR R4")
        self.assertEqual(fhir["messageType"], "Patient")
        fhir_payload = json.loads(fhir["payload"])
        self.assertEqual(fhir_payload["resourceType"], "Patient")
        self.assertEqual(
            fhir_payload["meta"]["profile"],
            ["https://twcore.mohw.gov.tw/ig/twcore/StructureDefinition/Patient-twcore"],
        )
        self.assertEqual(fhir_payload["name"][0]["text"], "Avery Lee Morgan")
        self.assertEqual(fhir_payload["gender"], "female")

        gdt = self.store.create_patient_record({**base_payload, "mode": "gdt", "mrn": "MRN-MODE-002"})
        self.assertEqual(gdt["protocolVersion"], "GDT 2.1")
        self.assertEqual(gdt["messageType"], "6301")
        records = parse_gdt_records(gdt["payload"])
        self.assertEqual(records["8000"], "6301")
        self.assertEqual(records["8100"], f"{len(gdt['payload'].encode('cp1252')):05d}")
        self.assertEqual(records["9218"], "02.10")
        self.assertEqual(records["9206"], "3")
        self.assertEqual(records["3000"], "MRN-MODE-002")
        self.assertEqual(records["3101"], "Morgan")
        self.assertEqual(records["3102"], "Avery")
        self.assertEqual(records["3103"], "12041985")
        self.assertEqual(records["3110"], "2")

        dicom = self.store.create_patient_record({**base_payload, "mode": "dicom", "mrn": "MRN-MODE-003"})
        self.assertEqual(dicom["protocolVersion"], "DICOM")
        self.assertEqual(dicom["messageType"], "Patient Module")
        self.assertIn("(0010,0010) PatientName", dicom["payload"])
        self.assertIn("Morgan^Avery^Lee", dicom["payload"])

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
        self.assertEqual(records["6200"], "GDT-ORD-000001")
        self.assertEqual(records["6220"], "20260706110000")
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
                ("3101", "Morgan"),
                ("3102", "Avery"),
                ("6200", order["localGdtOrderNumber"]),
                ("8410", order["localGdtOrderNumber"]),
                ("6220", "Normal sinus rhythm"),
                ("6302", "reports/ecg-result.pdf"),
                ("6303", "application/pdf"),
                ("6304", "reports/ecg-waveform.xml"),
                ("6305", "application/xml"),
            ],
            set_type="6310",
        )

        result = self.store.record_gdt_result({"rawGdtText": result_payload})

        self.assertEqual(result["messageType"], "6310")
        self.assertEqual(result["matchStatus"], "order-matched")
        self.assertEqual(result["parsedFields"]["6220"], ["Normal sinus rhythm"])
        self.assertEqual(result["canonical"]["order"]["localGdtOrderNumber"], order["localGdtOrderNumber"])
        updated_order = self.store.get_gdt_order_record(order["id"])
        self.assertEqual(updated_order["status"], "Result received")
        roles = {attachment["role"] for attachment in updated_order["attachments"]}
        self.assertIn("report", roles)
        self.assertIn("waveform", roles)
        event_types = {event["eventType"] for event in updated_order["events"]}
        self.assertIn("result-imported", event_types)
        self.assertIn("result-matched", event_types)

    def test_gdt_unmatched_result_is_persisted(self):
        result_payload = render_gdt_message(
            [
                ("3000", "UNKNOWN-GDT-PAT"),
                ("8410", "UNKNOWN-ORDER"),
                ("6220", "Unmatched result"),
            ],
            set_type="6310",
        )

        result = self.store.record_gdt_result({"rawGdtText": result_payload})

        self.assertEqual(result["messageType"], "6310")
        self.assertEqual(result["matchStatus"], "unmatched")
        self.assertEqual(result["rawGdtText"], result_payload)

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

    def test_order_send_result_persists_ack_and_transport_error(self):
        patient = self.store.create_patient_record(
            {
                "mrn": "MRN-A04-002",
                "firstName": "Jordan",
                "lastName": "Case",
                "dob": "19770102",
                "sex": "M",
            }
        )
        order = self.store.create_order_record({"patientRecordId": patient["id"]})

        accepted = self.store.update_order_send_result(
            order["id"],
            order_status="Accepted",
            ack_code="AA",
            ack_control_id="ORM1",
            ack_text="OK",
            ack_payload="MSH|^~\\&|OIE|HL7LAB|HEALTHCARE_LAB|DASHBOARD||ACK^O01|ACK1|P|2.3.1\rMSA|AA|ORM1|OK",
        )
        self.assertEqual(accepted["ack"]["code"], "AA")
        self.assertEqual(accepted["status"], "Accepted")

        failed = self.store.update_order_send_result(
            order["id"],
            order_status="Transport error",
            transport_error="connection refused",
        )
        self.assertEqual(failed["status"], "Transport error")
        self.assertEqual(failed["transportError"], "connection refused")

    def test_healthcare_lab_template_excludes_ap_simulator_views(self):
        template = (
            Path(__file__).parents[1] / "frontend" / "templates" / "index.html"
        ).read_text(encoding="utf-8")

        self.assertIn('id="lab-console-view"', template)
        self.assertIn("Server Health Dashboard", template)
        self.assertNotIn('data-category-target="gdt-hospital-view"', template)
        self.assertNotIn('id="gdt-ap-view"', template)
        self.assertNotIn("GDT AP Simulator", template)
        self.assertNotIn('id="ap-gdt-order-list"', template)


if __name__ == "__main__":
    unittest.main()
