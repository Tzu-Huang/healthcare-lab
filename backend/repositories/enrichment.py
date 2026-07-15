"""Narrow cross-context enrichment loaders for Patient and Order projections."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from sqlite3 import Connection, Row
from typing import Any

ConnectionFactory = Callable[[], AbstractContextManager[Connection]]


class PatientEnrichmentLoader:
    def __init__(self, connection_factory: ConnectionFactory, *, fhir_projector, sync_projector,
                 result_projector, json_loader) -> None:
        self._connect = connection_factory
        self._fhir_projector = fhir_projector
        self._sync_projector = sync_projector
        self._result_projector = result_projector
        self._json_loader = json_loader

    def load(self, rows: list[Row]) -> dict[int, dict[str, Any]]:
        ids = [int(row["id"]) for row in rows]
        result = {record_id: {"fhir": None, "sync": None, "results": []} for record_id in ids}
        if not ids:
            return result
        placeholders = ", ".join("?" for _ in ids)
        string_ids = [str(value) for value in ids]
        with self._connect() as connection:
            fhir_rows = connection.execute(
                f"SELECT * FROM local_fhir_workflow_records WHERE local_source_type = 'local_patient_records' AND local_source_id IN ({placeholders}) AND resource_type = 'Patient'",
                string_ids,
            ).fetchall()
            sync_rows = connection.execute(
                f"SELECT * FROM local_dcm4chee_patient_syncs WHERE patient_record_id IN ({placeholders}) ORDER BY updated_at DESC, id DESC",
                ids,
            ).fetchall()
            result_rows = connection.execute(
                f"SELECT * FROM local_dcm4chee_result_records WHERE patient_record_id IN ({placeholders}) ORDER BY last_refreshed_at DESC, id DESC",
                ids,
            ).fetchall()
            refresh_rows = connection.execute(
                f"SELECT patient_record_id, completed_at, results_snapshot_json FROM local_dcm4chee_result_refresh_runs WHERE patient_record_id IN ({placeholders}) ORDER BY id DESC",
                ids,
            ).fetchall()
        for row in fhir_rows:
            result[int(row["local_source_id"])]["fhir"] = self._fhir_projector(row)
        for row in sync_rows:
            item = result[int(row["patient_record_id"])]
            if item["sync"] is None:
                item["sync"] = self._sync_projector(row)
        snapshotted: set[int] = set()
        for row in refresh_rows:
            record_id = int(row["patient_record_id"])
            snapshotted.add(record_id)
            if row["completed_at"] and not result[record_id]["results"]:
                snapshot = self._json_loader(row["results_snapshot_json"], [])
                result[record_id]["results"] = snapshot if isinstance(snapshot, list) else []
        generations: dict[int, str] = {}
        for row in result_rows:
            record_id = int(row["patient_record_id"])
            if record_id not in snapshotted and row["refresh_generation"] and record_id not in generations:
                generations[record_id] = str(row["refresh_generation"])
        for row in result_rows:
            record_id = int(row["patient_record_id"])
            if record_id in snapshotted:
                continue
            if generations.get(record_id) and row["refresh_generation"] != generations[record_id]:
                continue
            result[record_id]["results"].append(self._result_projector(row))
        return result


class OrderEnrichmentLoader:
    def __init__(self, connection_factory: ConnectionFactory, *, fhir_projector,
                 attempt_projector, mapping_projector) -> None:
        self._connect = connection_factory
        self._fhir_projector = fhir_projector
        self._attempt_projector = attempt_projector
        self._mapping_projector = mapping_projector

    def load(self, rows: list[Row]) -> dict[int, dict[str, Any]]:
        ids = [int(row["id"]) for row in rows]
        result = {record_id: {"fhir": {}, "attempt": None, "mapping": None} for record_id in ids}
        if not ids:
            return result
        placeholders = ", ".join("?" for _ in ids)
        with self._connect() as connection:
            fhir_rows = connection.execute(
                f"SELECT * FROM local_fhir_workflow_records WHERE local_source_type = 'local_order_records' AND local_source_id IN ({placeholders}) AND resource_type = 'ServiceRequest'",
                [str(value) for value in ids],
            ).fetchall()
            attempt_rows = connection.execute(
                f"SELECT * FROM local_dcm4chee_mwl_attempts WHERE order_record_id IN ({placeholders}) ORDER BY attempted_at DESC, id DESC",
                ids,
            ).fetchall()
            mapping_rows = connection.execute(
                f"SELECT * FROM local_dcm4chee_mwl_mappings WHERE order_record_id IN ({placeholders})", ids
            ).fetchall()
        for row in fhir_rows:
            result[int(row["local_source_id"])]["fhir"][row["resource_type"]] = self._fhir_projector(row)
        for row in attempt_rows:
            item = result[int(row["order_record_id"])]
            if item["attempt"] is None:
                item["attempt"] = self._attempt_projector(row)
        for row in mapping_rows:
            result[int(row["order_record_id"])]["mapping"] = self._mapping_projector(row)
        return result
