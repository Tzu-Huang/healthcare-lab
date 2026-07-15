"""SQLite persistence for the lab server control plane."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager
from sqlite3 import Connection, Row
from threading import RLock
from typing import Any

from backend.domain.errors import SimulatorValidationError
from backend.domain.lab import (
    LAB_HEALTH_STATUSES,
    LAB_OPERATION_ACTIONS,
    LAB_SERVER_PROTOCOLS,
    LAB_SERVER_TYPES,
)

ConnectionFactory = Callable[[], AbstractContextManager[Connection]]


class LabRepository:
    def __init__(
        self,
        connection_factory: ConnectionFactory,
        lock: RLock,
        *,
        timestamp_factory: Callable[[], str],
    ) -> None:
        self._connect = connection_factory
        self._lock = lock
        self._timestamp = timestamp_factory

    @property
    def lock(self) -> RLock:
        return self._lock

    @staticmethod
    def validate_server_payload(
        payload: dict[str, Any], *, partial: bool = False
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SimulatorValidationError("Server payload must be a JSON object.")
        validated: dict[str, Any] = {}
        if "name" in payload or not partial:
            name = str(payload.get("name", "")).strip()
            if not name:
                raise SimulatorValidationError("Server name is required.")
            validated["name"] = name
        if "serverType" in payload or "server_type" in payload or not partial:
            server_type = str(payload.get("serverType", payload.get("server_type", ""))).strip()
            if server_type not in LAB_SERVER_TYPES:
                raise SimulatorValidationError(
                    f"Server type must be one of: {', '.join(LAB_SERVER_TYPES)}."
                )
            validated["server_type"] = server_type
        for source_key, target_key in (
            ("description", "description"), ("host", "host"),
            ("baseUrl", "base_url"), ("base_url", "base_url"), ("version", "version"),
        ):
            if source_key in payload:
                validated[target_key] = str(payload.get(source_key, "")).strip()
        if "port" in payload:
            raw_port = payload.get("port")
            if raw_port in (None, ""):
                validated["port"] = None
            else:
                try:
                    port = int(raw_port)
                except (TypeError, ValueError) as exc:
                    raise SimulatorValidationError(
                        "Port must be an integer between 1 and 65535."
                    ) from exc
                if not 1 <= port <= 65535:
                    raise SimulatorValidationError("Port must be an integer between 1 and 65535.")
                validated["port"] = port
        if "protocol" in payload or not partial:
            protocol = str(payload.get("protocol", "None")).strip() or "None"
            if protocol not in LAB_SERVER_PROTOCOLS:
                raise SimulatorValidationError(
                    f"Protocol must be one of: {', '.join(LAB_SERVER_PROTOCOLS)}."
                )
            validated["protocol"] = protocol
        if "enabled" in payload:
            validated["enabled"] = 1 if bool(payload.get("enabled")) else 0
        if "checkConfig" in payload:
            check_config = payload.get("checkConfig") or {}
            if not isinstance(check_config, dict):
                raise SimulatorValidationError("Check config must be a JSON object.")
            validated["check_config_json"] = json.dumps(check_config)
        operation_config = payload.get("operation")
        if isinstance(operation_config, dict):
            if "controlType" in operation_config:
                validated["control_type"] = str(operation_config.get("controlType", "")).strip()
            if "backingService" in operation_config:
                validated["backing_service"] = str(operation_config.get("backingService", "")).strip()
            if "supportedActions" in operation_config:
                actions = operation_config.get("supportedActions") or []
                if not isinstance(actions, list) or not all(isinstance(action, str) for action in actions):
                    raise SimulatorValidationError("Supported actions must be a list of strings.")
                unsupported = [action for action in actions if action not in LAB_OPERATION_ACTIONS]
                if unsupported:
                    raise SimulatorValidationError(
                        f"Unsupported lab operation action: {unsupported[0]}."
                    )
                validated["supported_actions_json"] = json.dumps(actions)
            if "timeoutSeconds" in operation_config:
                try:
                    timeout_seconds = int(operation_config.get("timeoutSeconds"))
                except (TypeError, ValueError) as exc:
                    raise SimulatorValidationError(
                        "Operation timeout must be a positive integer."
                    ) from exc
                if timeout_seconds <= 0:
                    raise SimulatorValidationError("Operation timeout must be a positive integer.")
                validated["operation_timeout_seconds"] = timeout_seconds
            if "smokeProfile" in operation_config:
                validated["smoke_profile"] = str(operation_config.get("smokeProfile", "")).strip()
        endpoint_base_url = validated.get("base_url", str(payload.get("baseUrl", "")).strip())
        endpoint_host = validated.get("host", str(payload.get("host", "")).strip())
        endpoint_port = validated.get("port", payload.get("port"))
        if endpoint_base_url and not endpoint_base_url.startswith(("http://", "https://")):
            raise SimulatorValidationError("Base URL must start with http:// or https://.")
        if not partial and not endpoint_base_url and not (endpoint_host and endpoint_port):
            if validated.get("protocol", "None") not in {"GDT", "None"}:
                raise SimulatorValidationError("Server requires either a base URL or host and port.")
        return validated

    @staticmethod
    def _server_dict(row: Row) -> dict[str, Any]:
        return {
            "id": row["id"], "name": row["name"], "serverType": row["server_type"],
            "description": row["description"], "host": row["host"], "port": row["port"],
            "baseUrl": row["base_url"], "protocol": row["protocol"],
            "enabled": bool(row["enabled"]), "version": row["version"],
            "checkConfig": json.loads(row["check_config_json"] or "{}"),
            "operation": {
                "controlType": row["control_type"], "backingService": row["backing_service"],
                "supportedActions": json.loads(row["supported_actions_json"] or "[]"),
                "timeoutSeconds": row["operation_timeout_seconds"],
                "smokeProfile": row["smoke_profile"],
            },
            "overallStatus": row["overall_status"],
            "checks": {"process": row["process_status"], "application": row["application_status"],
                       "protocol": row["protocol_status"]},
            "lastCheckAt": row["last_check_at"], "recentError": row["recent_error"],
            "createdAt": row["created_at"], "updatedAt": row["updated_at"],
        }

    def list_servers(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM lab_servers ORDER BY enabled DESC, name COLLATE NOCASE"
            ).fetchall()
        return [self._server_dict(row) for row in rows]

    def get_server(self, server_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM lab_servers WHERE id = ?", (server_id,)).fetchone()
        if not row:
            raise KeyError(server_id)
        return self._server_dict(row)

    def create_server(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = self.validate_server_payload(payload)
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            try:
                cursor = connection.execute(
                    """INSERT INTO lab_servers (
                        name, server_type, description, host, port, base_url, protocol, enabled,
                        version, check_config_json, control_type, backing_service,
                        supported_actions_json, operation_timeout_seconds, smoke_profile,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (values["name"], values["server_type"], values.get("description", ""),
                     values.get("host", ""), values.get("port"), values.get("base_url", ""),
                     values.get("protocol", "None"), values.get("enabled", 1),
                     values.get("version", ""), values.get("check_config_json", "{}"),
                     values.get("control_type", ""), values.get("backing_service", ""),
                     values.get("supported_actions_json", "[]"),
                     values.get("operation_timeout_seconds", 60), values.get("smoke_profile", ""),
                     timestamp, timestamp),
                )
            except sqlite3.IntegrityError as exc:
                raise SimulatorValidationError("Server name must be unique.") from exc
            server_id = int(cursor.lastrowid)
        return self.get_server(server_id)

    def update_server(self, server_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        values = self.validate_server_payload(payload, partial=True)
        if not values:
            return self.get_server(server_id)
        assignments = [f"{key} = ?" for key in values] + ["updated_at = ?"]
        params = [*values.values(), self._timestamp(), server_id]
        with self._lock, self._connect() as connection:
            if not connection.execute("SELECT id FROM lab_servers WHERE id = ?", (server_id,)).fetchone():
                raise KeyError(server_id)
            try:
                connection.execute(f"UPDATE lab_servers SET {', '.join(assignments)} WHERE id = ?", params)
            except sqlite3.IntegrityError as exc:
                raise SimulatorValidationError("Server name must be unique.") from exc
        return self.get_server(server_id)

    def update_health(self, server_id: int, *, overall_status: str, process_status: str,
                      application_status: str, protocol_status: str, recent_error: str = "",
                      version: str = "") -> dict[str, Any]:
        if overall_status not in LAB_HEALTH_STATUSES:
            raise SimulatorValidationError("Unknown overall health status.")
        if any(status not in LAB_HEALTH_STATUSES
               for status in (process_status, application_status, protocol_status)):
            raise SimulatorValidationError("Unknown health check status.")
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            if not connection.execute("SELECT id FROM lab_servers WHERE id = ?", (server_id,)).fetchone():
                raise KeyError(server_id)
            connection.execute(
                """UPDATE lab_servers SET overall_status = ?, process_status = ?,
                    application_status = ?, protocol_status = ?, recent_error = ?,
                    version = COALESCE(NULLIF(?, ''), version), last_check_at = ?, updated_at = ?
                    WHERE id = ?""",
                (overall_status, process_status, application_status, protocol_status,
                 recent_error, version, timestamp, timestamp, server_id),
            )
        return self.get_server(server_id)

    def record_operation(self, server_id: int | None, *, service_name: str, action: str,
                         operator: str, result: str, duration_ms: int = 0,
                         progress: list[dict[str, Any]] | None = None, error_text: str = "",
                         started_at: str = "", completed_at: str = "") -> dict[str, Any]:
        normalized_action = action.strip().lower()
        if normalized_action not in LAB_OPERATION_ACTIONS:
            raise SimulatorValidationError(
                f"Unsupported lab operation action: {normalized_action or 'unknown'}."
            )
        normalized_service_name = service_name.strip()
        if not normalized_service_name:
            raise SimulatorValidationError("Operation service name is required.")
        progress_steps = progress or []
        if not isinstance(progress_steps, list):
            raise SimulatorValidationError("Operation progress must be a list.")
        started = started_at or self._timestamp()
        completed = completed_at or self._timestamp()
        with self._lock, self._connect() as connection:
            if server_id is not None and not connection.execute(
                "SELECT id FROM lab_servers WHERE id = ?", (server_id,)
            ).fetchone():
                raise KeyError(server_id)
            cursor = connection.execute(
                """INSERT INTO lab_operation_history (
                    server_id, service_name, action, operator, result, duration_ms,
                    progress_json, error_text, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (server_id, normalized_service_name, normalized_action,
                 operator.strip() or "local-user", result.strip() or "Unknown",
                 max(0, int(duration_ms)), json.dumps(progress_steps), error_text,
                 started, completed),
            )
            operation_id = int(cursor.lastrowid)
        return self.get_operation(operation_id)

    @staticmethod
    def _operation_dict(row: Row) -> dict[str, Any]:
        return {
            "id": row["id"], "serverId": row["server_id"],
            "serviceName": row["service_name"], "action": row["action"],
            "operator": row["operator"], "result": row["result"],
            "durationMs": row["duration_ms"],
            "progress": json.loads(row["progress_json"] or "[]"),
            "error": row["error_text"], "startedAt": row["started_at"],
            "completedAt": row["completed_at"],
        }

    def get_operation(self, operation_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM lab_operation_history WHERE id = ?", (operation_id,)
            ).fetchone()
        if not row:
            raise KeyError(operation_id)
        return self._operation_dict(row)

    def list_operations(self, server_id: int | None = None, *, limit: int = 20) -> list[dict[str, Any]]:
        bounded_limit = min(200, max(1, int(limit)))
        with self._connect() as connection:
            if server_id is None:
                rows = connection.execute(
                    "SELECT * FROM lab_operation_history ORDER BY id DESC LIMIT ?",
                    (bounded_limit,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """SELECT * FROM lab_operation_history WHERE server_id = ?
                    ORDER BY id DESC LIMIT ?""", (server_id, bounded_limit)
                ).fetchall()
        return [self._operation_dict(row) for row in rows]

    # Application-facing names preserve the established lab workflow port.
    list_lab_servers = list_servers
    get_lab_server = get_server
    create_lab_server = create_server
    update_lab_server = update_server
    update_lab_server_health = update_health
    record_lab_operation = record_operation
    get_lab_operation = get_operation
    list_lab_operations = list_operations
