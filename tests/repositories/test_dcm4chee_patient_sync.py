from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.domain.statuses import (
    DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
    DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED,
)
from backend.lab_store import DemoStore


class Dcm4cheePatientSyncRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.database_path = Path(self.temp_dir.name) / "patient-sync.db"
        self.store = DemoStore(self.database_path)
        self.patient = self.store.create_patient_record(
            {
                "mode": "hl7-v2",
                "mrn": "MRN-DCM-001",
                "firstName": "Ada",
                "lastName": "Lovelace",
                "dob": "18151210",
                "sex": "F",
            }
        )
        self.profile = {
            "profileName": "local-dcm4chee",
            "dimse": {"calledAETitle": "DCM4CHEE"},
            "hl7": {
                "host": "dcm4chee",
                "port": 2575,
                "patientAssigningAuthority": "local-dcm4chee",
                "receivingApplication": "DCM4CHEE",
                "receivingFacility": "DCM4CHEE",
            },
        }

    def test_uses_disposable_database_and_shared_application_lock(self) -> None:
        self.assertNotIn("instance", self.database_path.parts)
        self.assertIs(self.store.dcm4chee_patient_sync_repository.lock, self.store.database.lock)

    def test_projects_ack_error_retry_and_success_transitions(self) -> None:
        sync = self.store.upsert_dcm4chee_patient_sync(int(self.patient["id"]), self.profile)
        failed_attempt = self.store.create_dcm4chee_patient_sync_attempt(
            int(self.patient["id"]),
            self.profile,
            patient_sync_id=int(sync["id"]),
            attempt_status=DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
            error_type="dcm4chee_hl7_unreachable",
            error_text="connection refused",
        )
        failed = self.store.update_dcm4chee_patient_sync_from_attempt(
            int(sync["id"]), failed_attempt, sync_status=DCM4CHEE_PATIENT_SYNC_STATUS_FAILED
        )
        retried = self.store.upsert_dcm4chee_patient_sync(
            int(self.patient["id"]), self.profile, increment_retry=True
        )
        success_attempt = self.store.create_dcm4chee_patient_sync_attempt(
            int(self.patient["id"]),
            self.profile,
            patient_sync_id=int(sync["id"]),
        )
        success_attempt = self.store.update_dcm4chee_patient_sync_attempt_result(
            int(success_attempt["id"]),
            attempt_status=DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED,
            response_payload="MSA|AA|CONTROL-1",
            ack={"code": "AA", "controlId": "CONTROL-1", "text": "accepted"},
        )
        succeeded = self.store.update_dcm4chee_patient_sync_from_attempt(
            int(sync["id"]), success_attempt, sync_status=DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED
        )

        self.assertTrue(failed["retryable"])
        self.assertEqual(failed["lastErrorType"], "dcm4chee_hl7_unreachable")
        self.assertEqual(retried["retryCount"], 1)
        self.assertEqual(succeeded["ack"]["code"], "AA")
        self.assertFalse(succeeded["retryable"])
        self.assertEqual(len(self.store.list_dcm4chee_patient_sync_attempts(int(self.patient["id"]))), 2)

    def test_failed_update_rolls_back_and_not_found_is_explicit(self) -> None:
        sync = self.store.upsert_dcm4chee_patient_sync(int(self.patient["id"]), self.profile)
        with self.store.connect() as connection:
            connection.execute(
                """CREATE TRIGGER reject_patient_sync_update
                   BEFORE UPDATE ON local_dcm4chee_patient_syncs
                   BEGIN SELECT RAISE(ABORT, 'test rollback'); END"""
            )

        with self.assertRaisesRegex(sqlite3.IntegrityError, "test rollback"):
            self.store.upsert_dcm4chee_patient_sync(
                int(self.patient["id"]), self.profile, increment_retry=True
            )
        self.assertEqual(self.store.get_dcm4chee_patient_sync(int(sync["id"]))["retryCount"], 0)
        with self.assertRaises(KeyError):
            self.store.get_dcm4chee_patient_sync(999999)


if __name__ == "__main__":
    unittest.main()
