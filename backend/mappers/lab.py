"""Lab control-plane row and boundary presentation."""

from __future__ import annotations

import json
from typing import Any

from backend.mappers.types import RowMapping


def project_server(row: RowMapping) -> dict[str, Any]:
    return {
        "id": row["id"], "name": row["name"], "serverType": row["server_type"],
        "description": row["description"], "host": row["host"], "port": row["port"],
        "baseUrl": row["base_url"], "protocol": row["protocol"],
        "enabled": bool(row["enabled"]), "version": row["version"],
        "checkConfig": json.loads(row["check_config_json"] or "{}"),
        "operation": {
            "controlType": row["control_type"], "backingService": row["backing_service"],
            "supportedActions": json.loads(row["supported_actions_json"] or "[]"),
            "timeoutSeconds": row["operation_timeout_seconds"], "smokeProfile": row["smoke_profile"],
        },
        "overallStatus": row["overall_status"],
        "checks": {"process": row["process_status"], "application": row["application_status"],
                   "protocol": row["protocol_status"]},
        "lastCheckAt": row["last_check_at"], "recentError": row["recent_error"],
        "createdAt": row["created_at"], "updatedAt": row["updated_at"],
    }


def project_operation(row: RowMapping) -> dict[str, Any]:
    return {
        "id": row["id"], "serverId": row["server_id"], "serviceName": row["service_name"],
        "action": row["action"], "operator": row["operator"], "result": row["result"],
        "durationMs": row["duration_ms"], "progress": json.loads(row["progress_json"] or "[]"),
        "error": row["error_text"], "startedAt": row["started_at"], "completedAt": row["completed_at"],
    }
