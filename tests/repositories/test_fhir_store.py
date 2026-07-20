import unittest

from ._case_support import *

class FhirStoreTests(StoreCaseSupport):
    """Focused assertion owner for FhirStoreTests."""

    def test_fhir_patient_common_fields_and_paired_ledger_metadata(self):
        patient = self.dependencies.patient_repository.create_patient_record(
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

        fhir_record = self.dependencies.patient_fhir.create_patient_fhir_workflow_record(patient)
        refreshed = self.dependencies.patient_repository.get_patient_record(patient["id"])
        self.assertEqual(fhir_record["resourceType"], "Patient")
        self.assertEqual(fhir_record["localSourceId"], str(patient["id"]))
        self.assertEqual(refreshed["fhir"]["recordId"], fhir_record["id"])
        self.assertEqual(refreshed["fhir"]["sync"]["status"], "Pending sync")
        self.assertEqual(
            refreshed["fhir"]["identifier"]["value"],
            f"local-patient-records-{patient['id']}",
        )

    def test_fhir_workflow_record_persists_status_identifier_and_resource(self):
        item = self.dependencies.fhir_ledger.create_fhir_workflow_record(
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
        self.assertEqual(self.dependencies.fhir_ledger.list_fhir_workflow_records()[0]["id"], item["id"])

        duplicate = self.dependencies.fhir_ledger.create_fhir_workflow_record(
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
        self.assertEqual(len(self.dependencies.fhir_ledger.list_fhir_workflow_records()), 1)

    def test_fhir_workflow_mapping_metadata_covers_supported_resources(self):
        mappings = {
            item["resourceType"]: item
            for item in list_fhir_resource_mappings()
        }

        self.assertEqual(
            set(mappings),
            {
                "Patient",
                "ServiceRequest",
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
        self.assertNotIn("Task", mappings)
        self.assertNotIn("Task", mappings["Provenance"]["dependsOn"])

    def test_fhir_order_builds_service_request_and_requires_synced_patient(self):
        patient = self.dependencies.patient_repository.create_patient_record(
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
            self.dependencies.order_fhir.create_fhir_order_record({"mode": "fhir", "patientRecordId": patient["id"]})

        patient_fhir = self.dependencies.patient_fhir.create_patient_fhir_workflow_record(patient)
        self.dependencies.fhir_ledger.mark_fhir_sync_success(
            patient_fhir["id"],
            medplum_resource_id="patient-1",
            medplum_resource_reference="Patient/patient-1",
        )

        order = self.dependencies.order_fhir.create_fhir_order_record(
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

        service_request = self.dependencies.order_fhir.create_order_service_request_fhir_workflow_record(order)
        self.dependencies.fhir_ledger.mark_fhir_sync_success(
            service_request["id"],
            medplum_resource_id="sr-1",
            medplum_resource_reference="ServiceRequest/sr-1",
        )

        self.assertEqual(service_request["identifier"]["value"], f"local-order-records-{order['id']}")
        refreshed = self.dependencies.order_repository.get_order_record(order["id"])
        self.assertEqual(refreshed["fhir"]["serviceRequest"]["resourceType"], "ServiceRequest")
        self.assertEqual(set(refreshed["fhir"]), {"serviceRequest"})

    def test_fhir_sync_attempts_and_failure_details_are_preserved(self):
        item = self.dependencies.fhir_ledger.create_fhir_workflow_record(
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

        syncing = self.dependencies.fhir_ledger.mark_fhir_syncing(item["id"])
        self.assertEqual(syncing["sync"]["status"], "Syncing")
        attempt = self.dependencies.fhir_ledger.record_fhir_sync_attempt(
            item["id"],
            method="POST",
            request_url="http://medplum/fhir/R4/ServiceRequest",
            request_payload=item["resource"],
            http_status=400,
            response_payload=outcome,
            operation_outcome=outcome,
            error_text="Medplum returned HTTP 400",
        )
        failed = self.dependencies.fhir_ledger.mark_fhir_sync_failure(
            item["id"],
            error_text="Medplum returned HTTP 400",
            operation_outcome=outcome,
        )

        self.assertEqual(attempt["httpStatus"], 400)
        self.assertEqual(attempt["operationOutcome"], outcome)
        self.assertEqual(failed["sync"]["status"], "Sync failed")
        self.assertEqual(failed["sync"]["operationOutcome"], outcome)
        self.assertIn("HTTP 400", failed["sync"]["error"])
        self.assertEqual(self.dependencies.fhir_ledger.list_fhir_sync_attempts(item["id"])[0]["id"], attempt["id"])

    def test_fhir_sync_success_preserves_medplum_reference_and_ordering(self):
        patient = self.dependencies.fhir_ledger.create_fhir_workflow_record(
            {
                "localSourceType": "local_patient_records",
                "localSourceId": "1",
                "resource": {"resourceType": "Patient"},
            }
        )
        report = self.dependencies.fhir_ledger.create_fhir_workflow_record(
            {
                "localSourceType": "local_fhir_results",
                "localSourceId": "99",
                "resource": {"resourceType": "DiagnosticReport", "status": "final"},
            }
        )

        synced = self.dependencies.fhir_ledger.mark_fhir_sync_success(
            patient["id"],
            medplum_resource_id="patient-medplum-id",
        )
        ordered = self.dependencies.fhir_ledger.ordered_fhir_workflow_records([report["id"], patient["id"]])

        self.assertEqual(synced["sync"]["status"], "Synced")
        self.assertEqual(synced["medplum"]["id"], "patient-medplum-id")
        self.assertEqual(synced["medplum"]["reference"], "Patient/patient-medplum-id")
        self.assertEqual([item["resourceType"] for item in ordered], ["Patient", "DiagnosticReport"])

    def test_fhir_synced_record_update_marks_changed_payload_pending(self):
        item = self.dependencies.fhir_ledger.create_fhir_workflow_record(
            {
                "localSourceType": "local_patient_records",
                "localSourceId": "1",
                "resource": {"resourceType": "Patient", "active": True},
            }
        )
        synced = self.dependencies.fhir_ledger.mark_fhir_sync_success(
            item["id"],
            medplum_resource_id="patient-medplum-id",
        )

        unchanged = self.dependencies.fhir_ledger.create_fhir_workflow_record(
            {
                "localSourceType": "local_patient_records",
                "localSourceId": "1",
                "resource": {"resourceType": "Patient", "active": True},
            }
        )
        changed = self.dependencies.fhir_ledger.create_fhir_workflow_record(
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


if __name__ == "__main__":
    unittest.main()
