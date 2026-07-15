from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.domain.statuses import (
    DCM4CHEE_MWL_STATUS_CREATED,
    DCM4CHEE_MWL_STATUS_FAILED,
    DCM4CHEE_MWL_VERIFICATION_VERIFIED,
)
from backend.lab_store import DemoStore


class Dcm4cheeMwlRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "mwl.db"
        self.store = DemoStore(self.path)
        patient = self.store.create_patient_record(
            {"mrn": "MRN-MWL-001", "firstName": "Grace", "lastName": "Hopper", "dob": "19061209", "sex": "F"}
        )
        self.order = self.store.create_dcm4chee_order_record(
            {"patientRecordId": patient["id"], "requestedAt": "20260715103000"}
        )
        self.profile = {
            "profileName": "local-dcm4chee",
            "dimse": {"calledAETitle": "DCM4CHEE"},
            "mwl": {"aeTitle": "WORKLIST", "defaultScheduledStationAETitle": "ECG_AP"},
        }

    def test_shared_lock_stable_identifiers_retry_readback_and_verification(self) -> None:
        self.assertIs(self.store.dcm4chee_mwl_repository.lock, self.store.database.lock)
        first = self.store.upsert_dcm4chee_mwl_mapping(int(self.order["id"]), self.profile)
        second = self.store.upsert_dcm4chee_mwl_mapping(
            int(self.order["id"]), self.profile, increment_retry=True
        )
        attempt = self.store.create_dcm4chee_mwl_attempt(
            int(self.order["id"]),
            self.profile,
            request_payload=second["latestRequestPayload"] or None,
            mapping_id=int(second["id"]),
        )
        attempt = self.store.update_dcm4chee_mwl_attempt_result(
            int(attempt["id"]), attempt_status=DCM4CHEE_MWL_STATUS_CREATED,
            http_status=200, response_body='{"created":true}',
        )
        updated = self.store.update_dcm4chee_mwl_mapping_from_attempt(
            int(self.order["id"]), attempt_id=int(attempt["id"]),
            sync_status=DCM4CHEE_MWL_STATUS_CREATED,
            readback_payload={"00080050": {"vr": "SH", "Value": [first["accessionNumber"]]}},
        )
        verify = self.store.create_dcm4chee_mwl_verification_attempt(
            int(self.order["id"]), updated, request_url="http://example.test/mwl",
            query_criteria={"AccessionNumber": updated["accessionNumber"]},
        )
        verified = self.store.update_dcm4chee_mwl_verification_result(
            int(self.order["id"]), attempt_id=int(verify["id"]),
            verification_status=DCM4CHEE_MWL_VERIFICATION_VERIFIED,
            method="dcm4chee-mwl-rest", query_criteria={"AccessionNumber": updated["accessionNumber"]},
            match_payload={"count": 1},
        )

        self.assertEqual(first["studyInstanceUid"], second["studyInstanceUid"])
        self.assertEqual(second["retryCount"], 1)
        self.assertEqual(updated["latestReadbackPayload"]["00080050"]["Value"], [first["accessionNumber"]])
        self.assertEqual(verified["verification"]["status"], DCM4CHEE_MWL_VERIFICATION_VERIFIED)

    def test_mapping_update_rollback_and_not_found(self) -> None:
        mapping = self.store.upsert_dcm4chee_mwl_mapping(int(self.order["id"]), self.profile)
        with self.store.connect() as connection:
            connection.execute(
                """CREATE TRIGGER reject_mwl_mapping_update
                   BEFORE UPDATE ON local_dcm4chee_mwl_mappings
                   BEGIN SELECT RAISE(ABORT, 'test rollback'); END"""
            )
        with self.assertRaisesRegex(sqlite3.IntegrityError, "test rollback"):
            self.store.upsert_dcm4chee_mwl_mapping(
                int(self.order["id"]), self.profile,
                sync_status=DCM4CHEE_MWL_STATUS_FAILED, increment_retry=True,
            )
        current = self.store.get_dcm4chee_mwl_mapping_for_order(int(self.order["id"]))
        self.assertEqual(current["id"], mapping["id"])
        self.assertEqual(current["retryCount"], 0)
        with self.assertRaises(KeyError):
            self.store.get_dcm4chee_mwl_attempt(999999)

    def test_historical_backfill_is_idempotent_and_links_attempts(self) -> None:
        payload = self.store.build_dcm4chee_mwl_payload(self.order, self.profile)
        attempt = self.store.create_dcm4chee_mwl_attempt(
            int(self.order["id"]), self.profile, request_payload=payload,
            attempt_status=DCM4CHEE_MWL_STATUS_CREATED,
        )
        with self.store.connect() as connection:
            connection.execute("DELETE FROM local_dcm4chee_mwl_mappings")
            connection.execute("UPDATE local_dcm4chee_mwl_attempts SET mapping_id = NULL")

        first_reopen = DemoStore(self.path)
        second_reopen = DemoStore(self.path)
        mappings = second_reopen.list_dcm4chee_mwl_mappings_for_patient(int(self.order["patientRecordId"]))
        attempts = second_reopen.list_dcm4chee_mwl_attempts(int(self.order["id"]))
        self.assertEqual(len(mappings), 1)
        self.assertEqual(mappings[0]["lastAttemptId"], attempt["id"])
        self.assertEqual(attempts[0]["mappingId"], mappings[0]["id"])
        self.assertEqual(first_reopen.get_dcm4chee_mwl_mapping_for_order(int(self.order["id"]))["id"], mappings[0]["id"])


if __name__ == "__main__":
    unittest.main()
