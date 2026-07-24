"""Transactional persistence for AP/external-device profiles."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from sqlite3 import Connection, IntegrityError
from threading import RLock
from typing import Any
from uuid import uuid4

from backend.domain.ap_device_profile import (
    APDeviceObservation,
    APDeviceProfile,
    validate_ap_device_observation,
)

ConnectionFactory = Callable[[], AbstractContextManager[Connection]]
AUDIT_OPERATIONS = frozenset({"bootstrap", "create", "update", "delete", "select-default"})
OBSERVATION_FIELDS = frozenset(
    {"profileKey", "protocol", "direction", "outcomeCode", "correlationKey", "observedAt"}
)
OBSERVATION_PROTOCOLS = frozenset({"hl7", "gdt", "dicom"})
OBSERVATION_DIRECTIONS = frozenset({"inbound", "outbound"})
SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_.:-]{0,128}$")


class DuplicateAPProfileNameError(ValueError):
    """A profile name conflicts after canonical normalization."""

    field = "profileName"
    code = "duplicate-profile-name"


class APDeviceProfileRepository:
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

    @staticmethod
    def normalize_name(value: str) -> str:
        return " ".join(str(value).strip().casefold().split())

    @staticmethod
    def normalize_environment(value: str) -> str:
        normalized = str(value).strip().casefold()
        if not normalized:
            raise ValueError("environment must not be empty")
        return normalized

    @staticmethod
    def _mapping(profile: Mapping[str, Any] | APDeviceProfile) -> dict[str, Any]:
        if isinstance(profile, Mapping):
            return dict(profile)
        return {
            "id": profile.profile_id, "name": profile.name,
            "environment": profile.environment, "enabled": profile.enabled,
            "isDefault": profile.is_default, "metadata": dict(profile.metadata),
            "hl7": {
                "enabled": profile.hl7.enabled, "host": profile.hl7.host,
                "port": profile.hl7.port,
                "sendingApplication": profile.hl7.sending_application,
                "sendingFacility": profile.hl7.sending_facility,
                "receivingApplication": profile.hl7.receiving_application,
                "receivingFacility": profile.hl7.receiving_facility,
            },
            "gdt": {
                "enabled": profile.gdt.enabled, "senderId": profile.gdt.sender_id,
                "receiverId": profile.gdt.receiver_id,
                "bridgeProfile": profile.gdt.bridge_profile,
            },
            "dicom": {
                "enabled": profile.dicom.enabled, "aeTitle": profile.dicom.ae_title,
                "host": profile.dicom.host, "port": profile.dicom.port,
                "mwlCallingAETitle": profile.dicom.mwl_calling_ae_title,
                "scheduledStationAETitle": profile.dicom.scheduled_station_ae_title,
                "resultDeliveryRole": profile.dicom.result_delivery_role,
            },
        }

    @staticmethod
    def _parts(profile: Mapping[str, Any] | APDeviceProfile) -> tuple[str, str, str, bool, bool, int, dict[str, Any], str]:
        profile = APDeviceProfileRepository._mapping(profile)
        name = str(profile.get("name", profile.get("profileName", ""))).strip()
        if not name:
            raise ValueError("profileName must not be empty")
        environment = APDeviceProfileRepository.normalize_environment(
            str(profile.get("environment", ""))
        )
        enabled = bool(profile.get("enabled", False))
        is_default = bool(profile.get("isDefault", False))
        if is_default and not enabled:
            raise ValueError("A disabled profile cannot be selected as default.")
        key = str(profile.get("id", profile.get("profileKey", ""))).strip() or str(uuid4())
        schema_version = int(profile.get("schemaVersion", 1))
        bootstrap_source = str(profile.get("bootstrapSource", ""))
        payload = {
            key_: value
            for key_, value in profile.items()
            if key_
            not in {
                "id", "name", "profileKey", "profileName", "environment", "enabled", "isDefault",
                "schemaVersion", "bootstrapSource", "createdAt", "updatedAt",
            }
        }
        return key, name, environment, enabled, is_default, schema_version, payload, bootstrap_source

    @staticmethod
    def _project(row: Any) -> dict[str, Any]:
        return {
            "id": row["profile_key"],
            "name": row["profile_name"],
            "environment": row["environment"],
            "enabled": bool(row["enabled"]),
            "isDefault": bool(row["is_default"]),
            "schemaVersion": int(row["schema_version"]),
            **json.loads(row["payload_json"]),
            "bootstrapSource": row["bootstrap_source"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    def list(self, *, environment: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM ap_device_profiles"
        parameters: tuple[Any, ...] = ()
        if environment is not None:
            query += " WHERE environment = ?"
            parameters = (self.normalize_environment(environment),)
        query += " ORDER BY environment, normalized_name, id"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._project(row) for row in rows]

    def get(self, profile_key: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ap_device_profiles WHERE profile_key = ?", (profile_key,)
            ).fetchone()
        if row is None:
            raise KeyError(profile_key)
        return self._project(row)

    def get_effective(self, environment: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM ap_device_profiles
                WHERE environment = ? AND enabled = 1 AND is_default = 1""",
                (self.normalize_environment(environment),),
            ).fetchone()
        return None if row is None else self._project(row)

    def create(
        self, profile: Mapping[str, Any] | APDeviceProfile, *, actor: str = "local-operator",
        operation: str = "create",
    ) -> dict[str, Any]:
        parts = self._parts(profile)
        key, name, environment, enabled, is_default, version, payload, source = parts
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            try:
                cursor = connection.execute(
                    """INSERT INTO ap_device_profiles (
                    profile_key, profile_name, normalized_name, environment, enabled,
                    is_default, schema_version, payload_json, bootstrap_source,
                    created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (key, name, self.normalize_name(name), environment, int(enabled),
                     int(is_default), version, json.dumps(payload, sort_keys=True,
                     separators=(",", ":")), source, timestamp, timestamp),
                )
            except IntegrityError as error:
                self._translate_integrity(error)
            self._audit(connection, int(cursor.lastrowid), actor, operation,
                        sorted(self._mapping(profile).keys()), timestamp)
        return self.get(key)

    def update(
        self, profile_key: str, profile: Mapping[str, Any], *,
        actor: str = "local-operator",
    ) -> dict[str, Any]:
        current = self.get(profile_key)
        merged = {**current, **profile, "id": profile_key}
        if profile.get("enabled") is False:
            merged["isDefault"] = False
        key, name, environment, enabled, is_default, version, payload, source = self._parts(merged)
        timestamp = self._timestamp()
        changed = sorted(
            field for field, value in merged.items() if current.get(field) != value
        )
        with self._lock, self._connect() as connection:
            try:
                cursor = connection.execute(
                    """UPDATE ap_device_profiles SET profile_name = ?, normalized_name = ?,
                    environment = ?, enabled = ?, is_default = ?, schema_version = ?,
                    payload_json = ?, bootstrap_source = ?, updated_at = ?
                    WHERE profile_key = ?""",
                    (name, self.normalize_name(name), environment, int(enabled),
                     int(is_default), version, json.dumps(payload, sort_keys=True,
                     separators=(",", ":")), source, timestamp, key),
                )
            except IntegrityError as error:
                self._translate_integrity(error)
            if cursor.rowcount != 1:
                raise KeyError(profile_key)
            row = connection.execute(
                "SELECT id FROM ap_device_profiles WHERE profile_key = ?", (key,)
            ).fetchone()
            self._audit(connection, int(row["id"]), actor, "update", changed, timestamp)
        return self.get(key)

    def select_default(
        self, profile_key: str, *, actor: str = "local-operator"
    ) -> dict[str, Any]:
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT id, environment, enabled FROM ap_device_profiles WHERE profile_key = ?",
                (profile_key,),
            ).fetchone()
            if row is None:
                raise KeyError(profile_key)
            if not row["enabled"]:
                raise ValueError("A disabled profile cannot be selected as default.")
            connection.execute(
                "UPDATE ap_device_profiles SET is_default = 0, updated_at = ? WHERE environment = ?",
                (timestamp, row["environment"]),
            )
            connection.execute(
                "UPDATE ap_device_profiles SET is_default = 1, updated_at = ? WHERE id = ?",
                (timestamp, row["id"]),
            )
            self._audit(connection, int(row["id"]), actor, "select-default",
                        ["isDefault"], timestamp)
        return self.get(profile_key)

    def delete(self, profile_key: str) -> None:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM ap_device_profiles WHERE profile_key = ?", (profile_key,)
            )
            if cursor.rowcount != 1:
                raise KeyError(profile_key)

    def list_audits(self, profile_key: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT a.actor, a.operation, a.changed_fields_json, a.outcome, a.created_at
                FROM ap_device_profile_audits a JOIN ap_device_profiles p ON p.id = a.profile_id
                WHERE p.profile_key = ? ORDER BY a.id""", (profile_key,)
            ).fetchall()
        return [{"actor": row["actor"], "operation": row["operation"],
                 "changedFields": json.loads(row["changed_fields_json"]),
                 "outcome": row["outcome"], "createdAt": row["created_at"]} for row in rows]

    def record_observation(
        self, observation: Mapping[str, Any] | APDeviceObservation
    ) -> dict[str, Any]:
        if isinstance(observation, APDeviceObservation):
            observation = {
                "profileId": observation.profile_id, "protocol": observation.protocol,
                "direction": observation.direction,
                "outcomeCode": observation.outcome_code,
                "correlation": dict(observation.correlation),
                "observedAt": observation.observed_at.isoformat(),
            }
        else:
            observation = dict(observation)
            if "profileId" in observation or "correlation" in observation:
                return self.record_observation(validate_ap_device_observation(observation))
        if "profileId" in observation:
            observation["profileKey"] = observation.pop("profileId")
        if "correlation" in observation:
            correlation = observation.pop("correlation")
            observation["correlationKey"] = json.dumps(
                correlation, sort_keys=True, separators=(",", ":")
            )
        unknown = set(observation) - OBSERVATION_FIELDS
        if unknown:
            raise ValueError(f"Observation contains unsupported fields: {sorted(unknown)!r}.")
        required = {"profileKey", "protocol", "direction", "outcomeCode"}
        if required - set(observation):
            raise ValueError("Observation is missing required fields.")
        protocol, direction = str(observation["protocol"]), str(observation["direction"])
        outcome = str(observation["outcomeCode"])
        correlation = str(observation.get("correlationKey", ""))
        if protocol not in OBSERVATION_PROTOCOLS or direction not in OBSERVATION_DIRECTIONS:
            raise ValueError("Unsupported observation protocol or direction.")
        if not SAFE_TOKEN.fullmatch(outcome) or len(correlation) > 256:
            raise ValueError("Observation metadata must be a bounded non-clinical token.")
        observed_at = str(observation.get("observedAt") or self._timestamp())
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM ap_device_profiles WHERE profile_key = ?",
                (observation["profileKey"],),
            ).fetchone()
            if row is None:
                raise KeyError(observation["profileKey"])
            connection.execute(
                """INSERT INTO ap_device_observations
                (profile_id, protocol, direction, outcome_code, correlation_key, observed_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (row["id"], protocol, direction, outcome, correlation, observed_at),
            )
        return {"profileKey": observation["profileKey"], "protocol": protocol,
                "direction": direction, "outcomeCode": outcome,
                "correlationKey": correlation, "observedAt": observed_at}

    def list_observations(self, profile_key: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT o.protocol, o.direction, o.outcome_code, o.correlation_key, o.observed_at
                FROM ap_device_observations o JOIN ap_device_profiles p ON p.id = o.profile_id
                WHERE p.profile_key = ? ORDER BY o.observed_at DESC, o.id DESC""",
                (profile_key,),
            ).fetchall()
        return [{"profileKey": profile_key, "protocol": row["protocol"],
                 "direction": row["direction"], "outcomeCode": row["outcome_code"],
                 "correlationKey": row["correlation_key"],
                 "observedAt": row["observed_at"]} for row in rows]

    @staticmethod
    def _audit(connection: Connection, profile_id: int, actor: str, operation: str,
               changed_fields: list[str], timestamp: str) -> None:
        if operation not in AUDIT_OPERATIONS:
            raise ValueError("Unsupported AP profile audit operation.")
        connection.execute(
            """INSERT INTO ap_device_profile_audits
            (profile_id, actor, operation, changed_fields_json, outcome, created_at)
            VALUES (?, ?, ?, ?, 'success', ?)""",
            (profile_id, str(actor or "local-operator")[:64], operation,
             json.dumps(changed_fields, separators=(",", ":")), timestamp),
        )

    @staticmethod
    def _translate_integrity(error: IntegrityError) -> None:
        message = str(error)
        if "normalized_name" in message:
            raise DuplicateAPProfileNameError(
                "A profile with this normalized name already exists."
            ) from error
        if "environment" in message or "is_default" in message:
            raise ValueError("An environment can have at most one default profile.") from error
        raise error
