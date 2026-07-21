"""Cohesive SQLite owner for the local GDT workflow ledger."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from sqlite3 import Connection, IntegrityError, Row
from threading import RLock
from typing import Any

from backend.domain.gdt_protocol import (
    GDT_ORDER_MESSAGE_TYPE,
    GDT_ORDER_TEST_CODE,
    GDT_ORDER_TEST_CODE_FIELD,
    GDT_RESULT_MESSAGE_TYPE,
    GdtAdapterResult,
    persistence_order_identifiers,
)
from backend.domain.errors import SimulatorValidationError
from backend.domain import gdt_workflow as gdt_domain
from backend.mappers import gdt as gdt_mapper

ConnectionFactory = Callable[[], AbstractContextManager[Connection]]

GDT_ORDER_PROTOCOL_VERSION = "GDT 2.1"
GDT_ORDER_STATUS_CREATED = "Created"
GDT_ORDER_STATUS_RESULT_RECEIVED = "Result received"
GDT_ORDER_TEST_LABEL = "12-lead resting ECG"


class GdtWorkflowRepository:
    """Own all five GDT tables while consuming only normalized protocol values."""

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        lock: RLock,
        *,
        timestamp_factory: Callable[[], str],
        patient_loader: Callable[[int], dict[str, Any]],
        patient_list_loader: Callable[[], list[dict[str, Any]]],
        order_builder: Callable[[dict[str, Any]], GdtAdapterResult | dict[str, Any]],
    ) -> None:
        self._connect = connection_factory
        self._lock = lock
        self._timestamp = timestamp_factory
        self._patient_loader = patient_loader
        self._patient_list_loader = patient_list_loader
        self._build_order = order_builder

    @staticmethod
    def _json(value: str, fallback: Any) -> Any:
        try:
            return json.loads(value or "")
        except (TypeError, ValueError):
            return fallback

    def _event(self, connection: Connection, *, event_type: str, timestamp: str,
               order_record_id: int | None = None, patient_context_id: int | None = None,
               message_record_id: int | None = None, attachment_record_id: int | None = None,
               actor: str = "", details: dict[str, Any] | None = None) -> int:
        cursor = connection.execute(
            """INSERT INTO local_gdt_workflow_events (
                order_record_id, patient_context_id, message_record_id, attachment_record_id,
                event_type, actor, details_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (order_record_id, patient_context_id, message_record_id, attachment_record_id,
             event_type, actor, json.dumps(details or {}, sort_keys=True), timestamp),
        )
        return int(cursor.lastrowid)

    def _ensure_context(self, connection: Connection, patient: dict[str, Any], *, override: str,
                        timestamp: str) -> Row:
        patient_id = int(patient["id"])
        context = connection.execute(
            "SELECT * FROM local_gdt_patient_contexts WHERE patient_record_id = ?", (patient_id,)
        ).fetchone()
        generated = gdt_domain.patient_number(patient_id)
        effective = override or generated
        snapshot_json = json.dumps(gdt_mapper.patient_snapshot(patient, effective), sort_keys=True)
        if not context:
            try:
                cursor = connection.execute(
                    """INSERT INTO local_gdt_patient_contexts (
                        patient_record_id, generated_gdt_patient_number, gdt_patient_number_override,
                        effective_gdt_patient_number, patient_snapshot_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (patient_id, generated, override, effective, snapshot_json, timestamp, timestamp),
                )
            except IntegrityError as exc:
                raise SimulatorValidationError("GDT patient number must be unique.") from exc
            context_id = int(cursor.lastrowid)
            self._event(connection, event_type="patient-number-generated", patient_context_id=context_id,
                        timestamp=timestamp, details={"generatedGdtPatientNumber": generated})
            if override:
                self._event(
                    connection, event_type="patient-number-overridden", patient_context_id=context_id,
                    timestamp=timestamp,
                    details={"generatedGdtPatientNumber": generated, "effectiveGdtPatientNumber": effective},
                )
        elif override and override != context["gdt_patient_number_override"]:
            try:
                connection.execute(
                    """UPDATE local_gdt_patient_contexts
                       SET gdt_patient_number_override = ?, effective_gdt_patient_number = ?,
                           patient_snapshot_json = ?, updated_at = ? WHERE id = ?""",
                    (override, effective, snapshot_json, timestamp, context["id"]),
                )
            except IntegrityError as exc:
                raise SimulatorValidationError("GDT patient number must be unique.") from exc
            self._event(
                connection, event_type="patient-number-overridden", patient_context_id=context["id"],
                timestamp=timestamp,
                details={"previousGdtPatientNumber": context["effective_gdt_patient_number"],
                         "effectiveGdtPatientNumber": effective},
            )
        else:
            effective = context["effective_gdt_patient_number"]
            snapshot_json = json.dumps(gdt_mapper.patient_snapshot(patient, effective), sort_keys=True)
            connection.execute(
                "UPDATE local_gdt_patient_contexts SET patient_snapshot_json = ?, updated_at = ? WHERE id = ?",
                (snapshot_json, timestamp, context["id"]),
            )
        return connection.execute(
            "SELECT * FROM local_gdt_patient_contexts WHERE patient_record_id = ?", (patient_id,)
        ).fetchone()

    def _message(self, connection: Connection, *, order_record_id: int | None,
                 patient_context_id: int | None, direction: str, raw_gdt_text: str,
                 parsed_fields: dict[str, list[str]], canonical: dict[str, Any], timestamp: str,
                 match_status: str = "", error_text: str = "") -> int:
        message_type = (parsed_fields.get("8000") or [""])[0]
        cursor = connection.execute(
            """INSERT INTO local_gdt_message_records (
                order_record_id, patient_context_id, direction, message_type, raw_gdt_text,
                parsed_fields_json, canonical_json, parse_status, match_status, error_text,
                generated_at, received_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'accepted', ?, ?, ?, ?, ?, ?)""",
            (order_record_id, patient_context_id, direction, message_type, raw_gdt_text,
             json.dumps(parsed_fields, sort_keys=True), json.dumps(canonical, sort_keys=True),
             match_status, error_text, timestamp if direction == "outbound" else "",
             timestamp if direction == "inbound" else "", timestamp, timestamp),
        )
        return int(cursor.lastrowid)

    def _attachment(self, connection: Connection, *, order_record_id: int | None,
                    message_record_id: int | None, role: str, timestamp: str, **values: Any) -> int:
        url, path = str(values.get("url") or "").strip(), str(values.get("path") or "").strip()
        reference = str(values.get("reference") or "").strip() or url or path
        filename = str(values.get("filename") or "").strip() or gdt_mapper.attachment_filename(url, path or reference)
        status = str(values.get("status") or "").strip()
        cursor = connection.execute(
            """INSERT INTO local_gdt_attachment_records (
                order_record_id, message_record_id, role, url, path, reference, content_type,
                description, source_file, status, details_json, filename, checksum, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (order_record_id, message_record_id, str(role or "other").strip() or "other", url, path,
             reference, str(values.get("content_type", values.get("contentType", "")) or "").strip(),
             str(values.get("description") or "").strip(),
             str(values.get("source_file", values.get("sourceFile", "")) or "").strip(), status,
             json.dumps(values.get("details") or {}, sort_keys=True), filename,
             str(values.get("checksum") or "").strip(), timestamp, timestamp),
        )
        attachment_id = int(cursor.lastrowid)
        self._event(
            connection, event_type="attachment-registered", order_record_id=order_record_id,
            message_record_id=message_record_id, attachment_record_id=attachment_id, timestamp=timestamp,
            details={"role": str(role or "other").strip() or "other", "filename": filename, "status": status},
        )
        return attachment_id

    def create_gdt_order_record(self, values: dict[str, Any]) -> dict[str, Any]:
        patient_id = int(values.get("patient_record_id", values.get("patientRecordId")))
        patient = self._patient_loader(patient_id)
        demographics = patient.get("patient") if isinstance(patient.get("patient"), dict) else patient
        summary = patient.get("summary") if isinstance(patient.get("summary"), dict) else {}
        requested_at = str(values.get("requested_at", values.get("requestedAt", "")) or "")
        provider = str(values.get("ordering_provider", values.get("orderingProvider", "")) or "")
        indication = str(values.get("clinical_indication", values.get("clinicalIndication", "")) or "")
        attachment_url = str(values.get("attachment_url", values.get("attachmentUrl", "")) or "")
        override = str(values.get("gdt_patient_number_override", values.get("gdtPatientNumberOverride", "")) or "")
        test_code = str(values.get("gdt_test_code", values.get("gdtTestCode", GDT_ORDER_TEST_CODE)) or GDT_ORDER_TEST_CODE)
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            context = self._ensure_context(connection, patient, override=override, timestamp=timestamp)
            workflow_patient_id = context["effective_gdt_patient_number"]
            canonical_mrn = str(demographics.get("mrn", summary.get("mrn", "")) or "").strip()
            patient_snapshot = gdt_mapper.patient_snapshot(patient, canonical_mrn)
            patient_snapshot["gdtWorkflowPatientId"] = workflow_patient_id
            order_snapshot = {
                "requestedAt": requested_at, "orderingProvider": provider,
                "clinicalIndication": indication, "gdtTestField": GDT_ORDER_TEST_CODE_FIELD,
                "gdtTestCode": test_code, "gdtTestLabel": GDT_ORDER_TEST_LABEL,
            }
            cursor = connection.execute(
                """INSERT INTO local_gdt_order_records (
                    local_gdt_order_number, patient_record_id, gdt_patient_context_id, protocol_version,
                    message_type, order_status, mrn, gdt_patient_number, first_name, last_name, middle_name,
                    dob, sex, visit_number, gdt_test_code, gdt_test_label, requested_at, ordering_provider,
                    clinical_indication, attachment_url, payload_gdt, patient_snapshot_json,
                    order_snapshot_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("", patient_id, context["id"], GDT_ORDER_PROTOCOL_VERSION, GDT_ORDER_MESSAGE_TYPE,
                 GDT_ORDER_STATUS_CREATED, canonical_mrn,
                 canonical_mrn, demographics.get("firstName", ""), demographics.get("lastName", ""),
                 demographics.get("middleName", ""), demographics.get("dob", summary.get("dob", "")),
                 demographics.get("sex", summary.get("sex", "")),
                 patient.get("visitNumber", summary.get("visitNumber", "")), test_code, GDT_ORDER_TEST_LABEL,
                 requested_at, provider, indication, attachment_url, "",
                 json.dumps(patient_snapshot, sort_keys=True), json.dumps(order_snapshot, sort_keys=True),
                 timestamp, timestamp),
            )
            record_id = int(cursor.lastrowid)
            order_number = gdt_domain.order_number(record_id)
            order_snapshot["localGdtOrderNumber"] = order_number
            adapter_result = self._build_order(gdt_domain.prepare_order_payload(
                demographics=demographics, summary=summary, gdt_patient_number=canonical_mrn,
                local_order_number=order_number, requested_at=requested_at,
                ordering_provider=provider, clinical_indication=indication,
                patient_snapshot=patient_snapshot, order_snapshot=order_snapshot,
                test_label=GDT_ORDER_TEST_LABEL,
            ))
            raw, parsed, canonical = gdt_domain.adapter_values(adapter_result)
            message_id = self._message(
                connection, order_record_id=record_id, patient_context_id=context["id"], direction="outbound",
                raw_gdt_text=raw, parsed_fields=parsed, canonical=canonical, timestamp=timestamp,
            )
            connection.execute(
                """UPDATE local_gdt_order_records SET local_gdt_order_number = ?, payload_gdt = ?,
                   order_snapshot_json = ?, updated_at = ? WHERE id = ?""",
                (order_number, raw, json.dumps(order_snapshot, sort_keys=True), timestamp, record_id),
            )
            self._event(connection, event_type="order-created", order_record_id=record_id,
                        patient_context_id=context["id"], timestamp=timestamp,
                        details={"localGdtOrderNumber": order_number})
            self._event(connection, event_type="message-generated", order_record_id=record_id,
                        patient_context_id=context["id"], message_record_id=message_id, timestamp=timestamp,
                        details={"messageType": GDT_ORDER_MESSAGE_TYPE})
            if attachment_url:
                self._attachment(connection, order_record_id=record_id, message_record_id=message_id,
                                 role="order-attachment", url=attachment_url, timestamp=timestamp)
        return self.get_gdt_order_record(record_id)

    def record_gdt_result(self, values: GdtAdapterResult | dict[str, Any]) -> dict[str, Any]:
        if not isinstance(values, dict):
            raw, fields, canonical = gdt_domain.adapter_values(values)
            extras: dict[str, Any] = {}
        else:
            raw, fields, canonical = gdt_domain.adapter_values(values)
            extras = values
        canonical = json.loads(json.dumps(canonical))
        identifiers = list(extras.get("orderIdentifiers") or persistence_order_identifiers(fields))
        patient_number = str((canonical.get("patient") or {}).get("gdtPatientNumber") or
                             ((fields.get("3000") or [""])[0]))
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            order_row = None
            if identifiers:
                placeholders = ", ".join("?" for _ in identifiers)
                order_row = connection.execute(
                    f"""SELECT * FROM local_gdt_order_records
                        WHERE local_gdt_order_number IN ({placeholders})
                        ORDER BY id DESC LIMIT 1""", identifiers,
                ).fetchone()
            patient_context_id = order_row["gdt_patient_context_id"] if order_row else None
            if not patient_context_id and patient_number:
                context = connection.execute(
                    """SELECT context.*
                       FROM local_gdt_patient_contexts AS context
                       JOIN local_patient_records AS patient
                         ON patient.id = context.patient_record_id
                       WHERE UPPER(TRIM(patient.mrn)) = UPPER(TRIM(?))
                          OR context.effective_gdt_patient_number = ?
                          OR context.generated_gdt_patient_number = ?
                          OR context.gdt_patient_number_override = ?
                       ORDER BY context.id DESC LIMIT 1""",
                    (patient_number, patient_number, patient_number, patient_number),
                ).fetchone()
                patient_context_id = context["id"] if context else None
            match_status = "order-matched" if order_row else "unmatched"
            canonical["order"] = {**canonical.get("order", {}),
                                  "localGdtOrderNumber": order_row["local_gdt_order_number"] if order_row else "",
                                  "identifiers": identifiers}
            canonical["correlation"] = {**canonical.get("correlation", {}),
                                        "matchStatus": match_status, "identifiers": identifiers}
            message_id = self._message(
                connection, order_record_id=order_row["id"] if order_row else None,
                patient_context_id=patient_context_id, direction="inbound", raw_gdt_text=raw,
                parsed_fields=fields, canonical=canonical, timestamp=timestamp, match_status=match_status,
            )
            source_file = str(extras.get("sourceFile", extras.get("source_file", "")) or "")
            attachments = list(canonical.get("attachments") or []) + list(extras.get("attachments") or [])
            for attachment in attachments:
                if not isinstance(attachment, dict):
                    continue
                item = dict(attachment)
                item["source_file"] = item.get("sourceFile", item.get("source_file", source_file))
                self._attachment(
                    connection, order_record_id=order_row["id"] if order_row else None,
                    message_record_id=message_id, role=str(item.pop("role", "result-artifact") or "result-artifact"),
                    timestamp=timestamp, **item,
                )
            self._event(connection, event_type="result-imported",
                        order_record_id=order_row["id"] if order_row else None,
                        patient_context_id=patient_context_id, message_record_id=message_id,
                        timestamp=timestamp,
                        details={"messageType": GDT_RESULT_MESSAGE_TYPE, "matchStatus": match_status})
            self._event(connection, event_type="result-matched" if order_row else "result-unmatched",
                        order_record_id=order_row["id"] if order_row else None,
                        patient_context_id=patient_context_id, message_record_id=message_id,
                        timestamp=timestamp, details={"identifiers": identifiers})
            if order_row:
                connection.execute(
                    "UPDATE local_gdt_order_records SET order_status = ?, updated_at = ? WHERE id = ?",
                    (GDT_ORDER_STATUS_RESULT_RECEIVED, timestamp, order_row["id"]),
                )
                self._event(connection, event_type="status-changed", order_record_id=order_row["id"],
                            patient_context_id=patient_context_id, message_record_id=message_id,
                            timestamp=timestamp, details={"status": GDT_ORDER_STATUS_RESULT_RECEIVED})
        return self._message_by_id(message_id)

    def record_gdt_order_export(self, order_record_id: int, *, export_path: str,
                                status: str, error_text: str = "") -> dict[str, Any]:
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT * FROM local_gdt_order_records WHERE id = ?", (order_record_id,)).fetchone()
            if not row:
                raise KeyError(order_record_id)
            connection.execute(
                "UPDATE local_gdt_order_records SET export_path = ?, error_text = ?, updated_at = ? WHERE id = ?",
                (export_path, error_text, timestamp, order_record_id),
            )
            self._event(connection, event_type="order-exported" if status == "exported" else "order-export-failed",
                        order_record_id=order_record_id, patient_context_id=row["gdt_patient_context_id"],
                        timestamp=timestamp,
                        details={"status": status, "path": export_path, "error": error_text})
        return self.get_gdt_order_record(order_record_id)

    def list_gdt_order_records(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM local_gdt_order_records ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [self._project_order(row) for row in rows]

    def get_gdt_order_record(self, record_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM local_gdt_order_records WHERE id = ?", (record_id,)).fetchone()
        if not row:
            raise KeyError(record_id)
        return self._project_order(row)

    def list_gdt_messages(self, order_record_id: int | None = None) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if order_record_id is None:
                rows = connection.execute(
                    "SELECT * FROM local_gdt_message_records ORDER BY created_at DESC, id DESC"
                ).fetchall()
            else:
                rows = connection.execute(
                    """SELECT * FROM local_gdt_message_records WHERE order_record_id = ?
                       ORDER BY created_at DESC, id DESC""", (order_record_id,),
                ).fetchall()
        return [gdt_mapper.project_message(row) for row in rows]

    def list_gdt_attachments(self, order_record_id: int | None = None) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if order_record_id is None:
                rows = connection.execute(
                    "SELECT * FROM local_gdt_attachment_records ORDER BY created_at DESC, id DESC"
                ).fetchall()
            else:
                rows = connection.execute(
                    """SELECT * FROM local_gdt_attachment_records WHERE order_record_id = ?
                       ORDER BY created_at ASC, id ASC""", (order_record_id,),
                ).fetchall()
        return [gdt_mapper.project_attachment(row) for row in rows]

    def list_gdt_events(self, order_record_id: int | None = None) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if order_record_id is None:
                rows = connection.execute(
                    "SELECT * FROM local_gdt_workflow_events ORDER BY created_at DESC, id DESC"
                ).fetchall()
            else:
                order = connection.execute(
                    "SELECT gdt_patient_context_id FROM local_gdt_order_records WHERE id = ?", (order_record_id,)
                ).fetchone()
                context_id = order["gdt_patient_context_id"] if order else None
                rows = connection.execute(
                    """SELECT * FROM local_gdt_workflow_events
                       WHERE order_record_id = ? OR (
                           ? IS NOT NULL AND patient_context_id = ? AND order_record_id IS NULL
                       ) ORDER BY created_at ASC, id ASC""",
                    (order_record_id, context_id, context_id),
                ).fetchall()
        return [gdt_mapper.project_event(row) for row in rows]

    def list_gdt_workbench(self, *, bridge_inbox: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        orders, messages, attachments = self.list_gdt_order_records(), self.list_gdt_messages(), self.list_gdt_attachments()
        return gdt_mapper.project_workbench(
            patients=self._patient_list_loader(), orders=orders, messages=messages,
            attachments=attachments, bridge_inbox=bridge_inbox,
        )

    def list_gdt_orders(self) -> list[dict[str, Any]]:
        return [{"id": item["id"], "orderNumber": item["localGdtOrderNumber"],
                 "status": item["status"], "updatedAt": item["updatedAt"]}
                for item in self.list_gdt_order_records()]

    def _message_by_id(self, record_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM local_gdt_message_records WHERE id = ?", (record_id,)).fetchone()
        if not row:
            raise KeyError(record_id)
        return gdt_mapper.project_message(row)

    def _project_order(self, row: Row) -> dict[str, Any]:
        attachments, messages, events = self.list_gdt_attachments(row["id"]), self.list_gdt_messages(row["id"]), self.list_gdt_events(row["id"])
        return gdt_mapper.project_order(
            row, attachments=attachments, messages=messages, events=events,
        )
