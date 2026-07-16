"""SQLite repository for generic local Order records and send results."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from sqlite3 import Connection, Row
from threading import RLock
from typing import Any

from backend.domain import order as order_domain
from backend.mappers.order import project as project_order

ConnectionFactory = Callable[[], AbstractContextManager[Connection]]


class OrderRepository:
    def __init__(self, connection_factory: ConnectionFactory, lock: RLock, *, validator,
                 payload_builder, timestamp_factory, hl7_timestamp_factory,
                 enrichment_loader=None, dcm4chee_status_view=None) -> None:
        self._connect = connection_factory
        self._lock = lock
        self._validate = validator
        self._build_payload = payload_builder
        self._timestamp = timestamp_factory
        self._hl7_timestamp = hl7_timestamp_factory
        self._enrichment = enrichment_loader
        self._dcm4chee_status_view = dcm4chee_status_view

    @property
    def lock(self) -> RLock:
        return self._lock

    def create_order_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = self._validate(payload)
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            patient = connection.execute("SELECT * FROM local_patient_records WHERE id = ?", (values["patient_record_id"],)).fetchone()
            if not patient:
                raise KeyError(values["patient_record_id"])
            cursor = connection.execute(
                """INSERT INTO local_order_records (
                    local_order_number, patient_record_id, protocol_version, message_type, order_status,
                    mrn, first_name, last_name, middle_name, dob, sex, visit_id, patient_class,
                    assigned_location, account_number, placer_order_number, filler_order_number,
                    priority, requested_at, ordering_provider, clinical_indication, order_code,
                    order_code_text, alternate_code, alternate_code_text, alternate_code_system,
                    validation_status, validation_messages_json, payload_hl7, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("", values["patient_record_id"], "2.5.1", "ORM^O01", "Ready to send", patient["mrn"],
                 patient["first_name"], patient["last_name"], patient["middle_name"], patient["dob"], patient["sex"],
                 patient["visit_number"], patient["patient_class"], patient["assigned_location"], patient["account_number"],
                 "", "", values["priority"], values["requested_at"], values["ordering_provider"], values["clinical_indication"],
                 values["order_code"], values["order_code_text"], values["alternate_code"], values["alternate_code_text"],
                 values["alternate_code_system"], "valid", "[]", "", timestamp, timestamp),
            )
            record_id = int(cursor.lastrowid)
            number = order_domain.record_number(record_id)
            visit = patient["visit_number"] or order_domain.visit_id(record_id)
            account = patient["account_number"] or order_domain.account_number(record_id)
            rendered = self._build_payload({**values, "local_order_number": number, "filler_order_number": "",
                "mrn": patient["mrn"], "first_name": patient["first_name"], "last_name": patient["last_name"],
                "middle_name": patient["middle_name"], "dob": patient["dob"], "sex": patient["sex"],
                "visit_id": visit, "patient_class": patient["patient_class"], "assigned_location": patient["assigned_location"],
                "account_number": account}, record_id=record_id, timestamp=self._hl7_timestamp())
            connection.execute(
                "UPDATE local_order_records SET local_order_number = ?, placer_order_number = ?, visit_id = ?, account_number = ?, payload_hl7 = ?, updated_at = ? WHERE id = ?",
                (number, number, visit, account, rendered, timestamp, record_id),
            )
        return self.get_order_record(record_id)

    def create_dcm4chee_order_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        item = self.create_order_record(payload)
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            connection.execute(
                """UPDATE local_order_records
                   SET protocol_version = 'DICOM', message_type = 'MWL', order_status = 'Created',
                       payload_hl7 = '', updated_at = ? WHERE id = ?""",
                (timestamp, int(item["id"])),
            )
        return self.get_order_record(int(item["id"]))

    def create_fhir_order_record(
        self,
        values: dict[str, Any],
        *,
        patient_reference: str,
        resource_builder: Callable[..., dict[str, Any]],
        priority_projector: Callable[[Any], str],
    ) -> dict[str, Any]:
        """Persist the generic order anchor and deterministic FHIR payload atomically."""
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            patient = connection.execute(
                "SELECT * FROM local_patient_records WHERE id = ?",
                (values["patient_record_id"],),
            ).fetchone()
            if not patient:
                raise KeyError(values["patient_record_id"])
            cursor = connection.execute(
                """INSERT INTO local_order_records (
                    local_order_number, patient_record_id, protocol_version, message_type,
                    order_status, mrn, first_name, last_name, middle_name, dob, sex,
                    visit_id, patient_class, assigned_location, account_number,
                    placer_order_number, filler_order_number, priority, requested_at,
                    ordering_provider, clinical_indication, order_code, order_code_text,
                    alternate_code, alternate_code_text, alternate_code_system,
                    validation_status, validation_messages_json, payload_hl7,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "", values["patient_record_id"], "FHIR R4", "ServiceRequest",
                    "Created", patient["mrn"], patient["first_name"], patient["last_name"],
                    patient["middle_name"], patient["dob"], patient["sex"],
                    patient["visit_number"], patient["patient_class"],
                    patient["assigned_location"], patient["account_number"], "", "",
                    priority_projector(values["priority"]), values["requested_at"],
                    values["ordering_provider"], values["clinical_indication"],
                    values["order_code"], values["order_code_text"], values["alternate_code"],
                    values["alternate_code_text"], values["alternate_code_system"],
                    "valid", "[]", "", timestamp, timestamp,
                ),
            )
            record_id = int(cursor.lastrowid)
            local_order_number = order_domain.record_number(record_id)
            visit_id = patient["visit_number"] or order_domain.visit_id(record_id)
            account_number = patient["account_number"] or order_domain.account_number(record_id)
            resource = resource_builder(
                values,
                record_id=record_id,
                local_order_number=local_order_number,
                patient_reference=patient_reference,
            )
            connection.execute(
                """UPDATE local_order_records
                   SET local_order_number = ?, placer_order_number = ?, visit_id = ?,
                       account_number = ?, payload_hl7 = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    local_order_number, local_order_number, visit_id, account_number,
                    json.dumps(resource, indent=2, sort_keys=True), timestamp, record_id,
                ),
            )
        return self.get_order_record(record_id)

    def _project(self, rows: list[Row]) -> list[dict[str, Any]]:
        enrichments = self._enrichment.load(rows) if self._enrichment else {}
        return [project_order(row,
            fhir_records=enrichments.get(int(row["id"]), {}).get("fhir", {}),
            dcm4chee_attempt=enrichments.get(int(row["id"]), {}).get("attempt"),
            dcm4chee_mapping=enrichments.get(int(row["id"]), {}).get("mapping"),
            dcm4chee_status_view=self._dcm4chee_status_view) for row in rows]

    def list_order_records(self, protocol_version: str = "") -> list[dict[str, Any]]:
        with self._connect() as connection:
            if protocol_version:
                rows = connection.execute("SELECT * FROM local_order_records WHERE protocol_version = ? ORDER BY created_at DESC, id DESC", (protocol_version,)).fetchall()
            else:
                rows = connection.execute("SELECT * FROM local_order_records ORDER BY created_at DESC, id DESC").fetchall()
        return self._project(rows)

    def get_order_record(self, record_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM local_order_records WHERE id = ?", (record_id,)).fetchone()
        if not row:
            raise KeyError(record_id)
        return self._project([row])[0]

    def update_order_send_result(self, record_id: int, *, order_status: str, ack_code: str = "",
                                 ack_control_id: str = "", ack_text: str = "", ack_payload: str = "",
                                 transport_error: str = "") -> dict[str, Any]:
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            if not connection.execute("SELECT id FROM local_order_records WHERE id = ?", (record_id,)).fetchone():
                raise KeyError(record_id)
            connection.execute(
                """UPDATE local_order_records SET order_status = ?, ack_code = ?, ack_control_id = ?,
                   ack_text = ?, ack_payload = ?, transport_error = ?, last_sent_at = ?, updated_at = ? WHERE id = ?""",
                (order_status, ack_code, ack_control_id, ack_text, ack_payload, transport_error, timestamp, timestamp, record_id),
            )
        return self.get_order_record(record_id)
