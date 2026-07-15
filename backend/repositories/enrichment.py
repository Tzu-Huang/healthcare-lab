"""Narrow cross-context enrichment loaders for Patient and Order projections."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from sqlite3 import Connection, Row
from typing import Any

ConnectionFactory = Callable[[], AbstractContextManager[Connection]]


class PatientEnrichmentLoader:
    def __init__(
        self, connection_factory: ConnectionFactory, *, fhir_projector,
        patient_sync_loader, result_loader,
    ) -> None:
        self._connect = connection_factory
        self._fhir_projector = fhir_projector
        self._load_patient_syncs = patient_sync_loader
        self._load_results = result_loader

    def load(self, rows: list[Row]) -> dict[int, dict[str, Any]]:
        ids = [int(row["id"]) for row in rows]
        result = {record_id: {"fhir": None, "sync": None, "results": []} for record_id in ids}
        if not ids:
            return result
        placeholders = ", ".join("?" for _ in ids)
        with self._connect() as connection:
            fhir_rows = connection.execute(
                f"""SELECT * FROM local_fhir_workflow_records
                    WHERE local_source_type = 'local_patient_records'
                    AND local_source_id IN ({placeholders}) AND resource_type = 'Patient'""",
                [str(value) for value in ids],
            ).fetchall()
        for row in fhir_rows:
            result[int(row["local_source_id"])]["fhir"] = self._fhir_projector(row)
        syncs = self._load_patient_syncs(ids)
        results = self._load_results(ids)
        for record_id in ids:
            result[record_id]["sync"] = syncs.get(record_id)
            result[record_id]["results"] = results.get(record_id, [])
        return result


class OrderEnrichmentLoader:
    def __init__(
        self, connection_factory: ConnectionFactory, *, fhir_projector, mwl_loader,
    ) -> None:
        self._connect = connection_factory
        self._fhir_projector = fhir_projector
        self._load_mwl = mwl_loader

    def load(self, rows: list[Row]) -> dict[int, dict[str, Any]]:
        ids = [int(row["id"]) for row in rows]
        result = {record_id: {"fhir": {}, "attempt": None, "mapping": None} for record_id in ids}
        if not ids:
            return result
        placeholders = ", ".join("?" for _ in ids)
        with self._connect() as connection:
            fhir_rows = connection.execute(
                f"""SELECT * FROM local_fhir_workflow_records
                    WHERE local_source_type = 'local_order_records'
                    AND local_source_id IN ({placeholders}) AND resource_type = 'ServiceRequest'""",
                [str(value) for value in ids],
            ).fetchall()
        for row in fhir_rows:
            result[int(row["local_source_id"])]["fhir"][row["resource_type"]] = self._fhir_projector(row)
        mwl = self._load_mwl(ids)
        for record_id in ids:
            result[record_id]["attempt"] = mwl.get(record_id, {}).get("attempt")
            result[record_id]["mapping"] = mwl.get(record_id, {}).get("mapping")
        return result
