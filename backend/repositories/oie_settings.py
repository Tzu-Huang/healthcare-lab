"""SQLite repository for the persistent OIE settings profile."""

from __future__ import annotations

import math
import urllib.parse
from collections.abc import Callable
from contextlib import AbstractContextManager
from sqlite3 import Connection, Row
from threading import RLock
from typing import Any

from backend.domain.errors import SimulatorValidationError

ProfileValidator = Callable[[dict[str, Any]], dict[str, Any]]
ProfileSerializer = Callable[[Row, list[Row]], dict[str, Any]]
ConnectionFactory = Callable[[], AbstractContextManager[Connection]]


def _required_object(payload: dict[str, Any], key: str, label: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise SimulatorValidationError(f"OIE {label} must be a JSON object.")
    return value


def _required_boolean(payload: dict[str, Any], key: str, label: str) -> bool:
    if key not in payload or not isinstance(payload[key], bool):
        raise SimulatorValidationError(f"OIE {label} must be true or false.")
    return payload[key]


def validate_oie_settings_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SimulatorValidationError("OIE settings payload must be a JSON object.")
    management = _required_object(payload, "managementApi", "managementApi")
    listener = _required_object(payload, "resultListener", "resultListener")
    mappings = payload.get("managedChannels")
    if not isinstance(mappings, list):
        raise SimulatorValidationError("OIE managedChannels must be a JSON array.")
    base_url = str(management.get("baseUrl") or "").strip()
    try:
        parsed = urllib.parse.urlparse(base_url)
        hostname = parsed.hostname
        parsed.port
    except ValueError as exc:
        raise SimulatorValidationError(
            "OIE Management API baseUrl must be an HTTP or HTTPS URL with a host."
        ) from exc
    if parsed.scheme.lower() not in {"http", "https"} or not hostname:
        raise SimulatorValidationError(
            "OIE Management API baseUrl must be an HTTP or HTTPS URL with a host."
        )
    username = str(management.get("username") or "").strip()
    if not username:
        raise SimulatorValidationError("OIE Management API username is required.")
    raw_timeout = management.get("timeoutSeconds")
    try:
        if isinstance(raw_timeout, bool):
            raise ValueError
        timeout = float(raw_timeout)
    except (TypeError, ValueError) as exc:
        raise SimulatorValidationError(
            "OIE Management API timeoutSeconds must be a positive number."
        ) from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise SimulatorValidationError(
            "OIE Management API timeoutSeconds must be a positive number."
        )
    host = str(listener.get("host") or "").strip()
    if not host:
        raise SimulatorValidationError("OIE resultListener host is required.")
    raw_port = listener.get("port")
    try:
        if isinstance(raw_port, bool):
            raise ValueError
        port = int(raw_port)
    except (TypeError, ValueError) as exc:
        raise SimulatorValidationError(
            "OIE resultListener port must be an integer between 1 and 65535."
        ) from exc
    if str(raw_port).strip() != str(port) or not 1 <= port <= 65535:
        raise SimulatorValidationError(
            "OIE resultListener port must be an integer between 1 and 65535."
        )
    normalized = []
    logical_types: set[str] = set()
    for index, mapping in enumerate(mappings):
        if not isinstance(mapping, dict):
            raise SimulatorValidationError(f"OIE managedChannels[{index}] must be a JSON object.")
        logical_type = str(mapping.get("logicalType") or "").strip().lower()
        channel_name = str(mapping.get("channelName") or "").strip()
        if not logical_type:
            raise SimulatorValidationError(
                f"OIE managedChannels[{index}].logicalType is required."
            )
        if not channel_name:
            raise SimulatorValidationError(
                f"OIE managedChannels[{index}].channelName is required."
            )
        if logical_type in logical_types:
            raise SimulatorValidationError(
                f"OIE managedChannels contains duplicate logicalType '{logical_type}'."
            )
        logical_types.add(logical_type)
        normalized.append({
            "logical_type": logical_type,
            "oie_channel_id": str(mapping.get("channelId") or "").strip(),
            "channel_name": channel_name,
            "template_version": str(mapping.get("templateVersion") or "").strip(),
            "last_known_revision": str(mapping.get("lastKnownRevision") or "").strip(),
        })
    password_provided = "password" in management
    password = ""
    if password_provided:
        raw_password = management.get("password")
        if not isinstance(raw_password, str) or not raw_password.strip():
            raise SimulatorValidationError(
                "OIE Management API password must be a non-empty string when provided."
            )
        password = raw_password
    return {
        "management_api_base_url": base_url,
        "management_api_username": username,
        "management_api_tls_verify": int(_required_boolean(
            management, "tlsVerify", "Management API tlsVerify")),
        "management_api_timeout_seconds": timeout,
        "result_listener_host": host,
        "result_listener_port": port,
        "result_listener_mllp_framing": int(_required_boolean(
            listener, "mllpFraming", "resultListener mllpFraming")),
        "result_listener_auto_start": int(_required_boolean(
            listener, "autoStart", "resultListener autoStart")),
        "managed_channels": normalized,
        "password_provided": password_provided,
        "management_api_password": password,
    }


def serialize_oie_settings_profile(profile: Row, mappings: list[Row]) -> dict[str, Any]:
    timeout = float(profile["management_api_timeout_seconds"])
    return {
        "profileName": profile["profile_name"],
        "managementApi": {
            "baseUrl": profile["management_api_base_url"],
            "username": profile["management_api_username"],
            "passwordConfigured": bool(profile["management_api_password"]),
            "tlsVerify": bool(profile["management_api_tls_verify"]),
            "timeoutSeconds": int(timeout) if timeout.is_integer() else timeout,
        },
        "resultListener": {
            "host": profile["result_listener_host"], "port": profile["result_listener_port"],
            "mllpFraming": bool(profile["result_listener_mllp_framing"]),
            "autoStart": bool(profile["result_listener_auto_start"]),
        },
        "managedChannels": [{
            "logicalType": item["logical_type"], "channelId": item["oie_channel_id"],
            "channelName": item["channel_name"], "templateVersion": item["template_version"],
            "lastKnownRevision": item["last_known_revision"],
        } for item in mappings],
        "createdAt": profile["created_at"], "updatedAt": profile["updated_at"],
    }


class OieSettingsRepository:
    def __init__(
        self,
        connection_factory: ConnectionFactory,
        lock: RLock,
        *,
        profile_name: str,
        validator: ProfileValidator,
        serializer: ProfileSerializer,
        timestamp_factory: Callable[[], str],
    ) -> None:
        self._connect = connection_factory
        self._lock = lock
        self._profile_name = profile_name
        self._validate = validator
        self._serialize = serializer
        self._timestamp = timestamp_factory

    def get(self) -> dict[str, Any]:
        with self._connect() as connection:
            profile = connection.execute(
                "SELECT * FROM oie_settings_profiles WHERE profile_name = ?",
                (self._profile_name,),
            ).fetchone()
            if not profile:
                raise KeyError(self._profile_name)
            mappings = connection.execute(
                """
                SELECT * FROM oie_managed_channel_mappings
                WHERE profile_id = ?
                ORDER BY logical_type COLLATE NOCASE, id
                """,
                (profile["id"],),
            ).fetchall()
        return self._serialize(profile, mappings)

    def update(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = self._validate(payload)
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            profile = connection.execute(
                "SELECT * FROM oie_settings_profiles WHERE profile_name = ?",
                (self._profile_name,),
            ).fetchone()
            if not profile:
                raise KeyError(self._profile_name)
            password = (
                values["management_api_password"]
                if values["password_provided"]
                else profile["management_api_password"]
            )
            connection.execute(
                """
                UPDATE oie_settings_profiles
                SET management_api_base_url = ?, management_api_username = ?,
                    management_api_password = ?, management_api_tls_verify = ?,
                    management_api_timeout_seconds = ?, result_listener_host = ?,
                    result_listener_port = ?, result_listener_mllp_framing = ?,
                    result_listener_auto_start = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    values["management_api_base_url"],
                    values["management_api_username"],
                    password,
                    values["management_api_tls_verify"],
                    values["management_api_timeout_seconds"],
                    values["result_listener_host"],
                    values["result_listener_port"],
                    values["result_listener_mllp_framing"],
                    values["result_listener_auto_start"],
                    timestamp,
                    profile["id"],
                ),
            )
            connection.execute(
                "DELETE FROM oie_managed_channel_mappings WHERE profile_id = ?",
                (profile["id"],),
            )
            for mapping in values["managed_channels"]:
                connection.execute(
                    """
                    INSERT INTO oie_managed_channel_mappings (
                        profile_id, logical_type, oie_channel_id, channel_name,
                        template_version, last_known_revision, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        profile["id"],
                        mapping["logical_type"],
                        mapping["oie_channel_id"],
                        mapping["channel_name"],
                        mapping["template_version"],
                        mapping["last_known_revision"],
                        timestamp,
                        timestamp,
                    ),
                )
        return self.get()
