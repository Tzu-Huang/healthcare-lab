"""SQLite owner for local FHIR workflow records and sync attempts."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from sqlite3 import Connection
from threading import RLock
from typing import Any

from backend.domain.fhir_ledger import (
    FHIR_RESOURCE_DEPENDENCY_ORDER, clean_text, list_resource_mappings,
    normalize_record_payload, record_number,
)
from backend.mappers.fhir import project_sync_attempt, project_workflow_record
from backend.domain.statuses import (
    FHIR_SYNC_STATUS_FAILED, FHIR_SYNC_STATUS_PENDING,
    FHIR_SYNC_STATUS_SYNCED, FHIR_SYNC_STATUS_SYNCING,
)

ConnectionFactory = Callable[[], AbstractContextManager[Connection]]


def load_fhir_sources(
    connection_factory: ConnectionFactory,
    record_ids: list[int],
    *,
    source_type: str,
    resource_type: str,
    projector: Callable[[Any], dict[str, Any]] = project_workflow_record,
) -> dict[int, dict[str, Any]]:
    """Batch-load FHIR projections for compatibility enrichment consumers."""
    if not record_ids:
        return {}
    placeholders = ", ".join("?" for _ in record_ids)
    with connection_factory() as connection:
        rows = connection.execute(
            f"""SELECT * FROM local_fhir_workflow_records
                WHERE local_source_type = ? AND local_source_id IN ({placeholders})
                AND resource_type = ?""",
            [source_type, *[str(item) for item in record_ids], resource_type],
        ).fetchall()
    return {int(row["local_source_id"]): projector(row) for row in rows}


class FhirLedgerRepository:
    def __init__(
        self, connection_factory: ConnectionFactory, lock: RLock, *,
        timestamp_factory: Callable[[], str],
        payload_normalizer: Callable[[dict[str, Any]], dict[str, Any]] = normalize_record_payload,
        workflow_projector: Callable[[Any], dict[str, Any]] = project_workflow_record,
        attempt_projector: Callable[[Any], dict[str, Any]] = project_sync_attempt,
    ) -> None:
        self._connect = connection_factory
        self._lock = lock
        self._timestamp = timestamp_factory
        self._normalize = payload_normalizer
        self._project_workflow = workflow_projector
        self._project_attempt = attempt_projector

    @property
    def lock(self) -> RLock:
        return self._lock

    def list_fhir_resource_mappings(self) -> list[dict[str, Any]]:
        return list_resource_mappings()

    def create_fhir_workflow_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            # Normalize within the transaction so an injected collaborator failure cannot expose writes.
            values = self._normalize(payload)
            existing = connection.execute(
                """SELECT * FROM local_fhir_workflow_records
                   WHERE resource_type = ? AND identifier_system = ? AND identifier_value = ?""",
                (values["resource_type"], values["identifier_system"], values["identifier_value"]),
            ).fetchone()
            if existing:
                changed = (
                    existing["resource_json"] != values["resource_json"]
                    or existing["dependency_json"] != values["dependency_json"]
                )
                connection.execute(
                    """UPDATE local_fhir_workflow_records
                       SET local_source_type = ?, local_source_id = ?, resource_json = ?,
                           dependency_json = ?, sync_status = ?, updated_at = ?,
                           sync_error = CASE WHEN ? THEN '' ELSE sync_error END,
                           operation_outcome_json = CASE WHEN ? THEN '{}' ELSE operation_outcome_json END,
                           sync_started_at = CASE WHEN ? THEN '' ELSE sync_started_at END
                       WHERE id = ?""",
                    (values["local_source_type"], values["local_source_id"], values["resource_json"],
                     values["dependency_json"], FHIR_SYNC_STATUS_PENDING if changed else existing["sync_status"],
                     timestamp, int(changed), int(changed), int(changed), existing["id"]),
                )
                record_id = int(existing["id"])
            else:
                cursor = connection.execute(
                    """INSERT INTO local_fhir_workflow_records (
                           local_fhir_record_number, local_source_type, local_source_id,
                           resource_type, identifier_system, identifier_value, resource_json,
                           dependency_json, sync_status, created_at, updated_at
                       ) VALUES ('', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (values["local_source_type"], values["local_source_id"], values["resource_type"],
                     values["identifier_system"], values["identifier_value"], values["resource_json"],
                     values["dependency_json"], FHIR_SYNC_STATUS_PENDING, timestamp, timestamp),
                )
                record_id = int(cursor.lastrowid)
                connection.execute(
                    "UPDATE local_fhir_workflow_records SET local_fhir_record_number = ? WHERE id = ?",
                    (record_number(record_id), record_id),
                )
        return self.get_fhir_workflow_record(record_id)

    def list_fhir_workflow_records(self, sync_status: str = "") -> list[dict[str, Any]]:
        with self._connect() as connection:
            if sync_status:
                rows = connection.execute(
                    "SELECT * FROM local_fhir_workflow_records WHERE sync_status = ? ORDER BY id DESC",
                    (sync_status,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM local_fhir_workflow_records ORDER BY id DESC"
                ).fetchall()
        return [self._project_workflow(row) for row in rows]

    def get_fhir_workflow_record(self, record_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_fhir_workflow_records WHERE id = ?", (record_id,)
            ).fetchone()
        if not row:
            raise KeyError(record_id)
        return self._project_workflow(row)

    def get_fhir_workflow_record_by_identifier(
        self, *, resource_type: str, identifier_system: str, identifier_value: str,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM local_fhir_workflow_records
                   WHERE resource_type = ? AND identifier_system = ? AND identifier_value = ?""",
                (resource_type, identifier_system, identifier_value),
            ).fetchone()
        if not row:
            raise KeyError(identifier_value)
        return self._project_workflow(row)

    def mark_fhir_syncing(self, record_id: int) -> dict[str, Any]:
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            self._require_record(connection, record_id)
            connection.execute(
                """UPDATE local_fhir_workflow_records
                   SET sync_status = ?, sync_started_at = ?, sync_error = '',
                       operation_outcome_json = '{}', updated_at = ? WHERE id = ?""",
                (FHIR_SYNC_STATUS_SYNCING, timestamp, timestamp, record_id),
            )
        return self.get_fhir_workflow_record(record_id)

    def mark_fhir_sync_success(
        self, record_id: int, *, medplum_resource_id: str,
        medplum_resource_reference: str = "",
    ) -> dict[str, Any]:
        timestamp = self._timestamp()
        resource_id = clean_text(medplum_resource_id, "medplumResourceId", required=True)
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT resource_type FROM local_fhir_workflow_records WHERE id = ?", (record_id,)
            ).fetchone()
            if not row:
                raise KeyError(record_id)
            reference = medplum_resource_reference.strip() if medplum_resource_reference else f"{row['resource_type']}/{resource_id}"
            connection.execute(
                """UPDATE local_fhir_workflow_records
                   SET medplum_resource_id = ?, medplum_resource_reference = ?,
                       sync_status = ?, sync_error = '', operation_outcome_json = '{}',
                       last_sync_at = ?, sync_started_at = '', updated_at = ? WHERE id = ?""",
                (resource_id, reference, FHIR_SYNC_STATUS_SYNCED, timestamp, timestamp, record_id),
            )
        return self.get_fhir_workflow_record(record_id)

    def mark_fhir_sync_failure(
        self, record_id: int, *, error_text: str,
        operation_outcome: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            self._require_record(connection, record_id)
            connection.execute(
                """UPDATE local_fhir_workflow_records
                   SET sync_status = ?, sync_error = ?, operation_outcome_json = ?,
                       sync_started_at = '', updated_at = ? WHERE id = ?""",
                (FHIR_SYNC_STATUS_FAILED, str(error_text or "").strip(),
                 json.dumps(operation_outcome or {}, sort_keys=True), timestamp, record_id),
            )
        return self.get_fhir_workflow_record(record_id)

    def record_fhir_sync_attempt(
        self, record_id: int, *, method: str, request_url: str,
        request_payload: dict[str, Any] | None = None, http_status: int | None = None,
        response_payload: dict[str, Any] | None = None,
        operation_outcome: dict[str, Any] | None = None, error_text: str = "",
    ) -> dict[str, Any]:
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            self._require_record(connection, record_id)
            cursor = connection.execute(
                """INSERT INTO local_fhir_sync_attempts (
                       fhir_record_id, method, request_url, request_payload_json,
                       http_status, response_payload_json, operation_outcome_json,
                       error_text, attempted_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (record_id, method.strip().upper(), request_url.strip(),
                 json.dumps(request_payload or {}, sort_keys=True), http_status,
                 json.dumps(response_payload or {}, sort_keys=True),
                 json.dumps(operation_outcome or {}, sort_keys=True),
                 str(error_text or "").strip(), timestamp),
            )
            row = connection.execute(
                "SELECT * FROM local_fhir_sync_attempts WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return self._project_attempt(row)

    def list_fhir_sync_attempts(self, record_id: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM local_fhir_sync_attempts
                   WHERE fhir_record_id = ? ORDER BY id DESC""", (record_id,)
            ).fetchall()
        return [self._project_attempt(row) for row in rows]

    def ordered_fhir_workflow_records(self, record_ids: list[int]) -> list[dict[str, Any]]:
        return sorted(
            [self.get_fhir_workflow_record(record_id) for record_id in record_ids],
            key=lambda item: (FHIR_RESOURCE_DEPENDENCY_ORDER.get(item["resourceType"], 999), int(item["id"])),
        )

    def load_for_patients(self, record_ids: list[int]) -> dict[int, dict[str, Any]]:
        rows = self._load_sources(record_ids, "local_patient_records", "Patient")
        return {int(row["local_source_id"]): self._project_workflow(row) for row in rows}

    def load_for_orders(self, record_ids: list[int]) -> dict[int, dict[str, dict[str, Any]]]:
        rows = self._load_sources(record_ids, "local_order_records", "ServiceRequest")
        result: dict[int, dict[str, dict[str, Any]]] = {record_id: {} for record_id in record_ids}
        for row in rows:
            result[int(row["local_source_id"])][row["resource_type"]] = self._project_workflow(row)
        return result

    def _load_sources(self, record_ids: list[int], source_type: str, resource_type: str) -> list[Any]:
        if not record_ids:
            return []
        placeholders = ", ".join("?" for _ in record_ids)
        with self._connect() as connection:
            return connection.execute(
                f"""SELECT * FROM local_fhir_workflow_records
                    WHERE local_source_type = ? AND local_source_id IN ({placeholders})
                    AND resource_type = ?""",
                [source_type, *[str(item) for item in record_ids], resource_type],
            ).fetchall()

    @staticmethod
    def _require_record(connection: Connection, record_id: int) -> None:
        if not connection.execute(
            "SELECT id FROM local_fhir_workflow_records WHERE id = ?", (record_id,)
        ).fetchone():
            raise KeyError(record_id)
