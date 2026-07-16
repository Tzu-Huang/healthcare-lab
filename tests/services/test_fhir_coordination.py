import tempfile
import unittest
from pathlib import Path

from backend.domain.errors import SimulatorValidationError
from backend.lab_store import DemoStore
from backend.repositories.fhir_ledger import FhirLedgerRepository
from backend.services.fhir_coordination import (
    FhirOrderCoordinator, PatientFhirCoordinator,
    create_order_ledger_record, create_patient_ledger_record,
)
from backend.templates.fhir import build_service_request


class FhirCoordinationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = DemoStore(Path(self.directory.name) / "coordination.db")
        self.ledger = FhirLedgerRepository(
            self.store.database.connect, self.store.database.lock,
            timestamp_factory=lambda: "2026-07-16T09:00:00+00:00",
        )
        self.patient_coordinator = PatientFhirCoordinator(
            self.store.patient_repository, self.ledger
        )
        self.order_coordinator = FhirOrderCoordinator(
            self.store.patient_repository, self.store.order_repository, self.ledger,
            timestamp_factory=lambda: "2026-07-16T09:00:00+00:00",
            storage_timestamp_factory=lambda: "20260716090000",
            resource_builder=build_service_request,
        )

    def tearDown(self):
        self.directory.cleanup()

    def patient(self, *, mode="fhir", mrn="MRN-FHIR-COORD"):
        return self.store.patient_repository.create_patient_record({
            "mode": mode, "mrn": mrn, "firstName": "Avery", "lastName": "Morgan",
            "dob": "19850412", "sex": "F",
        })

    def sync_patient(self, patient):
        record = self.patient_coordinator.create_patient_fhir_workflow_record(patient)
        self.ledger.mark_fhir_sync_success(
            record["id"], medplum_resource_id="patient-1",
            medplum_resource_reference="Patient/patient-1",
        )
        return self.store.patient_repository.get_patient_record(patient["id"])

    def test_patient_coordinator_creates_ledger_from_json_payload(self):
        patient = self.patient()
        record = self.patient_coordinator.create_patient_fhir_workflow_record_by_id(patient["id"])
        self.assertEqual("Patient", record["resourceType"])
        self.assertEqual(str(patient["id"]), record["localSourceId"])
        self.assertEqual("MRN-FHIR-COORD", record["resource"]["identifier"][1]["value"])
        with self.assertRaisesRegex(SimulatorValidationError, "not FHIR mode"):
            create_patient_ledger_record(self.patient(mode="hl7-v2", mrn="MRN-HL7"), self.ledger)

    def test_order_requires_fhir_synced_patient_reference(self):
        patient = self.patient()
        with self.assertRaisesRegex(SimulatorValidationError, "synced Medplum Patient"):
            self.order_coordinator.create_fhir_order_record({"patientRecordId": patient["id"]})
        with self.store.database.connect() as connection:
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM local_order_records").fetchone()[0])
        synced = self.sync_patient(patient)
        synced["fhir"]["medplum"]["reference"] = "Observation/not-patient"
        class BadReferencePatients:
            def get_patient_record(self, _record_id):
                return synced
        coordinator = FhirOrderCoordinator(
            BadReferencePatients(), self.store.order_repository, self.ledger,
            timestamp_factory=lambda: "2026-07-16T09:00:00+00:00",
            storage_timestamp_factory=lambda: "20260716090000",
            resource_builder=build_service_request,
        )
        with self.assertRaisesRegex(SimulatorValidationError, "Patient/<id>"):
            coordinator.create_fhir_order_record({"patientRecordId": patient["id"]})

    def test_local_order_then_service_request_ledger_preserve_content(self):
        patient = self.patient()
        self.sync_patient(patient)
        order, record = self.order_coordinator.create_local_order_and_ledger({
            "patientRecordId": patient["id"],
            "fhir": {"priority": "stat", "requester": "Practitioner/prac-1", "note": "Keep"},
        })
        self.assertEqual(("FHIR R4", "ServiceRequest", "S"),
                         (order["protocolVersion"], order["messageType"], order["priority"]))
        self.assertEqual("Patient/patient-1", record["resource"]["subject"]["reference"])
        self.assertEqual("Practitioner/prac-1", record["resource"]["requester"]["reference"])
        self.assertEqual(str(order["id"]), record["localSourceId"])

    def test_ledger_failure_occurs_after_committed_local_order(self):
        patient = self.patient()
        self.sync_patient(patient)
        events = []

        class RecordingOrders:
            def create_fhir_order_record(inner_self, *args, **kwargs):
                events.append("order")
                return self.store.order_repository.create_fhir_order_record(*args, **kwargs)

        class FailingLedger:
            def create_fhir_workflow_record(inner_self, _payload):
                events.append("ledger")
                raise RuntimeError("injected ledger failure")

        coordinator = FhirOrderCoordinator(
            self.store.patient_repository, RecordingOrders(), FailingLedger(),
            timestamp_factory=lambda: "2026-07-16T09:00:00+00:00",
            storage_timestamp_factory=lambda: "20260716090000",
            resource_builder=build_service_request,
        )
        with self.assertRaisesRegex(RuntimeError, "injected ledger failure"):
            coordinator.create_local_order_and_ledger({"patientRecordId": patient["id"]})
        self.assertEqual(["order", "ledger"], events)
        self.assertEqual(1, len(self.store.order_repository.list_order_records("FHIR R4")))

    def test_order_ledger_helper_rejects_non_fhir_order(self):
        with self.assertRaisesRegex(SimulatorValidationError, "Order record is not FHIR mode"):
            create_order_ledger_record({"id": 1, "protocolVersion": "HL7 v2.5.1", "payload": ""}, self.ledger)


if __name__ == "__main__":
    unittest.main()
