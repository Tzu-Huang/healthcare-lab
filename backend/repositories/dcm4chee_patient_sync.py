"""SQLite persistence owner for dcm4chee Patient sync mappings and attempts."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from sqlite3 import Connection, Row
from threading import RLock
from typing import Any

from backend.domain.errors import SimulatorValidationError
from backend.domain.statuses import (
    DCM4CHEE_PATIENT_SYNC_OPERATION_ADT_CREATE,
    DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
    DCM4CHEE_PATIENT_SYNC_STATUS_PENDING,
    DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED,
)

ConnectionFactory = Callable[[], AbstractContextManager[Connection]]


def _json_value(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return fallback

def project_patient_sync_dict(row: Row) -> dict[str, Any]:
        status = str(row["sync_status"] or "")
        retryable = status in {DCM4CHEE_PATIENT_SYNC_STATUS_PENDING, DCM4CHEE_PATIENT_SYNC_STATUS_FAILED}
        return {
            "id": row["id"],
            "patientRecordId": row["patient_record_id"],
            "profileName": row["profile_name"],
            "serverIdentity": row["server_identity"],
            "patientId": row["patient_id"],
            "issuerOfPatientId": row["issuer_of_patient_id"],
            "hl7Host": row["hl7_host"],
            "hl7Port": row["hl7_port"],
            "receivingApplication": row["receiving_application"],
            "receivingFacility": row["receiving_facility"],
            "status": status,
            "displayStatus": "Synced" if status == DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED else status,
            "retryable": retryable,
            "retryCount": row["retry_count"],
            "lastAttemptId": row["last_attempt_id"],
            "ack": {
                "code": row["last_ack_code"],
                "controlId": row["last_ack_control_id"],
                "text": row["last_ack_text"],
            },
            "lastResponsePayload": row["last_response_payload"],
            "lastErrorType": row["last_error_type"],
            "lastError": row["last_error_text"],
            "lastSyncAt": row["last_sync_at"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }


def project_patient_sync_attempt_dict(row: Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "patientSyncId": row["patient_sync_id"],
            "operationType": row["operation_type"],
            "patientRecordId": row["patient_record_id"],
            "profileName": row["profile_name"],
            "serverIdentity": row["server_identity"],
            "patientId": row["patient_id"],
            "issuerOfPatientId": row["issuer_of_patient_id"],
            "requestUrl": row["request_url"],
            "requestPayload": row["request_payload"],
            "responsePayload": row["response_payload"],
            "ack": {
                "code": row["ack_code"],
                "controlId": row["ack_control_id"],
                "text": row["ack_text"],
            },
            "status": row["attempt_status"],
            "errorType": row["error_type"],
            "error": row["error_text"],
            "attemptedAt": row["attempted_at"],
            "completedAt": row["completed_at"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }


class Dcm4cheePatientSyncRepository:
    def __init__(self, connection_factory: ConnectionFactory, lock: RLock, *, patient_loader,
                 identifiers, timestamp_factory) -> None:
        self._connect = connection_factory
        self._lock = lock
        self._get_patient_record = patient_loader
        self._identifiers = identifiers
        self._timestamp = timestamp_factory

    @property
    def lock(self) -> RLock:
        return self._lock

    def upsert_dcm4chee_patient_sync(
            self,
            patient_record_id: int,
            profile: dict[str, Any],
            *,
            sync_status: str = DCM4CHEE_PATIENT_SYNC_STATUS_PENDING,
            increment_retry: bool = False,
        ) -> dict[str, Any]:
            patient = self._get_patient_record(patient_record_id)
            identifiers = self._identifiers(patient, profile)
            if not identifiers["patient_id"]:
                raise SimulatorValidationError("dcm4chee Patient ID is required.")
            if not identifiers["issuer_of_patient_id"]:
                raise SimulatorValidationError("dcm4chee Patient issuer is required.")
            now = self._timestamp()
            with self._lock, self._connect() as connection:
                existing = connection.execute(
                    """
                    SELECT * FROM local_dcm4chee_patient_syncs
                    WHERE patient_record_id = ? AND profile_name = ? AND server_identity = ?
                    """,
                    (int(patient_record_id), identifiers["profile_name"], identifiers["server_identity"]),
                ).fetchone()
                if existing:
                    connection.execute(
                        """
                        UPDATE local_dcm4chee_patient_syncs
                        SET patient_id = ?, issuer_of_patient_id = ?, hl7_host = ?, hl7_port = ?,
                            receiving_application = ?, receiving_facility = ?, sync_status = ?,
                            retry_count = retry_count + ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            identifiers["patient_id"],
                            identifiers["issuer_of_patient_id"],
                            identifiers["hl7_host"],
                            int(identifiers["hl7_port"] or 0),
                            identifiers["receiving_application"],
                            identifiers["receiving_facility"],
                            sync_status,
                            1 if increment_retry else 0,
                            now,
                            existing["id"],
                        ),
                    )
                    sync_id = int(existing["id"])
                else:
                    cursor = connection.execute(
                        """
                        INSERT INTO local_dcm4chee_patient_syncs (
                            patient_record_id, profile_name, server_identity, patient_id,
                            issuer_of_patient_id, hl7_host, hl7_port, receiving_application,
                            receiving_facility, sync_status, retry_count, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            int(patient_record_id),
                            identifiers["profile_name"],
                            identifiers["server_identity"],
                            identifiers["patient_id"],
                            identifiers["issuer_of_patient_id"],
                            identifiers["hl7_host"],
                            int(identifiers["hl7_port"] or 0),
                            identifiers["receiving_application"],
                            identifiers["receiving_facility"],
                            sync_status,
                            1 if increment_retry else 0,
                            now,
                            now,
                        ),
                    )
                    sync_id = int(cursor.lastrowid)
            return self.get_dcm4chee_patient_sync(sync_id)

    def get_dcm4chee_patient_sync(self, sync_id: int) -> dict[str, Any]:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM local_dcm4chee_patient_syncs WHERE id = ?",
                    (int(sync_id),),
                ).fetchone()
                if not row:
                    raise KeyError(sync_id)
            return project_patient_sync_dict(row)

    def get_dcm4chee_patient_sync_for_patient(
            self,
            patient_record_id: int,
            profile: dict[str, Any] | None = None,
        ) -> dict[str, Any] | None:
            with self._connect() as connection:
                if profile:
                    identifiers = self._identifiers(self._get_patient_record(patient_record_id), profile)
                    row = connection.execute(
                        """
                        SELECT * FROM local_dcm4chee_patient_syncs
                        WHERE patient_record_id = ? AND profile_name = ? AND server_identity = ?
                        ORDER BY updated_at DESC, id DESC
                        LIMIT 1
                        """,
                        (int(patient_record_id), identifiers["profile_name"], identifiers["server_identity"]),
                    ).fetchone()
                else:
                    row = connection.execute(
                        """
                        SELECT * FROM local_dcm4chee_patient_syncs
                        WHERE patient_record_id = ?
                        ORDER BY updated_at DESC, id DESC
                        LIMIT 1
                        """,
                        (int(patient_record_id),),
                    ).fetchone()
            return project_patient_sync_dict(row) if row else None

    def create_dcm4chee_patient_sync_attempt(
            self,
            patient_record_id: int,
            profile: dict[str, Any],
            *,
            operation_type: str = DCM4CHEE_PATIENT_SYNC_OPERATION_ADT_CREATE,
            request_url: str = "",
            request_payload: str = "",
            attempt_status: str = DCM4CHEE_PATIENT_SYNC_STATUS_PENDING,
            error_type: str = "",
            error_text: str = "",
            response_payload: str = "",
            ack: dict[str, str] | None = None,
            patient_sync_id: int | None = None,
        ) -> dict[str, Any]:
            patient = self._get_patient_record(patient_record_id)
            identifiers = self._identifiers(patient, profile)
            if patient_sync_id is None:
                sync = self.upsert_dcm4chee_patient_sync(
                    int(patient_record_id),
                    profile,
                    sync_status=DCM4CHEE_PATIENT_SYNC_STATUS_PENDING,
                )
                patient_sync_id = int(sync["id"])
            ack = ack or {}
            now = self._timestamp()
            with self._lock, self._connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO local_dcm4chee_patient_sync_attempts (
                        patient_sync_id, operation_type, patient_record_id, profile_name,
                        server_identity, patient_id, issuer_of_patient_id, request_url,
                        request_payload, response_payload, ack_code, ack_control_id,
                        ack_text, attempt_status, error_type, error_text, attempted_at,
                        completed_at, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        patient_sync_id,
                        operation_type,
                        int(patient_record_id),
                        identifiers["profile_name"],
                        identifiers["server_identity"],
                        identifiers["patient_id"],
                        identifiers["issuer_of_patient_id"],
                        request_url,
                        request_payload,
                        response_payload,
                        str(ack.get("code") or ""),
                        str(ack.get("controlId") or ""),
                        str(ack.get("text") or ""),
                        attempt_status,
                        error_type,
                        error_text,
                        now,
                        now if attempt_status != DCM4CHEE_PATIENT_SYNC_STATUS_PENDING else "",
                        now,
                        now,
                    ),
                )
                attempt_id = int(cursor.lastrowid)
            return self.get_dcm4chee_patient_sync_attempt(attempt_id)

    def update_dcm4chee_patient_sync_attempt_result(
            self,
            attempt_id: int,
            *,
            attempt_status: str,
            response_payload: str = "",
            ack: dict[str, str] | None = None,
            error_type: str = "",
            error_text: str = "",
        ) -> dict[str, Any]:
            ack = ack or {}
            now = self._timestamp()
            with self._lock, self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM local_dcm4chee_patient_sync_attempts WHERE id = ?",
                    (int(attempt_id),),
                ).fetchone()
                if not row:
                    raise KeyError(attempt_id)
                connection.execute(
                    """
                    UPDATE local_dcm4chee_patient_sync_attempts
                    SET response_payload = ?, ack_code = ?, ack_control_id = ?, ack_text = ?,
                        attempt_status = ?, error_type = ?, error_text = ?, completed_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        response_payload,
                        str(ack.get("code") or ""),
                        str(ack.get("controlId") or ""),
                        str(ack.get("text") or ""),
                        attempt_status,
                        error_type,
                        error_text,
                        now,
                        now,
                        int(attempt_id),
                    ),
                )
            return self.get_dcm4chee_patient_sync_attempt(attempt_id)

    def update_dcm4chee_patient_sync_from_attempt(
            self,
            patient_sync_id: int,
            attempt: dict[str, Any],
            *,
            sync_status: str,
        ) -> dict[str, Any]:
            now = self._timestamp()
            with self._lock, self._connect() as connection:
                connection.execute(
                    """
                    UPDATE local_dcm4chee_patient_syncs
                    SET sync_status = ?, last_sync_at = ?, last_attempt_id = ?,
                        last_ack_code = ?, last_ack_control_id = ?, last_ack_text = ?,
                        last_response_payload = ?, last_error_type = ?, last_error_text = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        sync_status,
                        now if sync_status == DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED else "",
                        int(attempt["id"]),
                        str((attempt.get("ack") or {}).get("code") or ""),
                        str((attempt.get("ack") or {}).get("controlId") or ""),
                        str((attempt.get("ack") or {}).get("text") or ""),
                        str(attempt.get("responsePayload") or ""),
                        str(attempt.get("errorType") or ""),
                        str(attempt.get("error") or ""),
                        now,
                        int(patient_sync_id),
                    ),
                )
            return self.get_dcm4chee_patient_sync(int(patient_sync_id))

    def get_dcm4chee_patient_sync_attempt(self, attempt_id: int) -> dict[str, Any]:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM local_dcm4chee_patient_sync_attempts WHERE id = ?",
                    (int(attempt_id),),
                ).fetchone()
                if not row:
                    raise KeyError(attempt_id)
            return project_patient_sync_attempt_dict(row)

    def list_dcm4chee_patient_sync_attempts(self, patient_record_id: int | None = None) -> list[dict[str, Any]]:
            with self._connect() as connection:
                if patient_record_id is None:
                    rows = connection.execute(
                        """
                        SELECT * FROM local_dcm4chee_patient_sync_attempts
                        ORDER BY attempted_at DESC, id DESC
                        """
                    ).fetchall()
                else:
                    rows = connection.execute(
                        """
                        SELECT * FROM local_dcm4chee_patient_sync_attempts
                        WHERE patient_record_id = ?
                        ORDER BY attempted_at DESC, id DESC
                        """,
                        (int(patient_record_id),),
                    ).fetchall()
            return [project_patient_sync_attempt_dict(row) for row in rows]
