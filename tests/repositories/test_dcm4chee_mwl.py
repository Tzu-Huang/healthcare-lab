from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.domain.dicom import historical_mwl_identifiers
from backend.domain.statuses import (
    DCM4CHEE_MWL_STATUS_CREATED,
    DCM4CHEE_MWL_STATUS_FAILED,
    DCM4CHEE_MWL_VERIFICATION_VERIFIED,
)
from backend.application_composition import assemble_application_dependencies
from backend.repositories.database import SQLiteDatabase
from backend.repositories.dcm4chee_mwl import backfill_dcm4chee_mwl_mappings
from tests.repositories._case_support import build_dcm4chee_mwl_payload


class Dcm4cheeMwlRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "mwl.db"
        self.dependencies = assemble_application_dependencies(self.path)
        patient = self.dependencies.patient_repository.create_patient_record(
            {"mrn": "MRN-MWL-001", "firstName": "Grace", "lastName": "Hopper", "dob": "19061209", "sex": "F"}
        )
        self.order = self.dependencies.order_repository.create_dcm4chee_order_record(
            {"patientRecordId": patient["id"], "requestedAt": "20260715103000"}
        )
        self.profile = {
            "profileName": "local-dcm4chee",
            "dimse": {"calledAETitle": "DCM4CHEE"},
            "mwl": {"aeTitle": "WORKLIST", "defaultScheduledStationAETitle": "ECG_AP"},
        }

    def test_shared_lock_stable_identifiers_retry_readback_and_verification(self) -> None:
        self.assertIs(self.dependencies.dcm4chee_mwl_repository.lock, self.dependencies.database.lock)
        first = self.dependencies.dcm4chee_mwl_repository.upsert_dcm4chee_mwl_mapping(int(self.order["id"]), self.profile)
        second = self.dependencies.dcm4chee_mwl_repository.upsert_dcm4chee_mwl_mapping(
            int(self.order["id"]), self.profile, increment_retry=True
        )
        attempt = self.dependencies.dcm4chee_mwl_attempt_coordinator.create_dcm4chee_mwl_attempt(
            int(self.order["id"]),
            self.profile,
            request_payload=second["latestRequestPayload"] or None,
            mapping_id=int(second["id"]),
        )
        attempt = self.dependencies.dcm4chee_mwl_repository.update_dcm4chee_mwl_attempt_result(
            int(attempt["id"]), attempt_status=DCM4CHEE_MWL_STATUS_CREATED,
            http_status=200, response_body='{"created":true}',
        )
        updated = self.dependencies.dcm4chee_mwl_repository.update_dcm4chee_mwl_mapping_from_attempt(
            int(self.order["id"]), attempt_id=int(attempt["id"]),
            sync_status=DCM4CHEE_MWL_STATUS_CREATED,
            readback_payload={"00080050": {"vr": "SH", "Value": [first["accessionNumber"]]}},
        )
        verify = self.dependencies.dcm4chee_mwl_repository.create_dcm4chee_mwl_verification_attempt(
            int(self.order["id"]), updated, request_url="http://example.test/mwl",
            query_criteria={"AccessionNumber": updated["accessionNumber"]},
        )
        verified = self.dependencies.dcm4chee_mwl_repository.update_dcm4chee_mwl_verification_result(
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
        mapping = self.dependencies.dcm4chee_mwl_repository.upsert_dcm4chee_mwl_mapping(int(self.order["id"]), self.profile)
        with self.dependencies.database.connect() as connection:
            connection.execute(
                """CREATE TRIGGER reject_mwl_mapping_update
                   BEFORE UPDATE ON local_dcm4chee_mwl_mappings
                   BEGIN SELECT RAISE(ABORT, 'test rollback'); END"""
            )
        with self.assertRaisesRegex(sqlite3.IntegrityError, "test rollback"):
            self.dependencies.dcm4chee_mwl_repository.upsert_dcm4chee_mwl_mapping(
                int(self.order["id"]), self.profile,
                sync_status=DCM4CHEE_MWL_STATUS_FAILED, increment_retry=True,
            )
        current = self.dependencies.dcm4chee_mwl_repository.get_dcm4chee_mwl_mapping_for_order(int(self.order["id"]))
        self.assertEqual(current["id"], mapping["id"])
        self.assertEqual(current["retryCount"], 0)
        with self.assertRaises(KeyError):
            self.dependencies.dcm4chee_mwl_repository.get_dcm4chee_mwl_attempt(999999)

    def test_historical_backfill_selects_latest_and_preserves_existing_mapping(self) -> None:
        preserved = self.dependencies.dcm4chee_mwl_repository.upsert_dcm4chee_mwl_mapping(int(self.order["id"]), self.profile)
        with self.dependencies.database.connect() as connection:
            connection.execute(
                "UPDATE local_dcm4chee_mwl_mappings SET worklist_label = ? WHERE id = ?",
                ("USER MANAGED", int(preserved["id"])),
            )
            preserved_before = dict(
                connection.execute(
                    "SELECT * FROM local_dcm4chee_mwl_mappings WHERE id = ?",
                    (int(preserved["id"]),),
                ).fetchone()
            )

        historical_order = self.dependencies.order_repository.create_dcm4chee_order_record(
            {"patientRecordId": self.order["patientRecordId"], "requestedAt": "20260715113000"}
        )
        payload = build_dcm4chee_mwl_payload(historical_order, self.profile)
        older = self.dependencies.dcm4chee_mwl_attempt_coordinator.create_dcm4chee_mwl_attempt(
            int(historical_order["id"]), self.profile, request_payload=payload,
            attempt_status=DCM4CHEE_MWL_STATUS_FAILED,
        )
        latest = self.dependencies.dcm4chee_mwl_attempt_coordinator.create_dcm4chee_mwl_attempt(
            int(historical_order["id"]), self.profile, request_payload=payload,
            attempt_status=DCM4CHEE_MWL_STATUS_CREATED,
        )
        with self.dependencies.database.connect() as connection:
            connection.execute(
                "UPDATE local_dcm4chee_mwl_attempts SET attempted_at = ? WHERE id = ?",
                ("2026-07-15T10:00:00", int(older["id"])),
            )
            connection.execute(
                "UPDATE local_dcm4chee_mwl_attempts SET attempted_at = ? WHERE id = ?",
                ("2026-07-15T11:00:00", int(latest["id"])),
            )

        first_reopen = assemble_application_dependencies(self.path)
        second_reopen = assemble_application_dependencies(self.path)
        mappings = second_reopen.dcm4chee_mwl_repository.list_dcm4chee_mwl_mappings_for_patient(int(self.order["patientRecordId"]))
        backfilled = next(item for item in mappings if item["orderRecordId"] == historical_order["id"])
        attempts = second_reopen.dcm4chee_mwl_repository.list_dcm4chee_mwl_attempts(int(historical_order["id"]))
        with second_reopen.database.connect() as connection:
            preserved_after = dict(
                connection.execute(
                    "SELECT * FROM local_dcm4chee_mwl_mappings WHERE id = ?",
                    (int(preserved["id"]),),
                ).fetchone()
            )

        self.assertEqual(len(mappings), 2)
        self.assertEqual(backfilled["lastAttemptId"], latest["id"])
        self.assertEqual({item["mappingId"] for item in attempts}, {backfilled["id"]})
        self.assertEqual(preserved_after, preserved_before)
        self.assertEqual(
            first_reopen.dcm4chee_mwl_repository.get_dcm4chee_mwl_mapping_for_order(int(historical_order["id"]))["id"],
            backfilled["id"],
        )

    def test_historical_backfill_rolls_back_with_startup_maintenance(self) -> None:
        historical_order = self.dependencies.order_repository.create_dcm4chee_order_record(
            {"patientRecordId": self.order["patientRecordId"], "requestedAt": "20260715123000"}
        )
        payload = build_dcm4chee_mwl_payload(historical_order, self.profile)
        attempt = self.dependencies.dcm4chee_mwl_attempt_coordinator.create_dcm4chee_mwl_attempt(
            int(historical_order["id"]), self.profile, request_payload=payload,
            attempt_status=DCM4CHEE_MWL_STATUS_CREATED,
        )

        def apply_backfill(connection: sqlite3.Connection) -> None:
            backfill_dcm4chee_mwl_mappings(
                connection,
                order_default_text="12 Lead ECG",
                create_operation="create",
                identifier_projector=historical_mwl_identifiers,
            )

        def fail_after_backfill(_connection: sqlite3.Connection) -> None:
            raise RuntimeError("fail after backfill")

        database = SQLiteDatabase(
            self.path, maintenance=(apply_backfill, fail_after_backfill)
        )
        with self.assertRaisesRegex(RuntimeError, "fail after backfill"):
            database.initialize()

        with self.dependencies.database.connect() as connection:
            mapping_count = connection.execute(
                "SELECT COUNT(*) FROM local_dcm4chee_mwl_mappings WHERE order_record_id = ?",
                (int(historical_order["id"]),),
            ).fetchone()[0]
            mapping_id = connection.execute(
                "SELECT mapping_id FROM local_dcm4chee_mwl_attempts WHERE id = ?",
                (int(attempt["id"]),),
            ).fetchone()[0]
        self.assertEqual(mapping_count, 0)
        self.assertIsNone(mapping_id)


if __name__ == "__main__":
    unittest.main()
