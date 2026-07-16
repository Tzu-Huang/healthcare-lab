"""SQLite persistence for inbound OIE result records."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from sqlite3 import Connection
from threading import RLock
from typing import Any

from backend.mappers.oie import project_result

ConnectionFactory = Callable[[], AbstractContextManager[Connection]]


class OieRepository:
    def __init__(self, connection_factory: ConnectionFactory, lock: RLock, *,
                 timestamp_factory: Callable[[], str], patient_protocol: str,
                 order_protocol: str) -> None:
        self._connect = connection_factory
        self._lock = lock
        self._timestamp = timestamp_factory
        self._patient_protocol = patient_protocol
        self._order_protocol = order_protocol

    @property
    def lock(self) -> RLock:
        return self._lock

    def record_oie_result(self, payload_hl7: str, parsed: dict[str, str]) -> dict[str, Any]:
        timestamp = self._timestamp()
        message_control_id = str(parsed.get("messageControlId") or "").strip()
        message_type = str(parsed.get("messageType") or "").strip()
        patient_mrn = str(parsed.get("patientMrn") or "").strip()
        placer = str(parsed.get("placerOrderNumber") or "").strip()
        filler = str(parsed.get("fillerOrderNumber") or "").strip()
        with self._lock, self._connect() as connection:
            if message_control_id:
                duplicate = connection.execute(
                    "SELECT * FROM oie_result_records WHERE message_control_id = ?",
                    (message_control_id,),
                ).fetchone()
                if duplicate:
                    item = project_result(duplicate)
                    item.update(duplicate=True, duplicateOfId=duplicate["id"])
                    return item
            patient = None
            if patient_mrn:
                patient = connection.execute(
                    """SELECT * FROM local_patient_records
                    WHERE mrn = ? AND protocol_version = ? ORDER BY id DESC LIMIT 1""",
                    (patient_mrn, self._patient_protocol),
                ).fetchone()
            order = None
            if patient and (placer or filler):
                order = connection.execute(
                    """SELECT * FROM local_order_records
                    WHERE patient_record_id = ? AND protocol_version = ? AND (
                        (? != '' AND placer_order_number = ?)
                        OR (? != '' AND filler_order_number = ?)
                        OR (? != '' AND local_order_number = ?)
                    ) ORDER BY id DESC LIMIT 1""",
                    (patient["id"], self._order_protocol, placer, placer,
                     filler, filler, filler, filler),
                ).fetchone()
            match_status = "order-matched" if order else "patient-only" if patient else "unmatched-patient"
            cursor = connection.execute(
                """INSERT INTO oie_result_records (
                    message_control_id, message_type, patient_mrn, placer_order_number,
                    filler_order_number, matched_patient_record_id, matched_order_record_id,
                    match_status, duplicate_of_id, parse_status, error_text, payload_hl7,
                    received_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 'accepted', '', ?, ?, ?, ?)""",
                (message_control_id, message_type, patient_mrn, placer, filler,
                 patient["id"] if patient else None, order["id"] if order else None,
                 match_status, payload_hl7, timestamp, timestamp, timestamp),
            )
            row = connection.execute(
                "SELECT * FROM oie_result_records WHERE id = ?", (int(cursor.lastrowid),)
            ).fetchone()
        return project_result(row)

    def record_oie_result_error(self, payload_hl7: str, message_type: str,
                                error_text: str) -> dict[str, Any]:
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO oie_result_records (
                    message_control_id, message_type, patient_mrn, placer_order_number,
                    filler_order_number, matched_patient_record_id, matched_order_record_id,
                    match_status, duplicate_of_id, parse_status, error_text, payload_hl7,
                    received_at, created_at, updated_at
                ) VALUES ('', ?, '', '', '', NULL, NULL, 'unmatched-patient', NULL,
                    'error', ?, ?, ?, ?, ?)""",
                (message_type, error_text, payload_hl7, timestamp, timestamp, timestamp),
            )
            row = connection.execute(
                "SELECT * FROM oie_result_records WHERE id = ?", (int(cursor.lastrowid),)
            ).fetchone()
        return project_result(row)

    def list_oie_results(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM oie_result_records ORDER BY received_at DESC, id DESC"
            ).fetchall()
        return [project_result(row) for row in rows]
