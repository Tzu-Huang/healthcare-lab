from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.domain.dicom import reconcile_result_metadata
from backend.domain.statuses import (
    DCM4CHEE_RESULT_STATUS_AMBIGUOUS,
    DCM4CHEE_RESULT_STATUS_MATCHED,
    DCM4CHEE_RESULT_STATUS_NO_RESULT,
    DCM4CHEE_RESULT_STATUS_WRONG_PATIENT,
)
from backend.lab_store import DemoStore


class Dcm4cheeResultRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "results.db"
        self.store = DemoStore(self.path)
        self.patient = self.store.create_patient_record(
            {"mrn": "MRN-RESULT-001", "firstName": "Katherine", "lastName": "Johnson", "dob": "19180826", "sex": "F"}
        )
        self.order = self.store.create_dcm4chee_order_record({"patientRecordId": self.patient["id"]})
        self.profile = {
            "profileName": "local-dcm4chee",
            "dimse": {"calledAETitle": "DCM4CHEE"},
            "mwl": {"aeTitle": "WORKLIST", "defaultScheduledStationAETitle": "ECG_AP"},
            "dicomweb": {"wadoRsUrl": "http://example.test/dicomweb"},
            "viewer": {"studyUrlTemplate": "http://example.test/view/{studyInstanceUid}"},
        }
        self.mapping = self.store.upsert_dcm4chee_mwl_mapping(int(self.order["id"]), self.profile)

    def metadata(self, **overrides: str) -> dict[str, str]:
        values = {
            "study_instance_uid": self.mapping["studyInstanceUid"],
            "series_instance_uid": f"{self.mapping['studyInstanceUid']}.1",
            "sop_instance_uid": f"{self.mapping['studyInstanceUid']}.1.1",
            "accession_number": self.mapping["accessionNumber"],
            "patient_id": self.mapping["patientId"],
            "issuer_of_patient_id": self.mapping["issuerOfPatientId"],
            "requested_procedure_id": self.mapping["requestedProcedureId"],
            "scheduled_procedure_step_id": self.mapping["scheduledProcedureStepId"],
            "modality": "ECG",
        }
        values.update(overrides)
        return values

    def test_shared_lock_reconciliation_links_and_rollback(self) -> None:
        self.assertIs(self.store.dcm4chee_result_repository.lock, self.store.database.lock)
        result = self.store.upsert_dcm4chee_result_record(
            self.metadata(), self.profile, patient_record_id=int(self.patient["id"])
        )
        self.assertEqual(result["reconciliationStatus"], DCM4CHEE_RESULT_STATUS_MATCHED)
        self.assertEqual(result["orderRecordId"], self.order["id"])
        self.assertIn(self.mapping["studyInstanceUid"], result["viewerUrl"])

        with self.store.connect() as connection:
            connection.execute(
                """CREATE TRIGGER reject_result_update
                   BEFORE UPDATE ON local_dcm4chee_result_records
                   BEGIN SELECT RAISE(ABORT, 'test rollback'); END"""
            )
        with self.assertRaisesRegex(sqlite3.IntegrityError, "test rollback"):
            self.store.upsert_dcm4chee_result_record(
                self.metadata(modality="DOC"), self.profile,
                patient_record_id=int(self.patient["id"]),
            )
        self.assertEqual(self.store.get_dcm4chee_result_record(int(result["id"]))["modality"], "ECG")

    def test_completed_snapshots_generation_order_and_diagnostics(self) -> None:
        patient_id = int(self.patient["id"])
        self.store.begin_dcm4chee_result_refresh(patient_id, "generation-1")
        first = self.store.upsert_dcm4chee_result_record(
            self.metadata(), self.profile, patient_record_id=patient_id,
            refresh_generation="generation-1",
        )
        self.store.complete_dcm4chee_result_refresh(patient_id, "generation-1")
        self.store.begin_dcm4chee_result_refresh(patient_id, "generation-2")
        self.store.record_dcm4chee_result_refresh_diagnostic(
            patient_record_id=patient_id, profile=self.profile,
            status=DCM4CHEE_RESULT_STATUS_NO_RESULT, refresh_generation="generation-2",
        )
        self.assertEqual([item["id"] for item in self.store.list_dcm4chee_results_for_patient(patient_id)], [first["id"]])
        snapshot = self.store.complete_dcm4chee_result_refresh(patient_id, "generation-2")
        self.assertEqual([item["reconciliationStatus"] for item in snapshot], [DCM4CHEE_RESULT_STATUS_NO_RESULT])

        stale = self.store.upsert_dcm4chee_result_record(
            self.metadata(), self.profile, patient_record_id=patient_id,
            refresh_generation="generation-1",
        )
        self.assertEqual(stale["refreshGeneration"], "generation-1")
        self.assertEqual(
            [item["reconciliationStatus"] for item in self.store.get_patient_record(patient_id)["dcm4chee"]["dicomResults"]],
            [DCM4CHEE_RESULT_STATUS_NO_RESULT],
        )

    def test_refresh_completion_failure_preserves_previous_snapshot(self) -> None:
        patient_id = int(self.patient["id"])
        self.store.begin_dcm4chee_result_refresh(patient_id, "generation-1")
        first = self.store.upsert_dcm4chee_result_record(
            self.metadata(), self.profile, patient_record_id=patient_id,
            refresh_generation="generation-1",
        )
        self.store.complete_dcm4chee_result_refresh(patient_id, "generation-1")

        self.store.begin_dcm4chee_result_refresh(patient_id, "generation-2")
        self.store.upsert_dcm4chee_result_record(
            self.metadata(modality="DOC"), self.profile, patient_record_id=patient_id,
            refresh_generation="generation-2",
        )
        with self.store.connect() as connection:
            connection.execute(
                """CREATE TRIGGER reject_refresh_publication
                   BEFORE UPDATE OF completed_at, results_snapshot_json
                   ON local_dcm4chee_result_refresh_runs
                   WHEN OLD.refresh_generation = 'generation-2'
                   BEGIN SELECT RAISE(ABORT, 'reject refresh publication'); END"""
            )

        with self.assertRaisesRegex(sqlite3.IntegrityError, "reject refresh publication"):
            self.store.complete_dcm4chee_result_refresh(patient_id, "generation-2")

        reopened = DemoStore(self.path)
        visible = reopened.list_dcm4chee_results_for_patient(patient_id)
        with reopened.connect() as connection:
            failed_run = connection.execute(
                """SELECT completed_at, results_snapshot_json
                   FROM local_dcm4chee_result_refresh_runs
                   WHERE patient_record_id = ? AND refresh_generation = ?""",
                (patient_id, "generation-2"),
            ).fetchone()
        self.assertEqual([item["id"] for item in visible], [first["id"]])
        self.assertEqual([item["modality"] for item in visible], ["ECG"])
        self.assertEqual(failed_run["completed_at"], "")
        self.assertEqual(failed_run["results_snapshot_json"], "[]")

    def test_pure_reconciliation_rejects_wrong_patient_and_reports_duplicates(self) -> None:
        mapping = dict(self.mapping)
        wrong = reconcile_result_metadata(
            self.metadata(study_instance_uid="", patient_id="WRONG"), [mapping],
            profile_name=mapping["profileName"], server_identity=mapping["serverIdentity"],
        )
        duplicate = reconcile_result_metadata(
            self.metadata(), [mapping, {**mapping, "id": int(mapping["id"]) + 1}],
            profile_name=mapping["profileName"], server_identity=mapping["serverIdentity"],
        )
        self.assertEqual(wrong["status"], DCM4CHEE_RESULT_STATUS_WRONG_PATIENT)
        self.assertEqual(duplicate["status"], DCM4CHEE_RESULT_STATUS_AMBIGUOUS)
        self.assertEqual(len(duplicate["diagnostic"]["candidateMappingIds"]), 2)


if __name__ == "__main__":
    unittest.main()
