"""SQLite repository for the persistent OIE settings profile."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
import json
from sqlite3 import Connection, Row
import sqlite3
from threading import RLock
from typing import Any, Mapping

from backend.domain.oie import validate_settings_payload as validate_oie_settings_payload
from backend.mappers.oie import project_settings_profile as serialize_oie_settings_profile

ProfileValidator = Callable[[dict[str, Any]], dict[str, Any]]
ProfileSerializer = Callable[[Row, list[Row]], dict[str, Any]]
ConnectionFactory = Callable[[], AbstractContextManager[Connection]]


class OieMappingConflictError(RuntimeError):
    """The managed mapping changed since lifecycle state was inspected."""


_AUDIT_FIELDS = {
    "operation_id", "actor", "operation", "logical_type", "channel_id",
    "before_revision", "after_revision", "classification", "outcome",
    "error_category", "changed_owned_fields",
}
_AUDIT_LIMITS = {
    "operation_id": 128, "actor": 80, "operation": 40, "logical_type": 80,
    "channel_id": 128, "before_revision": 40, "after_revision": 40,
    "classification": 40, "outcome": 40, "error_category": 80,
}


class OieSettingsRepository:
    def __init__(self, connection_factory: ConnectionFactory, lock: RLock, *, profile_name: str,
                 validator: ProfileValidator, serializer: ProfileSerializer,
                 timestamp_factory: Callable[[], str]) -> None:
        self._connect = connection_factory
        self._lock = lock
        self._profile_name = profile_name
        self._validate = validator
        self._serialize = serializer
        self._timestamp = timestamp_factory

    def get(self) -> dict[str, Any]:
        with self._connect() as connection:
            profile = connection.execute(
                "SELECT * FROM oie_settings_profiles WHERE profile_name = ?", (self._profile_name,)
            ).fetchone()
            if not profile:
                raise KeyError(self._profile_name)
            mappings = connection.execute(
                """SELECT * FROM oie_managed_channel_mappings WHERE profile_id = ?
                ORDER BY logical_type COLLATE NOCASE, id""", (profile["id"],)
            ).fetchall()
        return self._serialize(profile, mappings)

    def get_management_api_configuration(self) -> dict[str, Any]:
        """Return the private persistence values needed only by composition."""
        with self._connect() as connection:
            profile = connection.execute(
                "SELECT * FROM oie_settings_profiles WHERE profile_name = ?", (self._profile_name,)
            ).fetchone()
        if not profile:
            raise KeyError(self._profile_name)
        return {
            "base_url": profile["management_api_base_url"],
            "username": profile["management_api_username"],
            "password": profile["management_api_password"],
            "tls_verify": bool(profile["management_api_tls_verify"]),
            "timeout_seconds": float(profile["management_api_timeout_seconds"]),
        }

    def update(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = self._validate(payload)
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            profile = connection.execute(
                "SELECT * FROM oie_settings_profiles WHERE profile_name = ?", (self._profile_name,)
            ).fetchone()
            if not profile:
                raise KeyError(self._profile_name)
            password = values["management_api_password"] if values["password_provided"] else profile["management_api_password"]
            connection.execute(
                """UPDATE oie_settings_profiles
                SET management_api_base_url = ?, management_api_username = ?, management_api_password = ?,
                    management_api_tls_verify = ?, management_api_timeout_seconds = ?, result_listener_host = ?,
                    result_listener_port = ?, result_listener_mllp_framing = ?, result_listener_auto_start = ?,
                    updated_at = ? WHERE id = ?""",
                (values["management_api_base_url"], values["management_api_username"], password,
                 values["management_api_tls_verify"], values["management_api_timeout_seconds"],
                 values["result_listener_host"], values["result_listener_port"],
                 values["result_listener_mllp_framing"], values["result_listener_auto_start"],
                 timestamp, profile["id"]),
            )
            connection.execute("DELETE FROM oie_managed_channel_mappings WHERE profile_id = ?", (profile["id"],))
            for mapping in values["managed_channels"]:
                connection.execute(
                    """INSERT INTO oie_managed_channel_mappings (
                        profile_id, logical_type, oie_channel_id, channel_name, template_version,
                        last_known_revision, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (profile["id"], mapping["logical_type"], mapping["oie_channel_id"],
                     mapping["channel_name"], mapping["template_version"], mapping["last_known_revision"],
                     timestamp, timestamp),
                )
        return self.get()

    def compare_and_update_managed_channel_mapping(
        self, *, logical_type: str, expected_channel_id: str,
        expected_revision: str, channel_id: str, channel_name: str,
        template_version: str, revision: str,
        audit_event: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        logical_type = self._required_text(logical_type, "logical_type", 80).lower()
        values = {
            "channel_id": self._bounded_text(channel_id, "channel_id", 128),
            "channel_name": self._required_text(channel_name, "channel_name", 160),
            "template_version": self._bounded_text(template_version, "template_version", 40),
            "revision": self._bounded_text(revision, "revision", 40),
        }
        expected_channel_id = self._bounded_text(expected_channel_id, "expected_channel_id", 128)
        expected_revision = self._bounded_text(expected_revision, "expected_revision", 40)
        safe_audit = self._validate_audit(audit_event) if audit_event is not None else None
        timestamp = self._timestamp()
        try:
            with self._lock, self._connect() as connection:
                profile_id = self._profile_id(connection)
                cursor = connection.execute(
                    """UPDATE oie_managed_channel_mappings
                    SET oie_channel_id = ?, channel_name = ?, template_version = ?,
                        last_known_revision = ?, updated_at = ?
                    WHERE profile_id = ? AND logical_type = ?
                      AND oie_channel_id = ? AND last_known_revision = ?""",
                    (values["channel_id"], values["channel_name"], values["template_version"],
                     values["revision"], timestamp, profile_id, logical_type,
                     expected_channel_id, expected_revision),
                )
                if cursor.rowcount == 0 and not expected_channel_id and not expected_revision:
                    cursor = connection.execute(
                        """INSERT INTO oie_managed_channel_mappings (
                            profile_id, logical_type, oie_channel_id, channel_name,
                            template_version, last_known_revision, created_at, updated_at
                        ) SELECT ?, ?, ?, ?, ?, ?, ?, ?
                        WHERE NOT EXISTS (
                            SELECT 1 FROM oie_managed_channel_mappings
                            WHERE profile_id = ? AND logical_type = ?
                        )""",
                        (profile_id, logical_type, values["channel_id"], values["channel_name"],
                         values["template_version"], values["revision"], timestamp, timestamp,
                         profile_id, logical_type),
                    )
                if cursor.rowcount != 1:
                    raise OieMappingConflictError(
                        f"Managed Channel mapping {logical_type!r} changed concurrently."
                    )
                if safe_audit is not None:
                    self._insert_audit(connection, profile_id, safe_audit, timestamp)
        except sqlite3.IntegrityError as exc:
            raise OieMappingConflictError(
                f"Managed Channel mapping {logical_type!r} conflicts with current identity."
            ) from exc
        return self._mapping(logical_type)

    def compare_and_clear_managed_channel_mapping(
        self, *, logical_type: str, expected_channel_id: str,
        expected_revision: str, audit_event: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        logical_type = self._required_text(logical_type, "logical_type", 80).lower()
        expected_channel_id = self._bounded_text(expected_channel_id, "expected_channel_id", 128)
        expected_revision = self._bounded_text(expected_revision, "expected_revision", 40)
        safe_audit = self._validate_audit(audit_event) if audit_event is not None else None
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            profile_id = self._profile_id(connection)
            cursor = connection.execute(
                """UPDATE oie_managed_channel_mappings
                SET oie_channel_id = '', last_known_revision = '', updated_at = ?
                WHERE profile_id = ? AND logical_type = ?
                  AND oie_channel_id = ? AND last_known_revision = ?""",
                (timestamp, profile_id, logical_type, expected_channel_id, expected_revision),
            )
            if cursor.rowcount != 1:
                raise OieMappingConflictError(
                    f"Managed Channel mapping {logical_type!r} changed concurrently."
                )
            if safe_audit is not None:
                self._insert_audit(connection, profile_id, safe_audit, timestamp)
        return self._mapping(logical_type)

    def append_managed_channel_lifecycle_audit(
        self, audit_event: Mapping[str, Any]
    ) -> int:
        safe_audit = self._validate_audit(audit_event)
        with self._lock, self._connect() as connection:
            return self._insert_audit(
                connection, self._profile_id(connection), safe_audit, self._timestamp()
            )

    def list_managed_channel_lifecycle_audits(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            profile_id = self._profile_id(connection)
            rows = connection.execute(
                """SELECT operation_id, actor, operation, logical_type, oie_channel_id,
                    before_revision, after_revision, classification, outcome,
                    error_category, changed_fields_json, created_at
                FROM oie_managed_channel_lifecycle_audits
                WHERE profile_id = ? ORDER BY created_at DESC, id DESC""",
                (profile_id,),
            ).fetchall()
        return [
            {"operation_id": row["operation_id"], "actor": row["actor"],
             "operation": row["operation"], "logical_type": row["logical_type"],
             "channel_id": row["oie_channel_id"], "before_revision": row["before_revision"],
             "after_revision": row["after_revision"], "classification": row["classification"],
             "outcome": row["outcome"], "error_category": row["error_category"],
             "changed_owned_fields": json.loads(row["changed_fields_json"]),
             "created_at": row["created_at"]}
            for row in rows
        ]

    def _profile_id(self, connection: Connection) -> int:
        row = connection.execute(
            "SELECT id FROM oie_settings_profiles WHERE profile_name = ?", (self._profile_name,)
        ).fetchone()
        if row is None:
            raise KeyError(self._profile_name)
        return int(row["id"])

    def _mapping(self, logical_type: str) -> dict[str, Any]:
        return next(
            item for item in self.get()["managedChannels"]
            if item["logicalType"] == logical_type
        )

    @classmethod
    def _validate_audit(cls, event: Mapping[str, Any] | None) -> dict[str, Any]:
        if not isinstance(event, Mapping):
            raise ValueError("Lifecycle audit event must be a mapping.")
        unknown = set(event) - _AUDIT_FIELDS
        if unknown:
            raise ValueError(f"Lifecycle audit contains unsupported fields: {sorted(unknown)!r}.")
        required = {"operation_id", "operation", "logical_type", "classification", "outcome"}
        missing = required - set(event)
        if missing:
            raise ValueError(f"Lifecycle audit is missing fields: {sorted(missing)!r}.")
        safe = {
            key: cls._bounded_text(event.get(key, ""), key, limit)
            for key, limit in _AUDIT_LIMITS.items()
        }
        if not safe["operation_id"] or not safe["operation"] or not safe["logical_type"]:
            raise ValueError("Lifecycle audit identity fields must not be empty.")
        fields = event.get("changed_owned_fields", [])
        if not isinstance(fields, (list, tuple)) or len(fields) > 64:
            raise ValueError("Lifecycle audit changed_owned_fields must be a bounded list.")
        safe["changed_owned_fields"] = [
            cls._required_text(value, "changed_owned_fields", 160) for value in fields
        ]
        safe["actor"] = safe["actor"] or "local-operator"
        return safe

    @staticmethod
    def _bounded_text(value: Any, field: str, limit: int) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string.")
        value = value.strip()
        if len(value) > limit:
            raise ValueError(f"{field} exceeds its {limit}-character limit.")
        return value

    @classmethod
    def _required_text(cls, value: Any, field: str, limit: int) -> str:
        value = cls._bounded_text(value, field, limit)
        if not value:
            raise ValueError(f"{field} must not be empty.")
        return value

    @staticmethod
    def _insert_audit(
        connection: Connection, profile_id: int, event: Mapping[str, Any], timestamp: str
    ) -> int:
        cursor = connection.execute(
            """INSERT INTO oie_managed_channel_lifecycle_audits (
                profile_id, operation_id, actor, operation, logical_type, oie_channel_id,
                before_revision, after_revision, classification, outcome, error_category,
                changed_fields_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (profile_id, event["operation_id"], event["actor"], event["operation"],
             event["logical_type"], event["channel_id"], event["before_revision"],
             event["after_revision"], event["classification"], event["outcome"],
             event["error_category"],
             json.dumps(event["changed_owned_fields"], separators=(",", ":"), sort_keys=True),
             timestamp),
        )
        return int(cursor.lastrowid)
