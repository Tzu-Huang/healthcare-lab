"""SQLite repository for local Patient records."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from sqlite3 import Connection, Row
from threading import RLock
from typing import Any

from backend.domain import patient as patient_domain
from backend.domain.errors import SimulatorValidationError
from backend.mappers.patient import project as project_patient
from backend.repositories.identifiers import PatientIdentifierRepository

ConnectionFactory = Callable[[], AbstractContextManager[Connection]]


class PatientRepository:
    def __init__(self, connection_factory: ConnectionFactory, lock: RLock, *, identifier_repository,
                 validator, payload_builder, timestamp_factory, hl7_timestamp_factory,
                 enrichment_loader=None) -> None:
        self._connect = connection_factory
        self._lock = lock
        self._identifiers = identifier_repository
        self._validate = validator
        self._build_payload = payload_builder
        self._timestamp = timestamp_factory
        self._hl7_timestamp = hl7_timestamp_factory
        self._enrichment = enrichment_loader

    @property
    def lock(self) -> RLock:
        return self._lock

    def create_patient_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = self._validate(payload)
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            values["mrn"] = values["mrn"] or self._identifiers.allocate(connection)
            if connection.execute("SELECT 1 FROM local_patient_records WHERE mrn = ? LIMIT 1", (values["mrn"],)).fetchone():
                raise SimulatorValidationError(f"Patient MRN {values['mrn']} already exists.")
            cursor = connection.execute(
                """INSERT INTO local_patient_records (
                    local_patient_number, protocol_version, message_type, mrn, first_name, last_name,
                    middle_name, dob, sex, address, phone, email, fhir_active, address_line,
                    address_city, address_state, address_postal_code, address_country,
                    managing_organization_reference, managing_organization_display, visit_number,
                    patient_class, assigned_location, attending_provider, account_number,
                    validation_status, validation_messages_json, payload_hl7, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("", patient_domain.PATIENT_MODES[values["mode"]]["protocol"], patient_domain.PATIENT_MODES[values["mode"]]["message_type"],
                 values["mrn"], values["first_name"], values["last_name"], values["middle_name"], values["dob"], values["sex"],
                 values["address"], values["phone"], values["email"], int(values["fhir_active"]), values["address_line"],
                 values["address_city"], values["address_state"], values["address_postal_code"], values["address_country"],
                 values["managing_organization_reference"], values["managing_organization_display"], values["visit_number"],
                 values["patient_class"], values["assigned_location"], values["attending_provider"], values["account_number"],
                 "valid", "[]", "", timestamp, timestamp),
            )
            record_id = int(cursor.lastrowid)
            rendered, visit = self._build_payload(values, record_id=record_id, timestamp=timestamp, hl7_time=self._hl7_timestamp())
            connection.execute(
                "UPDATE local_patient_records SET local_patient_number = ?, visit_number = ?, payload_hl7 = ?, updated_at = ? WHERE id = ?",
                (patient_domain.record_number(record_id), visit, rendered, timestamp, record_id),
            )
        return self.get_patient_record(record_id)

    def _project(self, rows: list[Row]) -> list[dict[str, Any]]:
        enrichments = self._enrichment.load(rows) if self._enrichment else {}
        return [project_patient(
            row, fhir_record=enrichments.get(int(row["id"]), {}).get("fhir"),
            dcm4chee_patient_sync=enrichments.get(int(row["id"]), {}).get("sync"),
            dcm4chee_results=enrichments.get(int(row["id"]), {}).get("results", []),
        ) for row in rows]

    def list_patient_records(self, protocol_version: str = "") -> list[dict[str, Any]]:
        with self._connect() as connection:
            if protocol_version:
                rows = connection.execute("SELECT * FROM local_patient_records WHERE protocol_version = ? ORDER BY created_at DESC, id DESC", (protocol_version,)).fetchall()
            else:
                rows = connection.execute("SELECT * FROM local_patient_records ORDER BY created_at DESC, id DESC").fetchall()
        return self._project(rows)

    def get_patient_record(self, record_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM local_patient_records WHERE id = ?", (record_id,)).fetchone()
        if not row:
            raise KeyError(record_id)
        return self._project([row])[0]
