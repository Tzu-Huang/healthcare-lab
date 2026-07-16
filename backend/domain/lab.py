"""Shared lab service types and operation constraints."""

from __future__ import annotations

import json
from typing import Any

from backend.domain.errors import SimulatorValidationError

LAB_SERVER_TYPES = (
    "HL7 Engine",
    "FHIR Server",
    "EMR",
    "GDT Bridge",
    "DICOM Archive",
    "Test Tool",
    "Generic HTTP Service",
)
LAB_SERVER_PROTOCOLS = ("HTTP", "TCP", "MLLP", "FHIR", "GDT", "DICOM", "None")
LAB_HEALTH_STATUSES = ("Healthy", "Degraded", "Down", "Unknown")
LAB_OPERATION_ACTIONS = ("status", "start", "stop", "restart", "smoke", "logs")


def validate_server_payload(payload: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
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
            raise SimulatorValidationError(f"Server type must be one of: {', '.join(LAB_SERVER_TYPES)}.")
        validated["server_type"] = server_type
    for source_key, target_key in (
        ("description", "description"), ("host", "host"), ("baseUrl", "base_url"),
        ("base_url", "base_url"), ("version", "version"),
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
                raise SimulatorValidationError("Port must be an integer between 1 and 65535.") from exc
            if not 1 <= port <= 65535:
                raise SimulatorValidationError("Port must be an integer between 1 and 65535.")
            validated["port"] = port
    if "protocol" in payload or not partial:
        protocol = str(payload.get("protocol", "None")).strip() or "None"
        if protocol not in LAB_SERVER_PROTOCOLS:
            raise SimulatorValidationError(f"Protocol must be one of: {', '.join(LAB_SERVER_PROTOCOLS)}.")
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
                raise SimulatorValidationError(f"Unsupported lab operation action: {unsupported[0]}.")
            validated["supported_actions_json"] = json.dumps(actions)
        if "timeoutSeconds" in operation_config:
            try:
                timeout_seconds = int(operation_config.get("timeoutSeconds"))
            except (TypeError, ValueError) as exc:
                raise SimulatorValidationError("Operation timeout must be a positive integer.") from exc
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
