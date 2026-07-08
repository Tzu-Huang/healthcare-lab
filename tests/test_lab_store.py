import tempfile
import unittest
import json
from pathlib import Path

from backend.lab_store import (
    DCM4CHEE_MWL_STATUS_CREATED,
    DemoStore,
    SimulatorValidationError,
    render_gdt_message,
)


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

    def test_dcm4chee_mapping_backfills_from_existing_attempts(self):
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
        profile = {
            "profileName": "local-dcm4chee",
            "dimse": {"calledAETitle": "DCM4CHEE"},
            "mwl": {"aeTitle": "DCM4CHEE", "defaultScheduledStationAETitle": "ECG_AP"},
        }
        order = self.store.create_dcm4chee_order_record(
            {"patientRecordId": patient["id"], "requestedAt": "20260708103000"}
        )
        payload = self.store.build_dcm4chee_mwl_payload(order, profile)
        attempt = self.store.create_dcm4chee_mwl_attempt(
            int(order["id"]),
            profile,
            request_payload=payload,
            attempt_status=DCM4CHEE_MWL_STATUS_CREATED,
            http_status=200,
            response_body='{"created":true}',
        )
        with self.store.connect() as connection:
            connection.execute("DELETE FROM local_dcm4chee_mwl_mappings")
            connection.execute("UPDATE local_dcm4chee_mwl_attempts SET mapping_id = NULL")

        reopened = DemoStore(self.store.path)
        mapping = reopened.get_dcm4chee_mwl_mapping_for_order(int(order["id"]))
        attempts = reopened.list_dcm4chee_mwl_attempts(int(order["id"]))

        self.assertIsNotNone(mapping)
        self.assertEqual(mapping["status"], DCM4CHEE_MWL_STATUS_CREATED)
        self.assertEqual(mapping["lastAttemptId"], attempt["id"])
        self.assertEqual(mapping["accessionNumber"], "ACC-000001")
        self.assertEqual(mapping["patientId"], "MRN-A04-001")
        self.assertEqual(attempts[0]["mappingId"], mapping["id"])
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
        self.assertTrue(fhir_payload["active"])

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

    def test_fhir_patient_common_fields_and_paired_ledger_metadata(self):
        patient = self.store.create_patient_record(
            {
                "mode": "fhir",
                "mrn": "MRN-FHIR-001",
                "firstName": "Avery",
                "middleName": "Lee",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
                "phone": "555-0100",
                "email": "avery@example.org",
                "active": False,
                "address": "100 Main St, Boston, MA 02110",
                "addressLine": "100 Main St",
                "addressCity": "Boston",
                "addressState": "MA",
                "addressPostalCode": "02110",
                "addressCountry": "US",
                "managingOrganizationReference": "Organization/healthcare-lab",
                "managingOrganizationDisplay": "Healthcare Lab",
            }
        )

        resource = json.loads(patient["payload"])
        self.assertFalse(resource["active"])
        self.assertEqual(
            resource["telecom"],
            [
                {"system": "phone", "value": "555-0100"},
                {"system": "email", "value": "avery@example.org"},
            ],
        )
        self.assertEqual(resource["address"][0]["line"], ["100 Main St"])
        self.assertEqual(resource["address"][0]["city"], "Boston")
        self.assertEqual(resource["address"][0]["postalCode"], "02110")
        self.assertEqual(
            resource["managingOrganization"],
            {
                "reference": "Organization/healthcare-lab",
                "display": "Healthcare Lab",
            },
        )

        fhir_record = self.store.create_patient_fhir_workflow_record(patient)
        refreshed = self.store.get_patient_record(patient["id"])
        self.assertEqual(fhir_record["resourceType"], "Patient")
        self.assertEqual(fhir_record["localSourceId"], str(patient["id"]))
        self.assertEqual(refreshed["fhir"]["recordId"], fhir_record["id"])
        self.assertEqual(refreshed["fhir"]["sync"]["status"], "Pending sync")
        self.assertEqual(
            refreshed["fhir"]["identifier"]["value"],
            f"local-patient-records-{patient['id']}",
        )

    def test_fhir_workflow_record_persists_status_identifier_and_resource(self):
        item = self.store.create_fhir_workflow_record(
            {
                "localSourceType": "local_patient_records",
                "localSourceId": "1",
                "resource": {
                    "resourceType": "Patient",
                    "name": [{"text": "Avery Morgan"}],
                },
            }
        )

        self.assertEqual(item["localFhirRecordNumber"], "FHIR-000001")
        self.assertEqual(item["resourceType"], "Patient")
        self.assertEqual(item["sync"]["status"], "Pending sync")
        self.assertEqual(
            item["identifier"]["system"],
            "https://healthcare-lab.local/fhir/identifier/patient",
        )
        self.assertEqual(item["identifier"]["value"], "local-patient-records-1")
        self.assertEqual(
            item["resource"]["identifier"][0],
            {
                "system": "https://healthcare-lab.local/fhir/identifier/patient",
                "value": "local-patient-records-1",
            },
        )
        self.assertEqual(self.store.list_fhir_workflow_records()[0]["id"], item["id"])

        duplicate = self.store.create_fhir_workflow_record(
            {
                "localSourceType": "local_patient_records",
                "localSourceId": "1",
                "resource": {
                    "resourceType": "Patient",
                    "active": True,
                },
            }
        )
        self.assertEqual(duplicate["id"], item["id"])
        self.assertTrue(duplicate["resource"]["active"])
        self.assertEqual(len(self.store.list_fhir_workflow_records()), 1)

    def test_fhir_workflow_mapping_metadata_covers_supported_resources(self):
        mappings = {
            item["resourceType"]: item
            for item in self.store.list_fhir_resource_mappings()
        }

        self.assertEqual(
            set(mappings),
            {
                "Patient",
                "ServiceRequest",
                "Task",
                "Binary",
                "Observation",
                "DocumentReference",
                "DiagnosticReport",
                "Provenance",
            },
        )
        self.assertEqual(mappings["Patient"]["dependsOn"], [])
        self.assertIn("Patient", mappings["ServiceRequest"]["dependsOn"])
        self.assertIn("DocumentReference", mappings["DiagnosticReport"]["dependsOn"])
        self.assertIn("DiagnosticReport", mappings["Provenance"]["dependsOn"])

    def test_fhir_order_builds_service_request_task_and_requires_synced_patient(self):
        patient = self.store.create_patient_record(
            {
                "mode": "fhir",
                "mrn": "MRN-FHIR-ORDER-001",
                "firstName": "Avery",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
            }
        )

        with self.assertRaisesRegex(SimulatorValidationError, "synced Medplum Patient"):
            self.store.create_fhir_order_record({"mode": "fhir", "patientRecordId": patient["id"]})

        patient_fhir = self.store.create_patient_fhir_workflow_record(patient)
        self.store.mark_fhir_sync_success(
            patient_fhir["id"],
            medplum_resource_id="patient-1",
            medplum_resource_reference="Patient/patient-1",
        )

        order = self.store.create_fhir_order_record(
            {
                "mode": "fhir",
                "patientRecordId": patient["id"],
                "fhir": {
                    "status": "active",
                    "intent": "order",
                    "priority": "stat",
                    "codeCode": "ECG12",
                    "codeDisplay": "12 Lead ECG",
                    "occurrenceDateTime": "2026-07-08T10:30",
                    "authoredOn": "2026-07-08T09:00",
                    "requester": "Practitioner/prac-1",
                    "reasonCodeText": "Chest pain evaluation",
                    "note": "Internal note",
                },
            }
        )

        self.assertEqual(order["protocolVersion"], "FHIR R4")
        self.assertEqual(order["messageType"], "ServiceRequest")
        resource = json.loads(order["payload"])
        self.assertEqual(resource["resourceType"], "ServiceRequest")
        self.assertEqual(resource["subject"]["reference"], "Patient/patient-1")
        self.assertEqual(resource["status"], "active")
        self.assertEqual(resource["intent"], "order")
        self.assertEqual(resource["priority"], "stat")
        self.assertRegex(resource["occurrenceDateTime"], r"^2026-07-08T10:30:00[+-]\d{2}:\d{2}$")
        self.assertRegex(resource["authoredOn"], r"^2026-07-08T09:00:00[+-]\d{2}:\d{2}$")
        self.assertEqual(resource["requester"]["reference"], "Practitioner/prac-1")
        self.assertEqual(resource["reasonCode"][0]["text"], "Chest pain evaluation")
        self.assertEqual(resource["note"][0]["text"], "Internal note")

        service_request = self.store.create_order_service_request_fhir_workflow_record(order)
        self.store.mark_fhir_sync_success(
            service_request["id"],
            medplum_resource_id="sr-1",
            medplum_resource_reference="ServiceRequest/sr-1",
        )
        task = self.store.create_order_task_fhir_workflow_record(
            order,
            patient_reference="Patient/patient-1",
            service_request_reference="ServiceRequest/sr-1",
        )

        self.assertEqual(service_request["identifier"]["value"], f"local-order-records-{order['id']}")
        self.assertEqual(task["identifier"]["value"], f"local-order-records-{order['id']}")
        self.assertEqual(task["resource"]["status"], "requested")
        self.assertEqual(task["resource"]["intent"], "order")
        self.assertEqual(task["resource"]["for"]["reference"], "Patient/patient-1")
        self.assertEqual(task["resource"]["focus"]["reference"], "ServiceRequest/sr-1")
        refreshed = self.store.get_order_record(order["id"])
        self.assertEqual(refreshed["fhir"]["serviceRequest"]["resourceType"], "ServiceRequest")
        self.assertEqual(refreshed["fhir"]["task"]["resourceType"], "Task")

    def test_fhir_sync_attempts_and_failure_details_are_preserved(self):
        item = self.store.create_fhir_workflow_record(
            {
                "localSourceType": "local_order_records",
                "localSourceId": "42",
                "resource": {
                    "resourceType": "ServiceRequest",
                    "status": "active",
                    "intent": "order",
                },
            }
        )
        outcome = {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "error", "diagnostics": "subject missing"}],
        }

        syncing = self.store.mark_fhir_syncing(item["id"])
        self.assertEqual(syncing["sync"]["status"], "Syncing")
        attempt = self.store.record_fhir_sync_attempt(
            item["id"],
            method="POST",
            request_url="http://medplum/fhir/R4/ServiceRequest",
            request_payload=item["resource"],
            http_status=400,
            response_payload=outcome,
            operation_outcome=outcome,
            error_text="Medplum returned HTTP 400",
        )
        failed = self.store.mark_fhir_sync_failure(
            item["id"],
            error_text="Medplum returned HTTP 400",
            operation_outcome=outcome,
        )

        self.assertEqual(attempt["httpStatus"], 400)
        self.assertEqual(attempt["operationOutcome"], outcome)
        self.assertEqual(failed["sync"]["status"], "Sync failed")
        self.assertEqual(failed["sync"]["operationOutcome"], outcome)
        self.assertIn("HTTP 400", failed["sync"]["error"])
        self.assertEqual(self.store.list_fhir_sync_attempts(item["id"])[0]["id"], attempt["id"])

    def test_fhir_sync_success_preserves_medplum_reference_and_ordering(self):
        patient = self.store.create_fhir_workflow_record(
            {
                "localSourceType": "local_patient_records",
                "localSourceId": "1",
                "resource": {"resourceType": "Patient"},
            }
        )
        report = self.store.create_fhir_workflow_record(
            {
                "localSourceType": "local_fhir_results",
                "localSourceId": "99",
                "resource": {"resourceType": "DiagnosticReport", "status": "final"},
            }
        )

        synced = self.store.mark_fhir_sync_success(
            patient["id"],
            medplum_resource_id="patient-medplum-id",
        )
        ordered = self.store.ordered_fhir_workflow_records([report["id"], patient["id"]])

        self.assertEqual(synced["sync"]["status"], "Synced")
        self.assertEqual(synced["medplum"]["id"], "patient-medplum-id")
        self.assertEqual(synced["medplum"]["reference"], "Patient/patient-medplum-id")
        self.assertEqual([item["resourceType"] for item in ordered], ["Patient", "DiagnosticReport"])

    def test_fhir_synced_record_update_marks_changed_payload_pending(self):
        item = self.store.create_fhir_workflow_record(
            {
                "localSourceType": "local_patient_records",
                "localSourceId": "1",
                "resource": {"resourceType": "Patient", "active": True},
            }
        )
        synced = self.store.mark_fhir_sync_success(
            item["id"],
            medplum_resource_id="patient-medplum-id",
        )

        unchanged = self.store.create_fhir_workflow_record(
            {
                "localSourceType": "local_patient_records",
                "localSourceId": "1",
                "resource": {"resourceType": "Patient", "active": True},
            }
        )
        changed = self.store.create_fhir_workflow_record(
            {
                "localSourceType": "local_patient_records",
                "localSourceId": "1",
                "resource": {"resourceType": "Patient", "active": False},
            }
        )

        self.assertEqual(synced["sync"]["status"], "Synced")
        self.assertEqual(unchanged["sync"]["status"], "Synced")
        self.assertEqual(changed["sync"]["status"], "Pending sync")
        self.assertFalse(changed["resource"]["active"])
        self.assertEqual(changed["medplum"]["reference"], "Patient/patient-medplum-id")

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
                ("8402", "EKG01"),
                ("3101", "Morgan"),
                ("3102", "Avery"),
                ("6200", order["localGdtOrderNumber"]),
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
