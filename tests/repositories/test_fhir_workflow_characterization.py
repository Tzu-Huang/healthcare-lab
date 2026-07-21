import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.domain.errors import SimulatorValidationError
from backend.application_composition import assemble_application_dependencies
from backend.services.coordination import OrderFhirOperations
from backend.services.order_workflow import OrderWorkflowService


class FhirWorkflowCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.temporary_root = Path(self.directory.name).resolve()
        self.database_path = (self.temporary_root / "fhir-characterization.db").resolve()
        repository_root = Path(__file__).resolve().parents[2]

        self.assertTrue(self.database_path.is_relative_to(self.temporary_root))
        self.assertFalse(self.database_path.is_relative_to(repository_root / "instance"))
        self.assertFalse(self.database_path.is_relative_to(repository_root))

        self.dependencies = assemble_application_dependencies(self.database_path)

    def tearDown(self):
        self.directory.cleanup()

    @staticmethod
    def patient(*, mode="fhir", mrn="MRN-200001"):
        return {
            "mode": mode,
            "mrn": mrn,
            "firstName": "Avery",
            "lastName": "Morgan",
            "dob": "19850412",
            "sex": "F",
        }

    def create_synced_patient(self):
        patient = self.dependencies.patient_repository.create_patient_record(self.patient())
        record = self.dependencies.patient_fhir.create_patient_fhir_workflow_record(patient)
        self.dependencies.fhir_ledger.mark_fhir_sync_success(
            record["id"],
            medplum_resource_id="patient-characterization",
            medplum_resource_reference="Patient/patient-characterization",
        )
        return patient, record

    def service_request_count(self):
        with self.dependencies.database.connect() as connection:
            return connection.execute(
                "SELECT COUNT(*) FROM local_fhir_workflow_records WHERE resource_type = 'ServiceRequest'"
            ).fetchone()[0]

    def test_dependency_only_change_requeues_and_clears_stale_sync_details(self):
        item = self.dependencies.fhir_ledger.create_fhir_workflow_record(
            {
                "localSourceType": "local_patient_records",
                "localSourceId": "17",
                "resource": {"resourceType": "Patient", "active": True},
                "dependencies": [],
            }
        )
        self.dependencies.fhir_ledger.mark_fhir_sync_success(
            item["id"],
            medplum_resource_id="patient-17",
            medplum_resource_reference="Patient/patient-17",
        )
        outcome = {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "error", "diagnostics": "stale dependency"}],
        }
        self.dependencies.fhir_ledger.mark_fhir_sync_failure(
            item["id"], error_text="stale sync error", operation_outcome=outcome
        )
        with self.dependencies.database.connect() as connection:
            connection.execute(
                "UPDATE local_fhir_workflow_records SET sync_started_at = ? WHERE id = ?",
                ("2026-07-16T01:02:03+00:00", item["id"]),
            )

        changed = self.dependencies.fhir_ledger.create_fhir_workflow_record(
            {
                "localSourceType": "local_patient_records",
                "localSourceId": "17",
                "resource": {"resourceType": "Patient", "active": True},
                "dependencies": ["Organization"],
            }
        )

        self.assertEqual(changed["id"], item["id"])
        self.assertEqual(changed["resource"], item["resource"])
        self.assertEqual(changed["dependencies"], ["Organization"])
        self.assertEqual(changed["sync"]["status"], "Pending sync")
        self.assertEqual(changed["sync"]["error"], "")
        self.assertEqual(changed["sync"]["operationOutcome"], {})
        self.assertEqual(changed["sync"]["syncStartedAt"], "")
        self.assertEqual(changed["medplum"]["id"], "patient-17")
        self.assertEqual(changed["medplum"]["reference"], "Patient/patient-17")

    def test_multiple_sync_attempts_preserve_complete_payloads_newest_first(self):
        record = self.dependencies.fhir_ledger.create_fhir_workflow_record(
            {
                "localSourceType": "local_order_records",
                "localSourceId": "23",
                "resource": {
                    "resourceType": "ServiceRequest",
                    "status": "active",
                    "intent": "order",
                },
            }
        )
        first_outcome = {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "error", "diagnostics": "patient missing"}],
        }
        first = self.dependencies.fhir_ledger.record_fhir_sync_attempt(
            record["id"],
            method="post",
            request_url="https://example.invalid/fhir/R4/ServiceRequest",
            request_payload={"resourceType": "ServiceRequest", "subject": {}},
            http_status=400,
            response_payload={"received": False, "outcome": first_outcome},
            operation_outcome=first_outcome,
            error_text="HTTP 400",
        )
        second = self.dependencies.fhir_ledger.record_fhir_sync_attempt(
            record["id"],
            method="put",
            request_url="https://example.invalid/fhir/R4/ServiceRequest/sr-23",
            request_payload={"resourceType": "ServiceRequest", "id": "sr-23"},
            http_status=200,
            response_payload={"resourceType": "ServiceRequest", "id": "sr-23"},
            operation_outcome={},
            error_text="",
        )

        attempts = self.dependencies.fhir_ledger.list_fhir_sync_attempts(record["id"])

        self.assertEqual([attempt["id"] for attempt in attempts], [second["id"], first["id"]])
        self.assertEqual(attempts[0], second)
        self.assertEqual(attempts[1], first)
        self.assertEqual(attempts[1]["method"], "POST")
        self.assertEqual(attempts[1]["requestPayload"]["subject"], {})
        self.assertEqual(attempts[1]["responsePayload"]["outcome"], first_outcome)
        self.assertEqual(attempts[1]["operationOutcome"], first_outcome)
        self.assertEqual(attempts[1]["error"], "HTTP 400")

    def test_unsynced_or_wrong_protocol_patient_creates_no_order_or_service_request(self):
        unsynced = self.dependencies.patient_repository.create_patient_record(self.patient(mrn="MRN-200002"))
        with self.assertRaisesRegex(SimulatorValidationError, "synced Medplum Patient"):
            self.dependencies.order_fhir.create_fhir_order_record(
                {"mode": "fhir", "patientRecordId": unsynced["id"]}
            )
        self.assertEqual(self.dependencies.order_repository.list_order_records(), [])
        self.assertEqual(self.service_request_count(), 0)

        wrong_protocol = self.dependencies.patient_repository.create_patient_record(
            self.patient(mode="hl7-v2", mrn="MRN-200003")
        )
        with self.assertRaisesRegex(SimulatorValidationError, "synced Medplum Patient"):
            self.dependencies.order_fhir.create_fhir_order_record(
                {"mode": "fhir", "patientRecordId": wrong_protocol["id"]}
            )
        self.assertEqual(self.dependencies.order_repository.list_order_records(), [])
        self.assertEqual(self.service_request_count(), 0)

    def test_fhir_order_sync_failure_preserves_one_order_and_one_submitted_resource(self):
        patient, _ = self.create_synced_patient()
        fhir_capability = OrderFhirOperations(
            self.dependencies.order_fhir.create_fhir_order_record,
            self.dependencies.order_fhir.create_order_service_request_fhir_workflow_record,
            self.dependencies.fhir_ledger.mark_fhir_sync_failure,
        )
        service = OrderWorkflowService(
            self.dependencies.order_repository,
            {},
            fhir_capability=fhir_capability,
            dcm_order_capability=Mock(),
            evidence_capability=Mock(),
            medplum_base_url=lambda: "",
            auth_manager=lambda: None,
            fhir_sync=lambda *args, **kwargs: self.fail("network sync must not be called"),
            dcm_sync=lambda *args, **kwargs: None,
            dcm_verify=lambda *args, **kwargs: {},
            dcm_profile=lambda configuration: {},
        )

        created = service.create(
            {
                "mode": "fhir",
                "patientRecordId": patient["id"],
                "fhir": {"codeCode": "ECG12", "codeDisplay": "12 Lead ECG"},
            }
        )

        orders = self.dependencies.order_repository.list_order_records("FHIR R4")
        submitted = [
            item
            for item in self.dependencies.fhir_ledger.list_fhir_workflow_records()
            if item["resourceType"] == "ServiceRequest"
        ]
        self.assertEqual([item["id"] for item in orders], [created["id"]])
        self.assertEqual(len(submitted), 1)
        self.assertEqual(submitted[0]["localSourceId"], str(created["id"]))
        self.assertEqual(submitted[0]["id"], created["fhir"]["serviceRequest"]["id"])
        self.assertEqual(submitted[0]["resource"], json.loads(created["payload"]))
        self.assertEqual(submitted[0]["sync"]["status"], "Sync failed")
        self.assertEqual(
            submitted[0]["sync"]["error"], "Medplum FHIR base URL is required."
        )

    def test_fhir_ledger_numbering_failure_rolls_back_new_record(self):
        with patch(
            "backend.repositories.fhir_ledger.record_number",
            side_effect=RuntimeError("numbering failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "numbering failed"):
                self.dependencies.fhir_ledger.create_fhir_workflow_record(
                    {
                        "localSourceType": "local_patient_records",
                        "localSourceId": "rollback-patient",
                        "resource": {"resourceType": "Patient", "active": True},
                    }
                )

        self.assertEqual(self.dependencies.fhir_ledger.list_fhir_workflow_records(), [])

    def test_service_request_builder_failure_rolls_back_local_order(self):
        patient, _ = self.create_synced_patient()
        with patch.object(
            self.dependencies.order_fhir,
            "_build_resource",
            side_effect=RuntimeError("service request build failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "service request build failed"):
                self.dependencies.order_fhir.create_fhir_order_record(
                    {"mode": "fhir", "patientRecordId": patient["id"]}
                )

        self.assertEqual(self.dependencies.order_repository.list_order_records("FHIR R4"), [])
        self.assertFalse(
            any(
                item["resourceType"] == "ServiceRequest"
                for item in self.dependencies.fhir_ledger.list_fhir_workflow_records()
            )
        )


if __name__ == "__main__":
    unittest.main()
