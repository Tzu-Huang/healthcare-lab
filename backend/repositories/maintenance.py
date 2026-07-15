"""Repeatable, non-destructive SQLite startup maintenance."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from typing import Any


def seed_patient_mrn_sequence(connection: sqlite3.Connection) -> None:
    highest_existing = 0
    for row in connection.execute("SELECT mrn FROM local_patient_records"):
        match = re.fullmatch(r"MRN-(\d+)", str(row["mrn"] or ""))
        if match:
            highest_existing = max(highest_existing, int(match.group(1)))
    connection.execute(
        """
        INSERT INTO local_identifier_sequences (name, next_value)
        VALUES ('patient_mrn', ?)
        ON CONFLICT(name) DO UPDATE SET
            next_value = MAX(local_identifier_sequences.next_value, excluded.next_value)
        """,
        (highest_existing + 1,),
    )


def seed_oie_settings_profile(
    connection: sqlite3.Connection,
    *,
    profile_name: str,
    management_api_base_url: str,
    management_api_username: str,
    management_api_password: str,
    management_api_timeout_seconds: float,
    result_listener_host: str,
    result_listener_port: int,
    timestamp_factory: Callable[[], str],
) -> None:
    timestamp = timestamp_factory()
    connection.execute(
        """
        INSERT INTO oie_settings_profiles (
            profile_name, management_api_base_url, management_api_username,
            management_api_password, management_api_tls_verify,
            management_api_timeout_seconds, result_listener_host,
            result_listener_port, result_listener_mllp_framing,
            result_listener_auto_start, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, 0, ?, ?, ?, 1, 1, ?, ?)
        ON CONFLICT(profile_name) DO NOTHING
        """,
        (
            profile_name,
            management_api_base_url,
            management_api_username,
            management_api_password,
            management_api_timeout_seconds,
            result_listener_host,
            result_listener_port,
            timestamp,
            timestamp,
        ),
    )


def seed_lab_servers(
    connection: sqlite3.Connection,
    *,
    defaults: Sequence[Mapping[str, Any]],
    operation_metadata: Mapping[str, Mapping[str, Any]],
    timestamp_factory: Callable[[], str],
) -> None:
    timestamp = timestamp_factory()
    fallback_metadata = {
        "control_type": "external",
        "backing_service": "",
        "supported_actions": ["status", "smoke"],
        "timeout_seconds": 60,
        "smoke_profile": "",
    }
    for item in defaults:
        metadata = operation_metadata.get(str(item["name"]), fallback_metadata)
        supported_actions_json = json.dumps(metadata["supported_actions"])
        check_config_json = json.dumps(item.get("check_config", {}))
        existing = connection.execute(
            "SELECT id FROM lab_servers WHERE name = ?", (item["name"],)
        ).fetchone()
        if existing:
            connection.execute(
                """
                UPDATE lab_servers
                SET control_type = ?, backing_service = ?, supported_actions_json = ?,
                    operation_timeout_seconds = ?, smoke_profile = ?,
                    check_config_json = CASE
                        WHEN check_config_json IN ('', '{}') THEN ?
                        ELSE check_config_json
                    END
                WHERE id = ?
                """,
                (
                    metadata["control_type"],
                    metadata["backing_service"],
                    supported_actions_json,
                    metadata["timeout_seconds"],
                    metadata["smoke_profile"],
                    check_config_json,
                    existing["id"],
                ),
            )
        else:
            connection.execute(
                """
                INSERT INTO lab_servers (
                    name, server_type, description, host, port, base_url, protocol,
                    enabled, version, check_config_json, control_type, backing_service,
                    supported_actions_json, operation_timeout_seconds, smoke_profile,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, '', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["name"],
                    item["server_type"],
                    item["description"],
                    item["host"],
                    item["port"],
                    item["base_url"],
                    item["protocol"],
                    check_config_json,
                    metadata["control_type"],
                    metadata["backing_service"],
                    supported_actions_json,
                    metadata["timeout_seconds"],
                    metadata["smoke_profile"],
                    timestamp,
                    timestamp,
                ),
            )


def _json_value(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return fallback


def _dicom_first_value(payload: dict[str, Any], tag: str, default: str = "") -> str:
    element = payload.get(tag) if isinstance(payload, dict) else None
    if not isinstance(element, dict):
        return default
    values = element.get("Value")
    if not isinstance(values, list) or not values:
        return default
    value = values[0]
    if isinstance(value, dict):
        return str(value.get("Alphabetic") or default).strip()
    return str(value or default).strip()


def _dcm4chee_sps_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sequence = payload.get("00400100") if isinstance(payload, dict) else None
    if not isinstance(sequence, dict):
        return {}
    values = sequence.get("Value")
    if not isinstance(values, list) or not values or not isinstance(values[0], dict):
        return {}
    return values[0]


def backfill_dcm4chee_mwl_mappings(
    connection: sqlite3.Connection,
    *,
    order_default_text: str,
    create_operation: str,
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
        sps_payload = _dcm4chee_sps_payload(request_payload)
        patient_id = _dicom_first_value(request_payload, "00100020", row["mrn"])
        issuer = _dicom_first_value(request_payload, "00100021", row["profile_name"])
        worklist_label = _dicom_first_value(
            request_payload,
            "00741202",
            str(row["order_code_text"] or row["order_code"] or order_default_text).strip(),
        )
        scheduled_station = row["scheduled_station_ae_title"] or _dicom_first_value(
            sps_payload,
            "00400001",
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
                scheduled_station,
                row["local_dcm4chee_order_number"],
                patient_id,
                issuer,
                row["accession_number"],
                row["requested_procedure_id"],
                row["scheduled_procedure_step_id"],
                row["study_instance_uid"],
                worklist_label,
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
