"""Narrow cross-context enrichment loaders for Patient and Order projections."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from sqlite3 import Connection, Row
from typing import Any

from backend.repositories.fhir_ledger import load_fhir_sources

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
        fhir = load_fhir_sources(
            self._connect,
            ids,
            source_type="local_patient_records",
            resource_type="Patient",
            projector=self._fhir_projector,
        )
        for record_id, item in fhir.items():
            result[record_id]["fhir"] = item
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
        fhir = load_fhir_sources(
            self._connect,
            ids,
            source_type="local_order_records",
            resource_type="ServiceRequest",
            projector=self._fhir_projector,
        )
        for record_id, item in fhir.items():
            result[record_id]["fhir"][item["resourceType"]] = item
        mwl = self._load_mwl(ids)
        for record_id in ids:
            result[record_id]["attempt"] = mwl.get(record_id, {}).get("attempt")
            result[record_id]["mapping"] = mwl.get(record_id, {}).get("mapping")
        return result
