"""SQLite repository for the persistent OIE settings profile."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from sqlite3 import Connection, Row
from threading import RLock
from typing import Any

from backend.domain.oie import validate_settings_payload as validate_oie_settings_payload
from backend.mappers.oie import project_settings_profile as serialize_oie_settings_profile

ProfileValidator = Callable[[dict[str, Any]], dict[str, Any]]
ProfileSerializer = Callable[[Row, list[Row]], dict[str, Any]]
ConnectionFactory = Callable[[], AbstractContextManager[Connection]]


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
