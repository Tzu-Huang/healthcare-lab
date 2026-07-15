"""SQLite persistence owner for dcm4chee result records and refresh snapshots."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager
from sqlite3 import Connection
from threading import RLock
from typing import Any

from backend.domain.dicom import reconcile_result_metadata
from backend.domain.errors import SimulatorValidationError
from backend.domain.statuses import DCM4CHEE_RESULT_STATUS_UNLINKED

ConnectionFactory = Callable[[], AbstractContextManager[Connection]]


def _json_value(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return fallback

def project_result_record(row: sqlite3.Row) -> dict[str, Any]:
    raw_metadata = _json_value(row["raw_metadata_json"], {})
    diagnostic = _json_value(row["diagnostic_payload_json"], {})
    artifact = raw_metadata.get("artifact") if isinstance(raw_metadata.get("artifact"), dict) else {}
    return {
        "id": row["id"],
        "resultKey": row["result_key"],
        "patientRecordId": row["patient_record_id"],
        "orderRecordId": row["order_record_id"],
        "mappingId": row["mapping_id"],
        "profileName": row["profile_name"],
        "serverIdentity": row["server_identity"],
        "sourceAETitle": row["source_ae_title"],
        "studyInstanceUid": row["study_instance_uid"],
        "seriesInstanceUid": row["series_instance_uid"],
        "sopInstanceUid": row["sop_instance_uid"],
        "accessionNumber": row["accession_number"],
        "patientId": row["patient_id"],
        "issuerOfPatientId": row["issuer_of_patient_id"],
        "requestedProcedureId": row["requested_procedure_id"],
        "scheduledProcedureStepId": row["scheduled_procedure_step_id"],
        "modality": row["modality"],
        "studyDateTime": row["study_datetime"],
        "seriesDateTime": row["series_datetime"],
        "instanceDateTime": row["instance_datetime"],
        "viewerUrl": row["viewer_url"],
        "studyRetrieveUrl": row["study_retrieve_url"],
        "seriesRetrieveUrl": row["series_retrieve_url"],
        "instanceRetrieveUrl": row["instance_retrieve_url"],
        "reconciliationStatus": row["reconciliation_status"],
        "matchMethod": row["match_method"],
        "matchStrength": row["match_strength"],
        "queryUrl": row["query_url"],
        "queryPayload": _json_value(row["query_payload_json"], {}),
        "diagnostic": diagnostic,
        "rawMetadata": raw_metadata,
        "source": raw_metadata.get("source", "") if isinstance(raw_metadata, dict) else "",
        "sourceType": raw_metadata.get("type", "") if isinstance(raw_metadata, dict) else "",
        "artifact": artifact,
        "refreshGeneration": row["refresh_generation"] if "refresh_generation" in row.keys() else "",
        "firstSeenAt": row["first_seen_at"],
        "lastRefreshedAt": row["last_refreshed_at"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        }


class Dcm4cheeResultRepository:
    def __init__(
        self, connection_factory: ConnectionFactory, lock: RLock, *, mwl_mapping_loader,
        profile_identity, link_builder, result_key_builder, timestamp_factory,
    ) -> None:
        self._connect = connection_factory
        self._lock = lock
        self._load_mwl_mappings = mwl_mapping_loader
        self._profile_identity = profile_identity
        self._build_links = link_builder
        self._result_key = result_key_builder
        self._timestamp = timestamp_factory

    @property
    def lock(self) -> RLock:
        return self._lock

    def _reconcile_result_metadata(
        self, metadata: dict[str, str], *, patient_record_id: int | None = None,
        profile_name: str = "", server_identity: str = "",
    ) -> dict[str, Any]:
        mappings = self._load_mwl_mappings(int(patient_record_id)) if patient_record_id is not None else []
        return reconcile_result_metadata(
            metadata, mappings, profile_name=profile_name, server_identity=server_identity
        )

    def reconcile_dcm4chee_result_metadata(self, *args, **kwargs) -> dict[str, Any]:
        return self._reconcile_result_metadata(*args, **kwargs)
    def upsert_dcm4chee_result_record(
        self,
        metadata: dict[str, str],
        profile: dict[str, Any],
        *,
        patient_record_id: int | None = None,
        query_url: str = "",
        query_payload: dict[str, Any] | None = None,
        raw_metadata: dict[str, Any] | None = None,
        refresh_generation: str = "",
    ) -> dict[str, Any]:
        profile_name, server_identity, source_ae_title = self._profile_identity(profile)
        reconciliation = self._reconcile_result_metadata(
            metadata,
            patient_record_id=patient_record_id,
            profile_name=profile_name,
            server_identity=server_identity,
        )
        mapping = reconciliation.get("mapping") or {}
        links = self._build_links(profile, metadata)
        result_key = self._result_key(
            profile_name=profile_name,
            server_identity=server_identity,
            patient_record_id=patient_record_id,
            status=str(reconciliation.get("status") or ""),
            study_instance_uid=metadata.get("study_instance_uid", ""),
            series_instance_uid=metadata.get("series_instance_uid", ""),
            sop_instance_uid=metadata.get("sop_instance_uid", ""),
            accession_number=metadata.get("accession_number", ""),
            requested_procedure_id=metadata.get("requested_procedure_id", ""),
            scheduled_procedure_step_id=metadata.get("scheduled_procedure_step_id", ""),
        )
        now = self._timestamp()
        values = {
            "patient_record_id": int(patient_record_id) if patient_record_id is not None else None,
            "order_record_id": int(mapping["orderRecordId"]) if mapping else None,
            "mapping_id": int(mapping["id"]) if mapping else None,
            "profile_name": profile_name,
            "server_identity": server_identity,
            "source_ae_title": source_ae_title,
            "study_instance_uid": metadata.get("study_instance_uid", ""),
            "series_instance_uid": metadata.get("series_instance_uid", ""),
            "sop_instance_uid": metadata.get("sop_instance_uid", ""),
            "accession_number": metadata.get("accession_number", ""),
            "patient_id": metadata.get("patient_id", ""),
            "issuer_of_patient_id": metadata.get("issuer_of_patient_id", ""),
            "requested_procedure_id": metadata.get("requested_procedure_id", ""),
            "scheduled_procedure_step_id": metadata.get("scheduled_procedure_step_id", ""),
            "modality": metadata.get("modality", ""),
            "study_datetime": metadata.get("study_datetime", ""),
            "series_datetime": metadata.get("series_datetime", ""),
            "instance_datetime": metadata.get("instance_datetime", ""),
            "viewer_url": links["viewer_url"],
            "study_retrieve_url": links["study_retrieve_url"],
            "series_retrieve_url": links["series_retrieve_url"],
            "instance_retrieve_url": links["instance_retrieve_url"],
            "reconciliation_status": reconciliation.get("status") or DCM4CHEE_RESULT_STATUS_UNLINKED,
            "match_method": reconciliation.get("method") or "",
            "match_strength": reconciliation.get("strength") or "",
            "query_url": query_url,
            "query_payload_json": json.dumps(query_payload or {}, sort_keys=True),
            "diagnostic_payload_json": json.dumps(reconciliation.get("diagnostic") or {}, sort_keys=True),
            "raw_metadata_json": json.dumps(raw_metadata or metadata or {}, sort_keys=True),
            "refresh_generation": str(refresh_generation or "").strip(),
        }
        with self._lock, self._connect() as connection:
            self._record_dcm4chee_result_refresh_run(
                connection,
                values["patient_record_id"],
                values["refresh_generation"],
                now,
            )
            existing = connection.execute(
                "SELECT * FROM local_dcm4chee_result_records WHERE result_key = ?",
                (result_key,),
            ).fetchone()
            if existing and self._dcm4chee_result_row_is_newer_than_generation(
                connection,
                existing,
                values["patient_record_id"],
                values["refresh_generation"],
            ):
                return project_result_record(existing)
            if existing:
                connection.execute(
                    """
                    UPDATE local_dcm4chee_result_records
                    SET patient_record_id = ?, order_record_id = ?, mapping_id = ?,
                        profile_name = ?, server_identity = ?, source_ae_title = ?,
                        study_instance_uid = ?, series_instance_uid = ?, sop_instance_uid = ?,
                        accession_number = ?, patient_id = ?, issuer_of_patient_id = ?,
                        requested_procedure_id = ?, scheduled_procedure_step_id = ?,
                        modality = ?, study_datetime = ?, series_datetime = ?, instance_datetime = ?,
                        viewer_url = ?, study_retrieve_url = ?, series_retrieve_url = ?,
                        instance_retrieve_url = ?, reconciliation_status = ?, match_method = ?,
                        match_strength = ?, query_url = ?, query_payload_json = ?,
                        diagnostic_payload_json = ?, raw_metadata_json = ?,
                        refresh_generation = ?,
                        last_refreshed_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        values["patient_record_id"],
                        values["order_record_id"],
                        values["mapping_id"],
                        values["profile_name"],
                        values["server_identity"],
                        values["source_ae_title"],
                        values["study_instance_uid"],
                        values["series_instance_uid"],
                        values["sop_instance_uid"],
                        values["accession_number"],
                        values["patient_id"],
                        values["issuer_of_patient_id"],
                        values["requested_procedure_id"],
                        values["scheduled_procedure_step_id"],
                        values["modality"],
                        values["study_datetime"],
                        values["series_datetime"],
                        values["instance_datetime"],
                        values["viewer_url"],
                        values["study_retrieve_url"],
                        values["series_retrieve_url"],
                        values["instance_retrieve_url"],
                        values["reconciliation_status"],
                        values["match_method"],
                        values["match_strength"],
                        values["query_url"],
                        values["query_payload_json"],
                        values["diagnostic_payload_json"],
                        values["raw_metadata_json"],
                        values["refresh_generation"],
                        now,
                        now,
                        int(existing["id"]),
                    ),
                )
                record_id = int(existing["id"])
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO local_dcm4chee_result_records (
                        result_key, patient_record_id, order_record_id, mapping_id,
                        profile_name, server_identity, source_ae_title,
                        study_instance_uid, series_instance_uid, sop_instance_uid,
                        accession_number, patient_id, issuer_of_patient_id,
                        requested_procedure_id, scheduled_procedure_step_id,
                        modality, study_datetime, series_datetime, instance_datetime,
                        viewer_url, study_retrieve_url, series_retrieve_url, instance_retrieve_url,
                        reconciliation_status, match_method, match_strength,
                        query_url, query_payload_json, diagnostic_payload_json, raw_metadata_json,
                        refresh_generation,
                        first_seen_at, last_refreshed_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result_key,
                        values["patient_record_id"],
                        values["order_record_id"],
                        values["mapping_id"],
                        values["profile_name"],
                        values["server_identity"],
                        values["source_ae_title"],
                        values["study_instance_uid"],
                        values["series_instance_uid"],
                        values["sop_instance_uid"],
                        values["accession_number"],
                        values["patient_id"],
                        values["issuer_of_patient_id"],
                        values["requested_procedure_id"],
                        values["scheduled_procedure_step_id"],
                        values["modality"],
                        values["study_datetime"],
                        values["series_datetime"],
                        values["instance_datetime"],
                        values["viewer_url"],
                        values["study_retrieve_url"],
                        values["series_retrieve_url"],
                        values["instance_retrieve_url"],
                        values["reconciliation_status"],
                        values["match_method"],
                        values["match_strength"],
                        values["query_url"],
                        values["query_payload_json"],
                        values["diagnostic_payload_json"],
                        values["raw_metadata_json"],
                        values["refresh_generation"],
                        now,
                        now,
                        now,
                        now,
                    ),
                )
                record_id = int(cursor.lastrowid)
        return self.get_dcm4chee_result_record(record_id)
    def complete_dcm4chee_result_refresh(
        self,
        patient_record_id: int,
        refresh_generation: str,
    ) -> list[dict[str, Any]]:
        generation = str(refresh_generation or "").strip()
        if not generation:
            raise SimulatorValidationError("DICOM result refresh generation is required.")
        completed_at = self._timestamp()
        with self._lock, self._connect() as connection:
            self._record_dcm4chee_result_refresh_run(
                connection,
                int(patient_record_id),
                generation,
                completed_at,
            )
            latest_run = connection.execute(
                """
                SELECT refresh_generation FROM local_dcm4chee_result_refresh_runs
                WHERE patient_record_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (int(patient_record_id),),
            ).fetchone()
            if latest_run and str(latest_run["refresh_generation"] or "").strip() != generation:
                return []
            rows = connection.execute(
                """
                SELECT * FROM local_dcm4chee_result_records
                WHERE patient_record_id = ? AND refresh_generation = ?
                ORDER BY last_refreshed_at DESC, id DESC
                """,
                (int(patient_record_id), generation),
            ).fetchall()
            snapshot = [project_result_record(row) for row in rows]
            connection.execute(
                """
                UPDATE local_dcm4chee_result_refresh_runs
                SET completed_at = ?, results_snapshot_json = ?
                WHERE patient_record_id = ? AND refresh_generation = ?
                """,
                (
                    completed_at,
                    json.dumps(snapshot, sort_keys=True),
                    int(patient_record_id),
                    generation,
                ),
            )
        return snapshot

    def get_dcm4chee_result_record(self, record_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_dcm4chee_result_records WHERE id = ?",
                (int(record_id),),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
        return project_result_record(row)

    def list_dcm4chee_results_for_patient(self, patient_record_id: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            latest = connection.execute(
                """
                SELECT results_snapshot_json FROM local_dcm4chee_result_refresh_runs
                WHERE patient_record_id = ? AND completed_at != ''
                ORDER BY id DESC
                LIMIT 1
                """,
                (int(patient_record_id),),
            ).fetchone()
            if latest:
                snapshot = _json_value(latest["results_snapshot_json"], [])
                return snapshot if isinstance(snapshot, list) else []
            has_run = connection.execute(
                """
                SELECT 1 FROM local_dcm4chee_result_refresh_runs
                WHERE patient_record_id = ?
                LIMIT 1
                """,
                (int(patient_record_id),),
            ).fetchone()
            if has_run:
                return []
            rows = connection.execute(
                """
                SELECT * FROM local_dcm4chee_result_records
                WHERE patient_record_id = ?
                ORDER BY last_refreshed_at DESC, id DESC
                """,
                (int(patient_record_id),),
            ).fetchall()
        return [project_result_record(row) for row in rows]

    def load_for_patients(self, patient_record_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
        ids = [int(value) for value in patient_record_ids]
        result: dict[int, list[dict[str, Any]]] = {record_id: [] for record_id in ids}
        if not ids:
            return result
        placeholders = ", ".join("?" for _ in ids)
        with self._connect() as connection:
            result_rows = connection.execute(
                f"""SELECT * FROM local_dcm4chee_result_records
                    WHERE patient_record_id IN ({placeholders})
                    ORDER BY last_refreshed_at DESC, id DESC""",
                ids,
            ).fetchall()
            refresh_rows = connection.execute(
                f"""SELECT patient_record_id, completed_at, results_snapshot_json
                    FROM local_dcm4chee_result_refresh_runs
                    WHERE patient_record_id IN ({placeholders}) ORDER BY id DESC""",
                ids,
            ).fetchall()
        refresh_run_patients: set[int] = set()
        selected_snapshots: set[int] = set()
        for row in refresh_rows:
            record_id = int(row["patient_record_id"])
            refresh_run_patients.add(record_id)
            if row["completed_at"] and record_id not in selected_snapshots:
                snapshot = _json_value(row["results_snapshot_json"], [])
                result[record_id] = snapshot if isinstance(snapshot, list) else []
                selected_snapshots.add(record_id)
        generations: dict[int, str] = {}
        for row in result_rows:
            record_id = int(row["patient_record_id"])
            if record_id not in refresh_run_patients and row["refresh_generation"] and record_id not in generations:
                generations[record_id] = str(row["refresh_generation"])
        for row in result_rows:
            record_id = int(row["patient_record_id"])
            if record_id in refresh_run_patients:
                continue
            if generations.get(record_id) and row["refresh_generation"] != generations[record_id]:
                continue
            result[record_id].append(project_result_record(row))
        return result

    def latest_simulated_dcm4chee_ap_return_generation(self, order_record_id: int) -> str:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT refresh_generation FROM local_dcm4chee_result_records
                WHERE order_record_id = ?
                AND refresh_generation LIKE 'simulated-ap-return-%'
                AND query_url LIKE 'simulated://ap-return/%'
                ORDER BY last_refreshed_at DESC, id DESC
                LIMIT 1
                """,
                (int(order_record_id),),
            ).fetchone()
        return str(row["refresh_generation"] or "").strip() if row else ""
    @staticmethod
    def _record_dcm4chee_result_refresh_run(
        connection: sqlite3.Connection,
        patient_record_id: int | None,
        refresh_generation: str,
        started_at: str,
    ) -> None:
        generation = str(refresh_generation or "").strip()
        if patient_record_id is None or not generation:
            return
        connection.execute(
            """
            INSERT OR IGNORE INTO local_dcm4chee_result_refresh_runs (
                patient_record_id, refresh_generation, started_at
            ) VALUES (?, ?, ?)
            """,
            (int(patient_record_id), generation, started_at),
        )

    @staticmethod
    def _dcm4chee_result_refresh_run_id(
        connection: sqlite3.Connection,
        patient_record_id: int,
        refresh_generation: str,
    ) -> int | None:
        row = connection.execute(
            """
            SELECT id FROM local_dcm4chee_result_refresh_runs
            WHERE patient_record_id = ? AND refresh_generation = ?
            """,
            (int(patient_record_id), str(refresh_generation or "").strip()),
        ).fetchone()
        return int(row["id"]) if row else None

    @classmethod
    def _dcm4chee_result_row_is_newer_than_generation(
        cls,
        connection: sqlite3.Connection,
        existing: sqlite3.Row,
        patient_record_id: int | None,
        refresh_generation: str,
    ) -> bool:
        existing_generation = str(existing["refresh_generation"] or "").strip()
        incoming_generation = str(refresh_generation or "").strip()
        if patient_record_id is None or not existing_generation or not incoming_generation:
            return False
        existing_run_id = cls._dcm4chee_result_refresh_run_id(
            connection,
            int(patient_record_id),
            existing_generation,
        )
        incoming_run_id = cls._dcm4chee_result_refresh_run_id(
            connection,
            int(patient_record_id),
            incoming_generation,
        )
        return bool(
            existing_run_id is not None
            and incoming_run_id is not None
            and existing_run_id > incoming_run_id
        )
    def begin_dcm4chee_result_refresh(
        self,
        patient_record_id: int,
        refresh_generation: str,
        *,
        promote_existing: bool = False,
    ) -> None:
        generation = str(refresh_generation or "").strip()
        if not generation:
            raise SimulatorValidationError("DICOM result refresh generation is required.")
        started_at = self._timestamp()
        with self._lock, self._connect() as connection:
            existing_run = connection.execute(
                """
                SELECT id FROM local_dcm4chee_result_refresh_runs
                WHERE patient_record_id = ? AND refresh_generation = ?
                """,
                (int(patient_record_id), generation),
            ).fetchone()
            latest_run = connection.execute(
                """
                SELECT id FROM local_dcm4chee_result_refresh_runs
                WHERE patient_record_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (int(patient_record_id),),
            ).fetchone()
            if (
                promote_existing
                and existing_run
                and latest_run
                and int(existing_run["id"]) != int(latest_run["id"])
            ):
                connection.execute(
                    "DELETE FROM local_dcm4chee_result_refresh_runs WHERE id = ?",
                    (int(existing_run["id"]),),
                )
            completed = connection.execute(
                """
                SELECT id FROM local_dcm4chee_result_refresh_runs
                WHERE patient_record_id = ? AND completed_at != ''
                LIMIT 1
                """,
                (int(patient_record_id),),
            ).fetchone()
            if not completed:
                legacy_rows = connection.execute(
                    """
                    SELECT * FROM local_dcm4chee_result_records
                    WHERE patient_record_id = ?
                    ORDER BY last_refreshed_at DESC, id DESC
                    """,
                    (int(patient_record_id),),
                ).fetchall()
                if legacy_rows:
                    legacy_generation = str(legacy_rows[0]["refresh_generation"] or "").strip()
                    if legacy_generation:
                        legacy_rows = [
                            row for row in legacy_rows
                            if str(row["refresh_generation"] or "").strip() == legacy_generation
                        ]
                    else:
                        legacy_generation = "legacy-snapshot"
                    legacy_snapshot = [project_result_record(row) for row in legacy_rows]
                    self._record_dcm4chee_result_refresh_run(
                        connection,
                        int(patient_record_id),
                        legacy_generation,
                        started_at,
                    )
                    connection.execute(
                        """
                        UPDATE local_dcm4chee_result_refresh_runs
                        SET completed_at = ?, results_snapshot_json = ?
                        WHERE patient_record_id = ? AND refresh_generation = ?
                        """,
                        (
                            started_at,
                            json.dumps(legacy_snapshot, sort_keys=True),
                            int(patient_record_id),
                            legacy_generation,
                        ),
                    )
            self._record_dcm4chee_result_refresh_run(
                connection,
                int(patient_record_id),
                generation,
                started_at,
            )
    def record_dcm4chee_result_refresh_diagnostic(
        self,
        *,
        patient_record_id: int,
        profile: dict[str, Any],
        status: str,
        query_url: str = "",
        query_payload: dict[str, Any] | None = None,
        diagnostic_payload: dict[str, Any] | None = None,
        refresh_generation: str = "",
    ) -> dict[str, Any]:
        profile_name, server_identity, source_ae_title = self._profile_identity(profile)
        result_key = self._result_key(
            profile_name=profile_name,
            server_identity=server_identity,
            patient_record_id=patient_record_id,
            status=status,
        )
        now = self._timestamp()
        generation = str(refresh_generation or "").strip()
        diagnostic_json = json.dumps(diagnostic_payload or {}, sort_keys=True)
        query_json = json.dumps(query_payload or {}, sort_keys=True)
        with self._lock, self._connect() as connection:
            self._record_dcm4chee_result_refresh_run(
                connection,
                int(patient_record_id),
                generation,
                now,
            )
            existing = connection.execute(
                "SELECT * FROM local_dcm4chee_result_records WHERE result_key = ?",
                (result_key,),
            ).fetchone()
            if existing and self._dcm4chee_result_row_is_newer_than_generation(
                connection,
                existing,
                int(patient_record_id),
                generation,
            ):
                return project_result_record(existing)
            if existing:
                connection.execute(
                    """
                    UPDATE local_dcm4chee_result_records
                    SET patient_record_id = ?, order_record_id = NULL, mapping_id = NULL,
                        profile_name = ?, server_identity = ?, source_ae_title = ?,
                        query_url = ?, query_payload_json = ?, diagnostic_payload_json = ?,
                        reconciliation_status = ?, match_method = '', match_strength = '',
                        refresh_generation = ?,
                        last_refreshed_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        int(patient_record_id),
                        profile_name,
                        server_identity,
                        source_ae_title,
                        query_url,
                        query_json,
                        diagnostic_json,
                        status,
                        generation,
                        now,
                        now,
                        int(existing["id"]),
                    ),
                )
                record_id = int(existing["id"])
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO local_dcm4chee_result_records (
                        result_key, patient_record_id, profile_name, server_identity, source_ae_title,
                        reconciliation_status, query_url, query_payload_json, diagnostic_payload_json,
                        refresh_generation, first_seen_at, last_refreshed_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result_key,
                        int(patient_record_id),
                        profile_name,
                        server_identity,
                        source_ae_title,
                        status,
                        query_url,
                        query_json,
                        diagnostic_json,
                        generation,
                        now,
                        now,
                        now,
                        now,
                    ),
                )
                record_id = int(cursor.lastrowid)
        return self.get_dcm4chee_result_record(record_id)
