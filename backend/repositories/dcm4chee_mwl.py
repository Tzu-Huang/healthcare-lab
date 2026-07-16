"""SQLite persistence owner for dcm4chee MWL mappings, attempts, and backfill."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager
from sqlite3 import Connection
from threading import RLock
from typing import Any

from backend.domain.statuses import (
    DCM4CHEE_MWL_OPERATION_CREATE,
    DCM4CHEE_MWL_OPERATION_VERIFY,
    DCM4CHEE_MWL_STATUS_FAILED,
    DCM4CHEE_MWL_STATUS_PENDING,
)
from backend.mappers.dicom import project_mwl_attempt, project_mwl_mapping

ConnectionFactory = Callable[[], AbstractContextManager[Connection]]
DCM4CHEE_DEFAULT_UID_ROOT = "1.2.826.0.1.3680043.10.543"


def _json_value(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return fallback

def backfill_dcm4chee_mwl_mappings(
    connection: sqlite3.Connection,
    *,
    order_default_text: str,
    create_operation: str,
    identifier_projector: Callable[..., dict[str, str]],
) -> None:
    rows = connection.execute(
        """
        SELECT a.*, o.mrn, o.order_code, o.order_code_text
        FROM local_dcm4chee_mwl_attempts a
        JOIN local_order_records o ON o.id = a.order_record_id
        WHERE NOT EXISTS (
            SELECT 1 FROM local_dcm4chee_mwl_mappings m
            WHERE m.order_record_id = a.order_record_id
        )
        AND a.id = (
            SELECT latest.id
            FROM local_dcm4chee_mwl_attempts latest
            WHERE latest.order_record_id = a.order_record_id
            ORDER BY latest.attempted_at DESC, latest.id DESC
            LIMIT 1
        )
        ORDER BY a.order_record_id
        """
    ).fetchall()
    for row in rows:
        request_payload = _json_value(row["request_payload_json"], {})
        identifiers = identifier_projector(
            request_payload,
            patient_id_default=str(row["mrn"] or "").strip(),
            issuer_default=str(row["profile_name"] or "").strip(),
            worklist_label_default=str(
                row["order_code_text"] or row["order_code"] or order_default_text
            ).strip(),
            scheduled_station_default=str(row["scheduled_station_ae_title"] or "").strip(),
        )
        completed_or_attempted = row["completed_at"] or row["attempted_at"]
        response_body = row["response_body"] or ""
        error_payload = {"responseBody": response_body} if row["error_type"] else {}
        cursor = connection.execute(
            """
            INSERT INTO local_dcm4chee_mwl_mappings (
                order_record_id, profile_name, server_identity, mwl_ae_title,
                scheduled_station_ae_title, local_dcm4chee_order_number,
                patient_id, issuer_of_patient_id, accession_number,
                requested_procedure_id, scheduled_procedure_step_id,
                study_instance_uid, worklist_label, uid_root, sync_status,
                last_sync_at, retry_count, last_attempt_id, last_http_status,
                last_response_body, last_error_type, last_error_text,
                last_error_payload_json, latest_request_payload_json,
                latest_readback_payload_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["order_record_id"],
                row["profile_name"],
                row["server_identity"],
                row["mwl_ae_title"],
                identifiers["scheduled_station_ae_title"],
                row["local_dcm4chee_order_number"],
                identifiers["patient_id"],
                identifiers["issuer_of_patient_id"],
                row["accession_number"],
                row["requested_procedure_id"],
                row["scheduled_procedure_step_id"],
                row["study_instance_uid"],
                identifiers["worklist_label"],
                row["uid_root"],
                row["attempt_status"],
                completed_or_attempted,
                max(
                    0,
                    int(
                        connection.execute(
                            """
                            SELECT COUNT(*) FROM local_dcm4chee_mwl_attempts
                            WHERE order_record_id = ?
                            """,
                            (row["order_record_id"],),
                        ).fetchone()[0]
                    )
                    - 1,
                ),
                row["id"],
                row["http_status"],
                response_body,
                row["error_type"],
                row["error_text"],
                json.dumps(error_payload, sort_keys=True),
                row["request_payload_json"] or "{}",
                "{}",
                row["created_at"],
                row["updated_at"],
            ),
        )
        mapping_id = int(cursor.lastrowid)
        connection.execute(
            """
            UPDATE local_dcm4chee_mwl_attempts
            SET mapping_id = ?, operation_type = COALESCE(NULLIF(operation_type, ''), ?)
            WHERE order_record_id = ? AND mapping_id IS NULL
            """,
            (mapping_id, create_operation, row["order_record_id"]),
        )


