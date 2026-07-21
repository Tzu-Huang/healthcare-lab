"""Repeatable, non-destructive SQLite startup maintenance."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from backend.domain.patient import CANONICAL_MRN_PATTERN


def seed_patient_mrn_sequence(connection: sqlite3.Connection) -> None:
    highest_existing = 0
    for row in connection.execute("SELECT mrn FROM local_patient_records"):
        normalized_mrn = str(row["mrn"] or "").strip().upper()
        if CANONICAL_MRN_PATTERN.fullmatch(normalized_mrn):
            highest_existing = max(highest_existing, int(normalized_mrn[4:]))
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
