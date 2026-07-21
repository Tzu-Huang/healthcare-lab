"""OIE settings validation independent of persistence and application wiring."""

from __future__ import annotations

import math
import json
import urllib.parse
from typing import Any

from backend.domain.errors import SimulatorValidationError


def _required_object(payload: dict[str, Any], key: str, label: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise SimulatorValidationError(f"OIE {label} must be a JSON object.")
    return value


def _required_boolean(payload: dict[str, Any], key: str, label: str) -> bool:
    if key not in payload or not isinstance(payload[key], bool):
        raise SimulatorValidationError(f"OIE {label} must be true or false.")
    return payload[key]


def validate_settings_payload(payload: dict[str, Any]) -> dict[str, Any]:
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
        raise SimulatorValidationError("OIE Management API baseUrl must be an HTTP or HTTPS URL with a host.") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not hostname:
        raise SimulatorValidationError("OIE Management API baseUrl must be an HTTP or HTTPS URL with a host.")
    username = str(management.get("username") or "").strip()
    if not username:
        raise SimulatorValidationError("OIE Management API username is required.")
    raw_timeout = management.get("timeoutSeconds")
    try:
        if isinstance(raw_timeout, bool):
            raise ValueError
        timeout = float(raw_timeout)
    except (TypeError, ValueError) as exc:
        raise SimulatorValidationError("OIE Management API timeoutSeconds must be a positive number.") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise SimulatorValidationError("OIE Management API timeoutSeconds must be a positive number.")
    host = str(listener.get("host") or "").strip()
    if not host:
        raise SimulatorValidationError("OIE resultListener host is required.")
    raw_port = listener.get("port")
    try:
        if isinstance(raw_port, bool):
            raise ValueError
        port = int(raw_port)
    except (TypeError, ValueError) as exc:
        raise SimulatorValidationError("OIE resultListener port must be an integer between 1 and 65535.") from exc
    if str(raw_port).strip() != str(port) or not 1 <= port <= 65535:
        raise SimulatorValidationError("OIE resultListener port must be an integer between 1 and 65535.")
    normalized = []
    logical_types: set[str] = set()
    for index, mapping in enumerate(mappings):
        if not isinstance(mapping, dict):
            raise SimulatorValidationError(f"OIE managedChannels[{index}] must be a JSON object.")
        logical_type = str(mapping.get("logicalType") or "").strip().lower()
        channel_name = str(mapping.get("channelName") or "").strip()
        if not logical_type:
            raise SimulatorValidationError(f"OIE managedChannels[{index}].logicalType is required.")
        if not channel_name:
            raise SimulatorValidationError(f"OIE managedChannels[{index}].channelName is required.")
        if logical_type in logical_types:
            raise SimulatorValidationError(f"OIE managedChannels contains duplicate logicalType '{logical_type}'.")
        logical_types.add(logical_type)
        desired = {}
        desired_fields = {
            "sourceHost": str,
            "sourcePort": int,
            "destinationHost": str,
            "destinationPort": int,
            "timeoutSeconds": (int, float),
            "queueEnabled": bool,
            "retryCount": int,
            "retryIntervalMs": int,
        }
        for key, expected in desired_fields.items():
            if key not in mapping:
                continue
            value = mapping[key]
            if isinstance(value, bool) and expected is not bool:
                raise SimulatorValidationError(f"OIE managedChannels[{index}].{key} has an invalid type.")
            if not isinstance(value, expected):
                raise SimulatorValidationError(f"OIE managedChannels[{index}].{key} has an invalid type.")
            desired[key] = value
        if "sourceHost" in desired and not desired["sourceHost"].strip():
            raise SimulatorValidationError(f"OIE managedChannels[{index}].sourceHost is required.")
        if "destinationHost" in desired and not desired["destinationHost"].strip():
            raise SimulatorValidationError(f"OIE managedChannels[{index}].destinationHost is required.")
        for key in ("sourcePort", "destinationPort"):
            if key in desired and not 1 <= desired[key] <= 65535:
                raise SimulatorValidationError(f"OIE managedChannels[{index}].{key} must be between 1 and 65535.")
        if "timeoutSeconds" in desired and (not math.isfinite(float(desired["timeoutSeconds"])) or float(desired["timeoutSeconds"]) <= 0):
            raise SimulatorValidationError(f"OIE managedChannels[{index}].timeoutSeconds must be positive.")
        for key in ("retryCount", "retryIntervalMs"):
            if key in desired and desired[key] < (0 if key == "retryCount" else 1):
                raise SimulatorValidationError(f"OIE managedChannels[{index}].{key} is invalid.")
        normalized.append({
            "logical_type": logical_type, "oie_channel_id": str(mapping.get("channelId") or "").strip(),
            "channel_name": channel_name, "template_version": str(mapping.get("templateVersion") or "").strip(),
            "last_known_revision": str(mapping.get("lastKnownRevision") or "").strip(),
            "desired_config_json": json.dumps(desired, sort_keys=True, separators=(",", ":")),
        })
    password_provided = "password" in management
    password = ""
    if password_provided:
        raw_password = management.get("password")
        if not isinstance(raw_password, str) or not raw_password.strip():
            raise SimulatorValidationError("OIE Management API password must be a non-empty string when provided.")
        password = raw_password
    return {
        "management_api_base_url": base_url, "management_api_username": username,
        "management_api_tls_verify": int(_required_boolean(management, "tlsVerify", "Management API tlsVerify")),
        "management_api_timeout_seconds": timeout, "result_listener_host": host,
        "result_listener_port": port,
        "result_listener_mllp_framing": int(_required_boolean(listener, "mllpFraming", "resultListener mllpFraming")),
        "result_listener_auto_start": int(_required_boolean(listener, "autoStart", "resultListener autoStart")),
        "managed_channels": normalized, "password_provided": password_provided,
        "management_api_password": password,
    }