class Dcm4cheeMwlRepository:
    def __init__(
        self, connection_factory: ConnectionFactory, lock: RLock, *, order_loader,
        identifiers_from_payload, uid_normalizer, study_uid_builder,
        local_order_number, accession_number, requested_procedure_id,
        scheduled_procedure_step_id, timestamp_factory,
    ) -> None:
        self._connect = connection_factory
        self._lock = lock
        self._get_order_record = order_loader
        self._identifiers_from_payload = identifiers_from_payload
        self._normalize_uid_root = uid_normalizer
        self._study_uid = study_uid_builder
        self._local_order_number = local_order_number
        self._accession_number = accession_number
        self._requested_procedure_id = requested_procedure_id
        self._scheduled_procedure_step_id = scheduled_procedure_step_id
        self._timestamp = timestamp_factory

    @property
    def lock(self) -> RLock:
        return self._lock
    def upsert_dcm4chee_mwl_mapping(
        self,
        order_record_id: int,
        profile: dict[str, Any],
        *,
        uid_root: Any = DCM4CHEE_DEFAULT_UID_ROOT,
        request_payload: dict[str, Any] | None = None,
        sync_status: str = DCM4CHEE_MWL_STATUS_PENDING,
        increment_retry: bool = False,
    ) -> dict[str, Any]:
        order = self._get_order_record(order_record_id)
        identifiers = self._identifiers_from_payload(
            order,
            profile,
            uid_root=uid_root,
            payload=request_payload,
        )
        now = self._timestamp()
        request_payload_json = json.dumps(request_payload or {}, sort_keys=True)
        with self._lock, self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM local_dcm4chee_mwl_mappings WHERE order_record_id = ?",
                (int(order_record_id),),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE local_dcm4chee_mwl_mappings
                    SET profile_name = ?, server_identity = ?, mwl_ae_title = ?,
                        scheduled_station_ae_title = ?, local_dcm4chee_order_number = ?,
                        patient_id = ?, issuer_of_patient_id = ?, accession_number = ?,
                        requested_procedure_id = ?, scheduled_procedure_step_id = ?,
                        study_instance_uid = ?, worklist_label = ?, uid_root = ?,
                        sync_status = ?, retry_count = retry_count + ?,
                        latest_request_payload_json = CASE WHEN ? != '{}' THEN ? ELSE latest_request_payload_json END,
                        updated_at = ?
                    WHERE order_record_id = ?
                    """,
                    (
                        identifiers["profile_name"],
                        identifiers["server_identity"],
                        identifiers["mwl_ae_title"],
                        identifiers["scheduled_station_ae_title"],
                        identifiers["local_dcm4chee_order_number"],
                        identifiers["patient_id"],
                        identifiers["issuer_of_patient_id"],
                        identifiers["accession_number"],
                        identifiers["requested_procedure_id"],
                        identifiers["scheduled_procedure_step_id"],
                        identifiers["study_instance_uid"],
                        identifiers["worklist_label"],
                        identifiers["uid_root"],
                        sync_status,
                        1 if increment_retry else 0,
                        request_payload_json,
                        request_payload_json,
                        now,
                        int(order_record_id),
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO local_dcm4chee_mwl_mappings (
                        order_record_id, profile_name, server_identity, mwl_ae_title,
                        scheduled_station_ae_title, local_dcm4chee_order_number,
                        patient_id, issuer_of_patient_id, accession_number,
                        requested_procedure_id, scheduled_procedure_step_id,
                        study_instance_uid, worklist_label, uid_root, sync_status,
                        retry_count, latest_request_payload_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(order_record_id),
                        identifiers["profile_name"],
                        identifiers["server_identity"],
                        identifiers["mwl_ae_title"],
                        identifiers["scheduled_station_ae_title"],
                        identifiers["local_dcm4chee_order_number"],
                        identifiers["patient_id"],
                        identifiers["issuer_of_patient_id"],
                        identifiers["accession_number"],
                        identifiers["requested_procedure_id"],
                        identifiers["scheduled_procedure_step_id"],
                        identifiers["study_instance_uid"],
                        identifiers["worklist_label"],
                        identifiers["uid_root"],
                        sync_status,
                        1 if increment_retry else 0,
                        request_payload_json,
                        now,
                        now,
                    ),
                )
        return self.get_dcm4chee_mwl_mapping_for_order(int(order_record_id))
    def get_dcm4chee_mwl_mapping_for_order(self, order_record_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_dcm4chee_mwl_mappings WHERE order_record_id = ?",
                (int(order_record_id),),
            ).fetchone()
        return project_mwl_mapping(row) if row else None

    def find_dcm4chee_mwl_mapping_for_reconciliation(
        self,
        *,
        study_instance_uid: str = "",
        accession_number: str = "",
        requested_procedure_id: str = "",
        scheduled_procedure_step_id: str = "",
        profile_name: str = "",
        server_identity: str = "",
    ) -> dict[str, Any] | None:
        study_uid = str(study_instance_uid or "").strip()
        accession = str(accession_number or "").strip()
        requested_procedure = str(requested_procedure_id or "").strip()
        sps_id = str(scheduled_procedure_step_id or "").strip()
        profile = str(profile_name or "").strip()
        server = str(server_identity or "").strip()
        with self._connect() as connection:
            if study_uid:
                row = connection.execute(
                    """
                    SELECT * FROM local_dcm4chee_mwl_mappings
                    WHERE study_instance_uid = ?
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 1
                    """,
                    (study_uid,),
                ).fetchone()
                if row:
                    return project_mwl_mapping(row)
            if accession and profile and server:
                row = connection.execute(
                    """
                    SELECT * FROM local_dcm4chee_mwl_mappings
                    WHERE accession_number = ? AND profile_name = ? AND server_identity = ?
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 1
                    """,
                    (accession, profile, server),
                ).fetchone()
                if row:
                    return project_mwl_mapping(row)
            if requested_procedure and sps_id and profile and server:
                row = connection.execute(
                    """
                    SELECT * FROM local_dcm4chee_mwl_mappings
                    WHERE requested_procedure_id = ?
                    AND scheduled_procedure_step_id = ?
                    AND profile_name = ?
                    AND server_identity = ?
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 1
                    """,
                    (requested_procedure, sps_id, profile, server),
                ).fetchone()
                if row:
                    return project_mwl_mapping(row)
        return None

    def list_dcm4chee_mwl_mappings_for_patient(self, patient_record_id: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT m.* FROM local_dcm4chee_mwl_mappings m
                JOIN local_order_records o ON o.id = m.order_record_id
                WHERE o.patient_record_id = ?
                ORDER BY m.updated_at DESC, m.id DESC
                """,
                (int(patient_record_id),),
            ).fetchall()
        return [project_mwl_mapping(row) for row in rows]

    def load_for_orders(self, order_record_ids: list[int]) -> dict[int, dict[str, Any]]:
        ids = [int(value) for value in order_record_ids]
        result = {record_id: {"attempt": None, "mapping": None} for record_id in ids}
        if not ids:
            return result
        placeholders = ", ".join("?" for _ in ids)
        with self._connect() as connection:
            attempt_rows = connection.execute(
                f"""SELECT * FROM local_dcm4chee_mwl_attempts
                    WHERE order_record_id IN ({placeholders})
                    ORDER BY attempted_at DESC, id DESC""",
                ids,
            ).fetchall()
            mapping_rows = connection.execute(
                f"SELECT * FROM local_dcm4chee_mwl_mappings WHERE order_record_id IN ({placeholders})",
                ids,
            ).fetchall()
        for row in attempt_rows:
            item = result[int(row["order_record_id"])]
            if item["attempt"] is None:
                item["attempt"] = project_mwl_attempt(row)
        for row in mapping_rows:
            result[int(row["order_record_id"])]["mapping"] = project_mwl_mapping(row)
        return result
    def create_dcm4chee_mwl_attempt(
        self,
        order_record_id: int,
        profile: dict[str, Any],
        *,
        uid_root: Any = DCM4CHEE_DEFAULT_UID_ROOT,
        request_url: str = "",
        request_payload: dict[str, Any] | None = None,
        attempt_status: str = DCM4CHEE_MWL_STATUS_PENDING,
        error_type: str = "",
        error_text: str = "",
        http_status: int | None = None,
        response_body: str = "",
        operation_type: str = DCM4CHEE_MWL_OPERATION_CREATE,
        mapping_id: int | None = None,
    ) -> dict[str, Any]:
        order = self._get_order_record(order_record_id)
        if request_payload is None:
            raise ValueError("DICOM MWL attempt request payload is required.")
        generated_payload = request_payload
        order_id = int(order["id"])
        mwl = profile.get("mwl") if isinstance(profile.get("mwl"), dict) else {}
        dimse = profile.get("dimse") if isinstance(profile.get("dimse"), dict) else {}
        uid_root_text = self._normalize_uid_root(uid_root)
        identifiers = self._identifiers_from_payload(
            order, profile, uid_root=uid_root, payload=generated_payload
        )
        now = self._timestamp()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO local_dcm4chee_mwl_attempts (
                    mapping_id, operation_type, order_record_id, profile_name,
                    server_identity, mwl_ae_title, scheduled_station_ae_title, local_dcm4chee_order_number,
                    accession_number, requested_procedure_id,
                    scheduled_procedure_step_id, study_instance_uid, uid_root,
                    request_url, request_payload_json, http_status, response_body,
                    attempt_status, error_type, error_text, attempted_at,
                    completed_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mapping_id,
                    operation_type,
                    order_id,
                    str(profile.get("profileName") or "").strip(),
                    str(dimse.get("calledAETitle") or mwl.get("aeTitle") or "").strip(),
                    str(mwl.get("aeTitle") or "").strip(),
                    identifiers["scheduled_station_ae_title"],
                    self._local_order_number(order_id),
                    identifiers["accession_number"],
                    identifiers["requested_procedure_id"],
                    identifiers["scheduled_procedure_step_id"],
                    identifiers["study_instance_uid"],
                    uid_root_text,
                    request_url,
                    json.dumps(generated_payload, sort_keys=True),
                    http_status,
                    response_body,
                    attempt_status,
                    error_type,
                    error_text,
                    now,
                    now if attempt_status != DCM4CHEE_MWL_STATUS_PENDING else "",
                    now,
                    now,
                ),
            )
            attempt_id = int(cursor.lastrowid)
        return self.get_dcm4chee_mwl_attempt(attempt_id)
    def update_dcm4chee_mwl_attempt_result(
        self,
        attempt_id: int,
        *,
        attempt_status: str,
        http_status: int | None = None,
        response_body: str = "",
        error_type: str = "",
        error_text: str = "",
    ) -> dict[str, Any]:
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM local_dcm4chee_mwl_attempts WHERE id = ?",
                (attempt_id,),
            ).fetchone()
            if not row:
                raise KeyError(attempt_id)
            connection.execute(
                """
                UPDATE local_dcm4chee_mwl_attempts
                SET attempt_status = ?, http_status = ?, response_body = ?,
                    error_type = ?, error_text = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    attempt_status,
                    http_status,
                    response_body,
                    error_type,
                    error_text,
                    timestamp,
                    timestamp,
                    attempt_id,
                ),
            )
        return self.get_dcm4chee_mwl_attempt(attempt_id)

    def get_dcm4chee_mwl_attempt(self, attempt_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_dcm4chee_mwl_attempts WHERE id = ?",
                (attempt_id,),
            ).fetchone()
            if not row:
                raise KeyError(attempt_id)
        return project_mwl_attempt(row)

    def list_dcm4chee_mwl_attempts(self, order_record_id: int | None = None) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if order_record_id is None:
                rows = connection.execute(
                    """
                    SELECT * FROM local_dcm4chee_mwl_attempts
                    ORDER BY attempted_at DESC, id DESC
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM local_dcm4chee_mwl_attempts
                    WHERE order_record_id = ?
                    ORDER BY attempted_at DESC, id DESC
                    """,
                    (order_record_id,),
                ).fetchall()
        return [project_mwl_attempt(row) for row in rows]
    def create_dcm4chee_mwl_verification_attempt(
        self,
        order_record_id: int,
        mapping: dict[str, Any],
        *,
        request_url: str,
        query_criteria: dict[str, str],
        attempt_status: str = DCM4CHEE_MWL_STATUS_PENDING,
        error_type: str = "",
        error_text: str = "",
        http_status: int | None = None,
        response_body: str = "",
    ) -> dict[str, Any]:
        now = self._timestamp()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO local_dcm4chee_mwl_attempts (
                    mapping_id, operation_type, order_record_id, profile_name,
                    server_identity, mwl_ae_title, scheduled_station_ae_title, local_dcm4chee_order_number,
                    accession_number, requested_procedure_id,
                    scheduled_procedure_step_id, study_instance_uid, uid_root,
                    request_url, request_payload_json, http_status, response_body,
                    attempt_status, error_type, error_text, attempted_at,
                    completed_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(mapping["id"]) if mapping.get("id") else None,
                    DCM4CHEE_MWL_OPERATION_VERIFY,
                    int(order_record_id),
                    str(mapping.get("profileName") or "").strip(),
                    str(mapping.get("serverIdentity") or "").strip(),
                    str(mapping.get("mwlAETitle") or "").strip(),
                    str(mapping.get("scheduledStationAETitle") or "").strip(),
                    str(mapping.get("localDcm4cheeOrderNumber") or "").strip(),
                    str(mapping.get("accessionNumber") or "").strip(),
                    str(mapping.get("requestedProcedureId") or "").strip(),
                    str(mapping.get("scheduledProcedureStepId") or "").strip(),
                    str(mapping.get("studyInstanceUid") or "").strip(),
                    str(mapping.get("uidRoot") or "").strip(),
                    request_url,
                    json.dumps(query_criteria, sort_keys=True),
                    http_status,
                    response_body,
                    attempt_status,
                    error_type,
                    error_text,
                    now,
                    now if attempt_status != DCM4CHEE_MWL_STATUS_PENDING else "",
                    now,
                    now,
                ),
            )
            attempt_id = int(cursor.lastrowid)
        return self.get_dcm4chee_mwl_attempt(attempt_id)

    def update_dcm4chee_mwl_verification_result(
        self,
        order_record_id: int,
        *,
        attempt_id: int,
        verification_status: str,
        method: str,
        query_criteria: dict[str, Any],
        match_payload: dict[str, Any] | None = None,
        error_type: str = "",
        error_text: str = "",
        error_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE local_dcm4chee_mwl_mappings
                SET verification_status = ?,
                    last_verification_at = ?,
                    last_verification_method = ?,
                    last_verification_attempt_id = ?,
                    last_verification_query_json = ?,
                    last_verification_match_json = ?,
                    last_verification_error_type = ?,
                    last_verification_error_text = ?,
                    last_verification_error_payload_json = ?,
                    updated_at = ?
                WHERE order_record_id = ?
                """,
                (
                    verification_status,
                    timestamp,
                    method,
                    int(attempt_id),
                    json.dumps(query_criteria, sort_keys=True),
                    json.dumps(match_payload or {}, sort_keys=True),
                    error_type,
                    error_text,
                    json.dumps(error_payload or {}, sort_keys=True),
                    timestamp,
                    int(order_record_id),
                ),
            )
        return self.get_dcm4chee_mwl_mapping_for_order(int(order_record_id))
    def create_dcm4chee_mwl_profile_failure_attempt(
        self,
        order_record_id: int,
        profile: dict[str, Any],
        *,
        uid_root: Any = DCM4CHEE_DEFAULT_UID_ROOT,
        request_url: str = "",
        diagnostics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        order = self._get_order_record(order_record_id)
        order_id = int(order["id"])
        mwl = profile.get("mwl") if isinstance(profile.get("mwl"), dict) else {}
        dimse = profile.get("dimse") if isinstance(profile.get("dimse"), dict) else {}
        uid_root_text = self._normalize_uid_root(uid_root)
        mapping = self.upsert_dcm4chee_mwl_mapping(
            order_id,
            profile,
            uid_root=uid_root_text,
            sync_status=DCM4CHEE_MWL_STATUS_FAILED,
        )
        study_uid = self._study_uid(
            uid_root_text,
            order_record_id=order_id,
            timestamp=str(order.get("requestedAt") or ""),
        )
        now = self._timestamp()
        diagnostic_payload = diagnostics or {}
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO local_dcm4chee_mwl_attempts (
                    mapping_id, operation_type, order_record_id, profile_name,
                    server_identity, mwl_ae_title, scheduled_station_ae_title, local_dcm4chee_order_number,
                    accession_number, requested_procedure_id,
                    scheduled_procedure_step_id, study_instance_uid, uid_root,
                    request_url, request_payload_json, http_status, response_body,
                    attempt_status, error_type, error_text, attempted_at,
                    completed_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(mapping["id"]),
                    DCM4CHEE_MWL_OPERATION_CREATE,
                    order_id,
                    str(profile.get("profileName") or "").strip(),
                    str(dimse.get("calledAETitle") or mwl.get("aeTitle") or "").strip(),
                    str(mwl.get("aeTitle") or "").strip(),
                    str(mwl.get("defaultScheduledStationAETitle") or "").strip(),
                    self._local_order_number(order_id),
                    self._accession_number(order_id),
                    self._requested_procedure_id(order_id),
                    self._scheduled_procedure_step_id(order_id),
                    study_uid,
                    uid_root_text,
                    request_url,
                    "{}",
                    None,
                    json.dumps(diagnostic_payload, sort_keys=True),
                    DCM4CHEE_MWL_STATUS_FAILED,
                    "profile_invalid",
                    str(diagnostic_payload.get("summary") or "dcm4chee profile is incomplete or invalid."),
                    now,
                    now,
                    now,
                    now,
                ),
            )
            attempt_id = int(cursor.lastrowid)
        self.update_dcm4chee_mwl_mapping_from_attempt(
            order_id,
            attempt_id=attempt_id,
            sync_status=DCM4CHEE_MWL_STATUS_FAILED,
            response_body=json.dumps(diagnostic_payload, sort_keys=True),
            error_type="profile_invalid",
            error_text=str(diagnostic_payload.get("summary") or "dcm4chee profile is incomplete or invalid."),
            error_payload=diagnostic_payload,
        )
        return self.get_dcm4chee_mwl_attempt(attempt_id)

    def update_dcm4chee_mwl_mapping_from_attempt(
        self,
        order_record_id: int,
        *,
        attempt_id: int | None,
        sync_status: str,
        http_status: int | None = None,
        response_body: str = "",
        error_type: str = "",
        error_text: str = "",
        error_payload: dict[str, Any] | None = None,
        readback_payload: dict[str, Any] | list[Any] | None = None,
        identifiers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        identifiers = {key: value for key, value in (identifiers or {}).items() if value}
        assignments = []
        values: list[Any] = []
        for key, column in (
            ("patient_id", "patient_id"),
            ("issuer_of_patient_id", "issuer_of_patient_id"),
            ("accession_number", "accession_number"),
            ("requested_procedure_id", "requested_procedure_id"),
            ("scheduled_procedure_step_id", "scheduled_procedure_step_id"),
            ("study_instance_uid", "study_instance_uid"),
            ("worklist_label", "worklist_label"),
            ("scheduled_station_ae_title", "scheduled_station_ae_title"),
        ):
            if identifiers.get(key):
                assignments.append(f"{column} = ?")
                values.append(identifiers[key])
        timestamp = self._timestamp()
        readback_json = json.dumps(readback_payload or {}, sort_keys=True)
        error_payload_json = json.dumps(error_payload or {}, sort_keys=True)
        assignments.extend(
            [
                "sync_status = ?",
                "last_sync_at = ?",
                "last_attempt_id = ?",
                "last_http_status = ?",
                "last_response_body = ?",
                "last_error_type = ?",
                "last_error_text = ?",
                "last_error_payload_json = ?",
                "latest_readback_payload_json = CASE WHEN ? != '{}' THEN ? ELSE latest_readback_payload_json END",
                "updated_at = ?",
            ]
        )
        values.extend(
            [
                sync_status,
                timestamp,
                attempt_id,
                http_status,
                response_body,
                error_type,
                error_text,
                error_payload_json,
                readback_json,
                readback_json,
                timestamp,
                int(order_record_id),
            ]
        )
        with self._lock, self._connect() as connection:
            connection.execute(
                f"""
                UPDATE local_dcm4chee_mwl_mappings
                SET {", ".join(assignments)}
                WHERE order_record_id = ?
                """,
                values,
            )
        return self.get_dcm4chee_mwl_mapping_for_order(int(order_record_id))
