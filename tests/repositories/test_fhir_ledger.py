import tempfile
import unittest
from pathlib import Path

from backend.lab_store import DemoStore
from backend.repositories.fhir_ledger import FhirLedgerRepository


class FhirLedgerRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = DemoStore(Path(self.directory.name) / "fhir-ledger.db")
        self.clock = iter(f"2026-07-16T00:00:{value:02d}+00:00" for value in range(60))
        self.repository = FhirLedgerRepository(
            self.store.database.connect, self.store.database.lock,
            timestamp_factory=lambda: next(self.clock),
        )

    def tearDown(self):
        self.directory.cleanup()

    @staticmethod
    def payload(source_id="1", active=True, **extra):
        return {
            "localSourceType": "local_patient_records", "localSourceId": source_id,
            "resource": {"resourceType": "Patient", "active": active}, **extra,
        }

    def test_upsert_idempotency_changed_payload_requeue_and_identifier_lookup(self):
        created = self.repository.create_fhir_workflow_record(self.payload())
        self.repository.mark_fhir_syncing(created["id"])
        outcome = {"resourceType": "OperationOutcome", "issue": [{"diagnostics": "bad"}]}
        self.repository.mark_fhir_sync_failure(created["id"], error_text="bad", operation_outcome=outcome)
        unchanged = self.repository.create_fhir_workflow_record(self.payload())
        self.assertEqual("Sync failed", unchanged["sync"]["status"])
        changed = self.repository.create_fhir_workflow_record(self.payload(active=False))
        self.assertEqual(created["id"], changed["id"])
        self.assertEqual("Pending sync", changed["sync"]["status"])
        self.assertEqual("", changed["sync"]["error"])
        self.assertEqual({}, changed["sync"]["operationOutcome"])
        self.assertEqual("", changed["sync"]["syncStartedAt"])
        found = self.repository.get_fhir_workflow_record_by_identifier(
            resource_type="Patient", identifier_system=changed["identifier"]["system"],
            identifier_value=changed["identifier"]["value"],
        )
        self.assertEqual(created["id"], found["id"])
        self.assertEqual("FHIR-000001", found["localFhirRecordNumber"])

    def test_state_transitions_attempt_audit_and_missing_records(self):
        item = self.repository.create_fhir_workflow_record(self.payload())
        syncing = self.repository.mark_fhir_syncing(item["id"])
        self.assertEqual("Syncing", syncing["sync"]["status"])
        outcome = {"resourceType": "OperationOutcome"}
        first = self.repository.record_fhir_sync_attempt(
            item["id"], method=" post ", request_url=" http://medplum/Patient ",
            request_payload={"b": 2, "a": 1}, http_status=400,
            response_payload=outcome, operation_outcome=outcome, error_text=" bad ",
        )
        second = self.repository.record_fhir_sync_attempt(
            item["id"], method="put", request_url="http://medplum/Patient/1",
        )
        attempts = self.repository.list_fhir_sync_attempts(item["id"])
        self.assertEqual([second["id"], first["id"]], [attempt["id"] for attempt in attempts])
        self.assertEqual(("POST", "http://medplum/Patient", {"a": 1, "b": 2}),
                         (first["method"], first["requestUrl"], first["requestPayload"]))
        synced = self.repository.mark_fhir_sync_success(item["id"], medplum_resource_id="patient-1")
        self.assertEqual("Patient/patient-1", synced["medplum"]["reference"])
        self.assertFalse(synced["localOnly"])
        for operation in (
            lambda: self.repository.get_fhir_workflow_record(999),
            lambda: self.repository.mark_fhir_syncing(999),
            lambda: self.repository.record_fhir_sync_attempt(999, method="GET", request_url="x"),
        ):
            with self.assertRaises(KeyError):
                operation()

    def test_dependency_order_batch_enrichment_and_filtering(self):
        patient = self.repository.create_fhir_workflow_record(self.payload(source_id="7"))
        order = self.repository.create_fhir_workflow_record({
            "localSourceId": "8", "resource": {"resourceType": "ServiceRequest"},
        })
        report = self.repository.create_fhir_workflow_record({
            "localSourceId": "9", "resource": {"resourceType": "DiagnosticReport"},
        })
        ordered = self.repository.ordered_fhir_workflow_records([report["id"], order["id"], patient["id"]])
        self.assertEqual(["Patient", "ServiceRequest", "DiagnosticReport"], [item["resourceType"] for item in ordered])
        self.assertEqual(patient["id"], self.repository.load_for_patients([7, 999])[7]["id"])
        orders = self.repository.load_for_orders([8, 999])
        self.assertEqual(order["id"], orders[8]["ServiceRequest"]["id"])
        self.assertEqual({}, orders[999])
        self.assertEqual([], self.repository.list_fhir_workflow_records("Synced"))
        self.assertEqual({}, self.repository.load_for_patients([]))

    def test_injected_normalizer_failure_rolls_back_without_partial_ledger_state(self):
        def fail_after_write_candidate(_payload):
            raise RuntimeError("injected normalizer failure")

        repository = FhirLedgerRepository(
            self.store.database.connect, self.store.database.lock,
            timestamp_factory=lambda: "2026-07-16T00:00:00+00:00",
            payload_normalizer=fail_after_write_candidate,
        )
        with self.assertRaisesRegex(RuntimeError, "injected normalizer failure"):
            repository.create_fhir_workflow_record(self.payload())
        with self.store.database.connect() as connection:
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM local_fhir_workflow_records").fetchone()[0])
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM local_fhir_sync_attempts").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
