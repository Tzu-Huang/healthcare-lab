"""Atomic persistence for closed typed integration settings profiles."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from sqlite3 import Connection
from threading import RLock
from typing import Any

from backend.domain.integration_settings import (
    DCM4CHEE_DEFAULT_TIMEOUT_SECONDS,
    DCM4CHEE_PROFILE_TYPE,
    MEDPLUM_DEFAULT_TIMEOUT_SECONDS,
    MEDPLUM_DEFAULT_WEB_UI_URL,
    MEDPLUM_PROFILE_TYPE,
    PROFILE_FIELDS,
    PROFILE_SECRET_FIELDS,
    SecretAction,
    SecretMutation,
    TypedProfile,
    validate_profile,
)

ConnectionFactory = Callable[[], AbstractContextManager[Connection]]
AUDIT_OPERATIONS = frozenset({"bootstrap", "update", "remove-secret"})
MEDPLUM_VERIFICATION_STAGES = (
    "metadata",
    "oauth",
    "authenticated-read",
)
MEDPLUM_VERIFICATION_STATES = frozenset(
    {"healthy", "degraded", "disabled", "failed", "unavailable"}
)
MEDPLUM_STAGE_STATES = frozenset({"passed", "failed", "skipped", "disabled"})
MEDPLUM_STAGE_CATEGORIES = frozenset(
    {
        "disabled",
        "invalid-configuration",
        "reachable",
        "http-error",
        "connection-failure",
        "not-configured",
        "authorized",
        "authorization-failure",
        "oauth-unavailable",
        "readable",
        "read-failure",
        "unavailable",
    }
)


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

    def has_dcm4chee_dependencies(self) -> bool:
        tables = (
            "local_dcm4chee_mwl_mappings",
            "local_dcm4chee_patient_syncs",
            "local_dcm4chee_result_records",
        )
        with self._connect() as connection:
            return any(
                connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
                is not None
                for table in tables
            )

    def migrate_medplum_profile(self) -> bool:
        """Idempotently evolve pre-ZAC-73 JSON without consulting environment."""
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """SELECT id, schema_version, public_payload_json
                FROM integration_settings_profiles WHERE profile_type = ?""",
                (MEDPLUM_PROFILE_TYPE,),
            ).fetchone()
            if row is None:
                return False
            fields = json.loads(row["public_payload_json"])
            changed = False
            if "webUiUrl" not in fields:
                fields["webUiUrl"] = MEDPLUM_DEFAULT_WEB_UI_URL
                changed = True
            if "timeoutSeconds" not in fields:
                fields["timeoutSeconds"] = MEDPLUM_DEFAULT_TIMEOUT_SECONDS
                changed = True
            profile = validate_profile(MEDPLUM_PROFILE_TYPE, fields)
            if not changed and int(row["schema_version"]) == profile.schema_version:
                return False
            connection.execute(
                """UPDATE integration_settings_profiles
                SET schema_version = ?, public_payload_json = ?,
                    configuration_revision = configuration_revision + 1,
                    updated_at = ?
                WHERE id = ?""",
                (
                    profile.schema_version,
                    json.dumps(profile.fields, sort_keys=True, separators=(",", ":")),
                    timestamp,
                    row["id"],
                ),
            )
        return True

    def migrate_dcm4chee_profile(self) -> bool:
        """Idempotently add typed transport defaults without replacing operator data."""
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """SELECT id, schema_version, public_payload_json
                FROM integration_settings_profiles WHERE profile_type = ?""",
                (DCM4CHEE_PROFILE_TYPE,),
            ).fetchone()
            if row is None:
                return False
            fields = json.loads(row["public_payload_json"])
            changed = False
            if "timeoutSeconds" not in fields:
                fields["timeoutSeconds"] = DCM4CHEE_DEFAULT_TIMEOUT_SECONDS
                changed = True
            profile = validate_profile(DCM4CHEE_PROFILE_TYPE, fields)
            if not changed and int(row["schema_version"]) == profile.schema_version:
                return False
            connection.execute(
                """UPDATE integration_settings_profiles
                SET schema_version = ?, public_payload_json = ?,
                    configuration_revision = configuration_revision + 1,
                    updated_at = ?
                WHERE id = ?""",
                (
                    profile.schema_version,
                    json.dumps(profile.fields, sort_keys=True, separators=(",", ":")),
                    timestamp,
                    row["id"],
                ),
            )
        return True

    def get_medplum_configuration_revision(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT configuration_revision
                FROM integration_settings_profiles WHERE profile_type = ?""",
                (MEDPLUM_PROFILE_TYPE,),
            ).fetchone()
        if row is None:
            raise KeyError(MEDPLUM_PROFILE_TYPE)
        return int(row["configuration_revision"])

    def get_medplum_verification(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT v.configuration_revision, v.state, v.stages_json, v.checked_at
                FROM medplum_verification_state v
                JOIN integration_settings_profiles p ON p.id = v.profile_id
                WHERE p.profile_type = ?
                """,
                (MEDPLUM_PROFILE_TYPE,),
            ).fetchone()
        if row is None:
            return None
        return {
            "configurationRevision": int(row["configuration_revision"]),
            "state": str(row["state"]),
            "stages": json.loads(row["stages_json"]),
            "checkedAt": str(row["checked_at"]),
        }

    def record_medplum_verification(
        self,
        configuration_revision: int,
        report: Mapping[str, Any],
    ) -> bool:
        state, stages = self._bounded_medplum_verification(report)
        checked_at = self._timestamp()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """SELECT id, configuration_revision
                FROM integration_settings_profiles WHERE profile_type = ?""",
                (MEDPLUM_PROFILE_TYPE,),
            ).fetchone()
            if row is None:
                raise KeyError(MEDPLUM_PROFILE_TYPE)
            if int(row["configuration_revision"]) != int(configuration_revision):
                return False
            connection.execute(
                """
                INSERT INTO medplum_verification_state (
                    profile_id, configuration_revision, state, stages_json, checked_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(profile_id) DO UPDATE SET
                    configuration_revision = excluded.configuration_revision,
                    state = excluded.state,
                    stages_json = excluded.stages_json,
                    checked_at = excluded.checked_at
                """,
                (
                    int(row["id"]),
                    int(configuration_revision),
                    state,
                    json.dumps(stages, separators=(",", ":")),
                    checked_at,
                ),
            )
        return True

    @staticmethod
    def _bounded_medplum_verification(
        report: Mapping[str, Any],
    ) -> tuple[str, list[dict[str, str]]]:
        if not isinstance(report, Mapping) or set(report) - {"state", "stages"}:
            raise ValueError("Unsupported Medplum verification report.")
        state = str(report.get("state", ""))
        if state not in MEDPLUM_VERIFICATION_STATES:
            raise ValueError("Unsupported Medplum verification state.")
        submitted = report.get("stages")
        if not isinstance(submitted, list) or len(submitted) != 3:
            raise ValueError("Medplum verification requires three bounded stages.")
        stages: list[dict[str, str]] = []
        for expected, item in zip(MEDPLUM_VERIFICATION_STAGES, submitted):
            if not isinstance(item, Mapping) or set(item) != {
                "stage",
                "state",
                "category",
            }:
                raise ValueError("Unsupported Medplum verification stage.")
            stage = str(item.get("stage", ""))
            stage_state = str(item.get("state", ""))
            category = str(item.get("category", ""))
            if (
                stage != expected
                or stage_state not in MEDPLUM_STAGE_STATES
                or category not in MEDPLUM_STAGE_CATEGORIES
            ):
                raise ValueError("Invalid Medplum verification stage.")
            stages.append(
                {"stage": stage, "state": stage_state, "category": category}
            )
        if state == "healthy" and [
            (item["state"], item["category"]) for item in stages
        ] != [
            ("passed", "reachable"),
            ("passed", "authorized"),
            ("passed", "readable"),
        ]:
            raise ValueError(
                "Healthy Medplum verification requires all bounded stages to pass."
            )
        return state, stages

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
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """SELECT id, public_payload_json, configuration_revision
                FROM integration_settings_profiles WHERE profile_type = ?""",
                (profile.profile_type,),
            ).fetchone()
            if row is None:
                raise KeyError(profile.profile_type)
            profile_id = int(row["id"])
            previous_fields = json.loads(row["public_payload_json"])
            changed_fields = [
                field
                for field, value in profile.fields.items()
                if previous_fields.get(field) != value
            ]
            secret_rows = connection.execute(
                """SELECT field_name, secret_value
                FROM integration_settings_secrets WHERE profile_id = ?""",
                (profile_id,),
            ).fetchall()
            previous_secrets = {
                item["field_name"]: item["secret_value"] for item in secret_rows
            }
            for field, mutation in secret_mutations.items():
                if mutation.action is SecretAction.PRESERVE:
                    continue
                if mutation.action is SecretAction.REMOVE:
                    if field in previous_secrets:
                        changed_fields.append(field)
                    continue
                if previous_secrets.get(field) != mutation.value:
                    changed_fields.append(field)
            connection.execute(
                """
                UPDATE integration_settings_profiles
                SET profile_name = ?, schema_version = ?, public_payload_json = ?,
                    configuration_revision = configuration_revision + ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    profile.profile_name,
                    profile.schema_version,
                    json.dumps(profile.fields, sort_keys=True, separators=(",", ":")),
                    (
                        1
                        if profile.profile_type == MEDPLUM_PROFILE_TYPE
                        and bool(changed_fields)
                        else 0
                    ),
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
        return self.get_private(profile.profile_type)

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
