import unittest

from ._case_support import *

class PatientOrderStoreTests(StoreCaseSupport):
    """Focused assertion owner for PatientOrderStoreTests."""

    def test_patient_mrn_sequence_allocates_persists_and_does_not_reuse_deleted_values(self):
        first = self.dependencies.patient_repository.create_patient_record(self.patient_payload())
        second = self.dependencies.patient_repository.create_patient_record(self.patient_payload(firstName="Blake"))

        self.assertEqual(first["summary"]["mrn"], "MRN-000001")
        self.assertEqual(second["summary"]["mrn"], "MRN-000002")

        with self.dependencies.database.connect() as connection:
            connection.execute("DELETE FROM local_patient_records WHERE id = ?", (second["id"],))

        reopened = assemble_application_dependencies(self.dependencies.database.path)
        third = reopened.patient_repository.create_patient_record(self.patient_payload(firstName="Casey"))

        self.assertEqual(third["summary"]["mrn"], "MRN-000003")

    def test_patient_mrn_sequence_skips_explicit_collision(self):
        manual = self.dependencies.patient_repository.create_patient_record(
            self.patient_payload(mrn="MRN-000001", firstName="Manual")
        )
        generated = self.dependencies.patient_repository.create_patient_record(self.patient_payload(firstName="Generated"))

        self.assertEqual(manual["summary"]["mrn"], "MRN-000001")
        self.assertEqual(generated["summary"]["mrn"], "MRN-000002")

    def test_duplicate_explicit_mrn_is_rejected_without_patient_side_effects(self):
        created = self.dependencies.patient_repository.create_patient_record(self.patient_payload(mrn="mrn-000101"))

        with self.assertRaisesRegex(
            SimulatorValidationError,
            "Patient MRN MRN-000101 already exists",
        ):
            self.dependencies.patient_repository.create_patient_record(
                self.patient_payload(mrn=" MRN-000101 ", firstName="Duplicate")
            )

        records = self.dependencies.patient_repository.list_patient_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["id"], created["id"])
        with self.dependencies.database.connect() as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM local_fhir_workflow_records").fetchone()[0],
                0,
            )

    def test_noncanonical_explicit_mrn_is_rejected_without_side_effects(self):
        with self.assertRaisesRegex(SimulatorValidationError, "canonical format"):
            self.dependencies.patient_repository.create_patient_record(
                self.patient_payload(mrn="EXTERNAL-001")
            )

        self.assertEqual(self.dependencies.patient_repository.list_patient_records(), [])

    def test_database_enforces_normalized_mrn_uniqueness(self):
        self.dependencies.patient_repository.create_patient_record(
            self.patient_payload(mrn="MRN-000102")
        )
        other = self.dependencies.patient_repository.create_patient_record(
            self.patient_payload(mrn="MRN-000103", firstName="Other")
        )
        with self.dependencies.database.connect() as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE local_patient_records SET mrn = ? WHERE id = ?",
                    (" mrn-000102 ", other["id"]),
                )

        self.assertEqual(len(self.dependencies.patient_repository.list_patient_records()), 2)

    def test_patient_protocol_filter_and_workbenches_keep_protocol_boundaries(self):
        hl7_patient = self.dependencies.patient_repository.create_patient_record(
            self.patient_payload(mrn="MRN-000201", mode="hl7-v2")
        )
        self.dependencies.patient_repository.create_patient_record(self.patient_payload(mrn="MRN-000202", mode="fhir"))
        gdt_patient = self.dependencies.patient_repository.create_patient_record(
            self.patient_payload(mrn="MRN-000203", mode="gdt")
        )
        self.dependencies.patient_repository.create_patient_record(self.patient_payload(mrn="MRN-000204", mode="dicom"))

        self.assertEqual(
            [item["id"] for item in self.dependencies.patient_repository.list_patient_records("HL7 v2.5.1")],
            [hl7_patient["id"]],
        )
        self.assertEqual(
            [item["id"] for item in self.oie_coordination.list_oie_local_adt_inventory()],
            [hl7_patient["id"]],
        )
        self.assertEqual(
            [item["id"] for item in self.oie_workbench()["patients"]],
            [hl7_patient["id"]],
        )
        self.assertEqual(
            [item["id"] for item in self.dependencies.gdt_workflow.list_gdt_workbench()["patients"]],
            [gdt_patient["id"]],
        )

    def test_local_order_record_persists_orm_payload(self):
        patient = self.dependencies.patient_repository.create_patient_record(
            {
                "mrn": "MRN-000301",
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

        order = self.dependencies.order_repository.create_order_record(
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
        self.assertEqual(order["visitNumber"], patient["visitNumber"])
        self.assertEqual(order["visitId"], patient["visitNumber"])
        self.assertEqual(order["summary"]["visitNumber"], patient["visitNumber"])
        self.assertEqual(order["summary"]["visitId"], patient["visitNumber"])
        self.assertEqual(order["accountNumber"], "ACC-ORD-000001")
        self.assertIn("MSH|^~\\&|HEALTHCARE_LAB|DASHBOARD|OIE|HL7LAB|", order["payload"])
        self.assertIn("ORM^O01^ORM_O01", order["payload"])
        self.assertIn("|P|2.5.1||||||UNICODE UTF-8", order["payload"])
        self.assertIn("PID|1||MRN-000301^^^HEALTHCARE_LAB^MR", order["payload"])
        self.assertIn("PV1|1|O|CARDIOLOGY^ROOM1", order["payload"])
        self.assertIn("ORC|NW|ORD-000001", order["payload"])
        self.assertIn(
            "ECG12^12 Lead ECG^L^93000^Electrocardiogram, routine ECG with at least 12 leads^C4",
            order["payload"],
        )

    def test_local_patient_modes_generate_protocol_specific_payloads(self):
        base_payload = {
            "mrn": "MRN-000401",
            "firstName": "Avery",
            "middleName": "Lee",
            "lastName": "Morgan",
            "dob": "19850412",
            "sex": "F",
            "phone": "555-0100",
            "address": "100 Main St",
        }

        fhir = self.dependencies.patient_repository.create_patient_record({**base_payload, "mode": "fhir"})
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

        gdt = self.dependencies.patient_repository.create_patient_record({**base_payload, "mode": "gdt", "mrn": "MRN-000402"})
        self.assertEqual(gdt["protocolVersion"], "GDT 2.1")
        self.assertEqual(gdt["messageType"], "6301")
        records = parse_gdt_records(gdt["payload"])
        self.assertEqual(records["8000"], "6301")
        self.assertEqual(records["8100"], f"{len(gdt['payload'].encode('cp1252')):05d}")
        self.assertEqual(records["9218"], "02.10")
        self.assertEqual(records["9206"], "3")
        self.assertEqual(records["3000"], "MRN-000402")
        self.assertEqual(records["3101"], "Morgan")
        self.assertEqual(records["3102"], "Avery")
        self.assertEqual(records["3103"], "12041985")
        self.assertEqual(records["3110"], "2")

        dicom = self.dependencies.patient_repository.create_patient_record({**base_payload, "mode": "dicom", "mrn": "MRN-000403"})
        self.assertEqual(dicom["protocolVersion"], "DICOM")
        self.assertEqual(dicom["messageType"], "Patient Module")
        self.assertIn("(0010,0010) PatientName", dicom["payload"])
        self.assertIn("Morgan^Avery^Lee", dicom["payload"])

    def test_generated_mrn_propagates_across_patient_modes_and_into_order_snapshot(self):
        base_payload = {
            "firstName": "Avery",
            "lastName": "Morgan",
            "dob": "19850412",
            "sex": "F",
        }

        hl7 = self.dependencies.patient_repository.create_patient_record({**base_payload, "mode": "hl7-v2"})
        fhir = self.dependencies.patient_repository.create_patient_record({**base_payload, "mode": "fhir"})
        gdt = self.dependencies.patient_repository.create_patient_record({**base_payload, "mode": "gdt"})
        dicom = self.dependencies.patient_repository.create_patient_record({**base_payload, "mode": "dicom"})

        self.assertIn("PID|1||MRN-000001^^^HEALTHCARE_LAB^MR", hl7["payload"])
        self.assertEqual(json.loads(fhir["payload"])["identifier"][0]["value"], "MRN-000002")
        self.assertEqual(parse_gdt_records(gdt["payload"])["3000"], "MRN-000003")
        self.assertEqual(json.loads(dicom["payload"])["(0010,0020) PatientID"], "MRN-000004")

        order = self.dependencies.order_repository.create_order_record(
            {
                "patientRecordId": hl7["id"],
                "requestedAt": "20260713143000",
                "orderingProvider": "1001^WANG^AMY",
            }
        )

        self.assertEqual(order["summary"]["mrn"], "MRN-000001")
        self.assertIn("PID|1||MRN-000001^^^HEALTHCARE_LAB^MR", order["payload"])


if __name__ == "__main__":
    unittest.main()
