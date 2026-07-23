"""Atomic persistence for closed typed integration settings profiles."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from sqlite3 import Connection
from threading import RLock
from typing import Any

from backend.domain.integration_settings import (
    PROFILE_FIELDS,
    PROFILE_SECRET_FIELDS,
    SecretAction,
    SecretMutation,
    TypedProfile,
    validate_profile,
)

ConnectionFactory = Callable[[], AbstractContextManager[Connection]]
AUDIT_OPERATIONS = frozenset({"bootstrap", "update", "remove-secret"})


class IntegrationSettingsRepository:
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

    def _require_profile_type(self, profile_type: str) -> None:
        if profile_type not in PROFILE_FIELDS:
            raise KeyError(profile_type)

    def exists(self, profile_type: str) -> bool:
        self._require_profile_type(profile_type)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM integration_settings_profiles WHERE profile_type = ?",
                (profile_type,),
            ).fetchone()
        return row is not None

    def get_private(self, profile_type: str) -> dict[str, Any]:
        self._require_profile_type(profile_type)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM integration_settings_profiles WHERE profile_type = ?",
                (profile_type,),
            ).fetchone()
            if row is None:
                raise KeyError(profile_type)
            secret_rows = connection.execute(
                """
                SELECT field_name, secret_value
                FROM integration_settings_secrets
                WHERE profile_id = ?
                ORDER BY field_name
                """,
                (row["id"],),
            ).fetchall()
        fields = json.loads(row["public_payload_json"])
        validate_profile(profile_type, fields)
        return {
            "profileType": row["profile_type"],
            "profileName": row["profile_name"],
            "schemaVersion": row["schema_version"],
            "fields": fields,
            "secrets": {item["field_name"]: item["secret_value"] for item in secret_rows},
            "bootstrapSource": row["bootstrap_source"],
        }

    def get_public(self, profile_type: str) -> dict[str, Any]:
        private = self.get_private(profile_type)
        configured = {
            field: {"configured": bool(private["secrets"].get(field))}
            for field in sorted(PROFILE_SECRET_FIELDS[profile_type])
        }
        return {
            "profileType": private["profileType"],
            "profileName": private["profileName"],
            "schemaVersion": private["schemaVersion"],
            "fields": private["fields"],
            "secrets": configured,
        }

    def create_if_missing(
        self,
        profile: TypedProfile,
        *,
        secrets: Mapping[str, str],
        bootstrap_source: str,
        actor: str = "startup-bootstrap",
    ) -> bool:
        validated = validate_profile(profile.profile_type, profile.fields)
        if validated != profile:
            raise ValueError("Profile must be the canonical validated projection.")
        secret_fields = PROFILE_SECRET_FIELDS[profile.profile_type]
        unknown_secrets = set(secrets) - secret_fields
        if unknown_secrets:
            raise ValueError("Unsupported secret field.")
        timestamp = self._timestamp()
        changed_fields = sorted([*profile.fields, *secrets])
        with self._lock, self._connect() as connection:
            existing = connection.execute(
                "SELECT 1 FROM integration_settings_profiles WHERE profile_type = ?",
                (profile.profile_type,),
            ).fetchone()
            if existing:
                return False
            cursor = connection.execute(
                """
                INSERT INTO integration_settings_profiles (
                    profile_type, profile_name, schema_version, public_payload_json,
                    bootstrap_source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.profile_type,
                    profile.profile_name,
                    profile.schema_version,
                    json.dumps(profile.fields, sort_keys=True, separators=(",", ":")),
                    bootstrap_source,
                    timestamp,
                    timestamp,
                ),
            )
            profile_id = int(cursor.lastrowid)
            for field, value in secrets.items():
                if str(value):
                    connection.execute(
                        """
                        INSERT INTO integration_settings_secrets (
                            profile_id, field_name, secret_value, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (profile_id, field, str(value), timestamp, timestamp),
                    )
            self._append_audit(
                connection,
                profile_id,
                actor=actor,
                operation="bootstrap",
                changed_fields=changed_fields,
                timestamp=timestamp,
            )
        return True

    def replace(
        self,
        profile: TypedProfile,
        *,
        secret_mutations: Mapping[str, SecretMutation],
        actor: str = "local-operator",
    ) -> dict[str, Any]:
        validated = validate_profile(profile.profile_type, profile.fields)
        if validated != profile:
            raise ValueError("Profile must be the canonical validated projection.")
        secret_fields = PROFILE_SECRET_FIELDS[profile.profile_type]
        if set(secret_mutations) - secret_fields:
            raise ValueError("Unsupported secret field.")
        timestamp = self._timestamp()
        changed_fields = list(profile.fields)
        changed_fields.extend(
            field
            for field, mutation in secret_mutations.items()
            if mutation.action is not SecretAction.PRESERVE
        )
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM integration_settings_profiles WHERE profile_type = ?",
                (profile.profile_type,),
            ).fetchone()
            if row is None:
                raise KeyError(profile.profile_type)
            profile_id = int(row["id"])
            connection.execute(
                """
                UPDATE integration_settings_profiles
                SET profile_name = ?, schema_version = ?, public_payload_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    profile.profile_name,
                    profile.schema_version,
                    json.dumps(profile.fields, sort_keys=True, separators=(",", ":")),
                    timestamp,
                    profile_id,
                ),
            )
            for field, mutation in secret_mutations.items():
                if mutation.action is SecretAction.PRESERVE:
                    continue
                if mutation.action is SecretAction.REMOVE:
                    connection.execute(
                        "DELETE FROM integration_settings_secrets WHERE profile_id = ? AND field_name = ?",
                        (profile_id, field),
                    )
                    continue
                connection.execute(
                    """
                    INSERT INTO integration_settings_secrets (
                        profile_id, field_name, secret_value, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(profile_id, field_name) DO UPDATE SET
                        secret_value = excluded.secret_value,
                        updated_at = excluded.updated_at
                    """,
                    (profile_id, field, mutation.value, timestamp, timestamp),
                )
            self._append_audit(
                connection,
                profile_id,
                actor=actor,
                operation=(
                    "remove-secret"
                    if any(
                        item.action is SecretAction.REMOVE
                        for item in secret_mutations.values()
                    )
                    else "update"
                ),
                changed_fields=sorted(set(changed_fields)),
                timestamp=timestamp,
            )
        return self.get_public(profile.profile_type)

    def list_audits(self, profile_type: str) -> list[dict[str, Any]]:
        self._require_profile_type(profile_type)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT a.actor, a.operation, a.changed_fields_json, a.outcome, a.created_at
                FROM integration_settings_mutation_audits a
                JOIN integration_settings_profiles p ON p.id = a.profile_id
                WHERE p.profile_type = ?
                ORDER BY a.id
                """,
                (profile_type,),
            ).fetchall()
        return [
            {
                "actor": row["actor"],
                "operation": row["operation"],
                "changedFields": json.loads(row["changed_fields_json"]),
                "outcome": row["outcome"],
                "createdAt": row["created_at"],
            }
            for row in rows
        ]

    @staticmethod
    def _append_audit(
        connection: Connection,
        profile_id: int,
        *,
        actor: str,
        operation: str,
        changed_fields: list[str],
        timestamp: str,
    ) -> None:
        if operation not in AUDIT_OPERATIONS:
            raise ValueError("Unsupported settings audit operation.")
        connection.execute(
            """
            INSERT INTO integration_settings_mutation_audits (
                profile_id, actor, operation, changed_fields_json, outcome, created_at
            ) VALUES (?, ?, ?, ?, 'success', ?)
            """,
            (
                profile_id,
                str(actor or "local-operator")[:64],
                operation,
                json.dumps(changed_fields, separators=(",", ":")),
                timestamp,
            ),
        )
