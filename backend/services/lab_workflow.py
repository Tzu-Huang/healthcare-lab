"""Lab health, dashboard, smoke, and lifecycle operation coordination."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from backend.clients.health import (
    DOCKER_COMPOSE_APPLICATION_URLS,
    run_http_smoke,
    run_lab_application_check,
    run_tcp_smoke,
    smoke_step,
)
from backend.clients.medplum import MedplumAuthManager
from backend.config import dcm4chee_profile_from_config
from backend.dashboard_services import (
    LAB_DASHBOARD_SERVICE_GROUPS,
    collect_dashboard_resource_snapshot,
    dashboard_action_for_group,
    dashboard_child_for_group,
    dashboard_health_rank,
    dashboard_operation_services,
    dashboard_servers_for_group,
    dashboard_summary,
    derive_dashboard_group_status,
)
from backend.domain.dicom import validate_dcm4chee_profile
from backend.domain.errors import (
    LabOperationError,
    SimulatorValidationError,
    UpstreamFhirError,
    ValidationError,
)
from backend.domain.gdt import ensure_gdt_bridge_dirs
from backend.domain.lab import (
    LAB_HEALTH_STATUSES,
    LAB_OPERATION_ACTIONS,
    LAB_SERVER_PROTOCOLS,
    LAB_SERVER_TYPES,
)
from backend.lab_operations import (
    DockerComposeLabOperationAdapter,
    DockerSocketLabOperationAdapter,
)
from backend.repositories.gdt_bridge_health import validate_gdt_bridge_dirs
from backend.services.fhir_workflow import (
    fetch_fhir_diagnostic_report_bundle,
    fetch_fhir_service_requests,
)


class ApplicationPort(Protocol):
    config: dict[str, Any]
    extensions: dict[str, Any]


class LabRepositoryPort(Protocol):
    """Lab control-plane persistence consumed by the lab server workflow."""

    def get_lab_server(self, server_id: int) -> dict[str, Any]: ...

    def list_lab_servers(self) -> list[dict[str, Any]]: ...

    def create_lab_server(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def update_lab_server(
        self, server_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    def update_lab_server_health(
        self,
        server_id: int,
        *,
        overall_status: str,
        process_status: str,
        application_status: str,
        protocol_status: str,
        recent_error: str = "",
        version: str = "",
    ) -> dict[str, Any]: ...

    def record_lab_operation(
        self,
        server_id: int | None,
        *,
        service_name: str,
        action: str,
        operator: str,
        result: str,
        duration_ms: int = 0,
        progress: list[dict[str, Any]] | None = None,
        error_text: str = "",
        started_at: str = "",
        completed_at: str = "",
    ) -> dict[str, Any]: ...

    def list_lab_operations(
        self, server_id: int | None = None, *, limit: int = 20
    ) -> list[dict[str, Any]]: ...


class LabOperationStorePort(LabRepositoryPort, Protocol):
    """Cross-context inventory needed only by smoke/operation coordination."""

    def list_gdt_orders(self) -> list[dict[str, Any]]: ...

def current_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


class LabRegistryService:
    """Own Lab Server metadata and registry use cases."""

    def __init__(
        self,
        app: ApplicationPort,
        repository: LabRepositoryPort,
        *,
        availability_decorator: Callable[[ApplicationPort, dict[str, Any]], dict[str, Any]],
    ) -> None:
        self.app = app
        self.repository = repository
        self._availability_decorator = availability_decorator

    def metadata(self) -> dict[str, list[str]]:
        return {
            "serverTypes": list(LAB_SERVER_TYPES),
            "protocols": list(LAB_SERVER_PROTOCOLS),
            "healthStatuses": list(LAB_HEALTH_STATUSES),
        }

    def _decorate(self, item: dict[str, Any]) -> dict[str, Any]:
        return self._availability_decorator(self.app, item)

    def list_servers(self) -> list[dict[str, Any]]:
        return [self._decorate(item) for item in self.repository.list_lab_servers()]

    def create_server(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._decorate(self.repository.create_lab_server(payload))

    def get_server(self, server_id: int) -> dict[str, Any]:
        return self._decorate(self.repository.get_lab_server(server_id))

    def update_server(self, server_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._decorate(self.repository.update_lab_server(server_id, payload))


class LabHealthService:
    """Own single-server and bulk Lab health use cases."""

    def __init__(self, app: ApplicationPort, repository: LabRepositoryPort, *, health_checker: Callable[[LabRepositoryPort, int], dict[str, Any]], availability_decorator: Callable[[ApplicationPort, dict[str, Any]], dict[str, Any]]) -> None:
        self.app = app
        self.repository = repository
        self._health_checker = health_checker
        self._availability_decorator = availability_decorator

    def _decorate(self, item: dict[str, Any]) -> dict[str, Any]:
        return self._availability_decorator(self.app, item)

    def check_server(self, server_id: int) -> dict[str, Any]:
        return self._decorate(self._health_checker(self.repository, server_id))

    def check_all_servers(self) -> list[dict[str, Any]]:
        items = []
        for server in self.repository.list_lab_servers():
            checked = (
                server
                if not server["enabled"]
                else self._health_checker(self.repository, int(server["id"]))
            )
            items.append(self._decorate(checked))
        return items


class LabOperationService:
    """Own Lab operation history and execution use cases."""

    def __init__(self, app: ApplicationPort, repository: LabRepositoryPort, operation_repository: LabOperationStorePort, *, operation_runner: Callable[..., dict[str, Any]]) -> None:
        self.app = app
        self.repository = repository
        self.operation_repository = operation_repository
        self._operation_runner = operation_runner

    def operation_history(self, server_id: int, *, limit: int = 20) -> list[dict[str, Any]]:
        self.repository.get_lab_server(server_id)
        return self.repository.list_lab_operations(server_id, limit=limit)

    def execute_operation(
        self, server_id: int, action: str, *, lines: int = 200
    ) -> dict[str, Any]:
        return self._operation_runner(
            app=self.app,
            store=self.operation_repository,
            server_id=server_id,
            action=action,
            lines=lines,
        )


class LabSmokeService:
    """Own bulk Lab smoke coordination and partial-failure collection."""

    def __init__(self, app: ApplicationPort, repository: LabRepositoryPort, operation_repository: LabOperationStorePort, *, operation_runner: Callable[..., dict[str, Any]], operator_resolver: Callable[[], str]) -> None:
        self.app = app
        self.repository = repository
        self.operation_repository = operation_repository
        self._operation_runner = operation_runner
        self._operator_resolver = operator_resolver

    def smoke_all_servers(self) -> list[dict[str, Any]]:
        results = []
        for item in self.repository.list_lab_servers():
            if not item["enabled"]:
                results.append(
                    {
                        "server": item,
                        "operation": self.repository.record_lab_operation(
                            item["id"],
                            service_name=item["name"],
                            action="smoke",
                            operator=self._operator_resolver(),
                            result="skipped",
                            progress=[{"step": "smoke", "status": "skipped"}],
                            error_text="Server is disabled.",
                        ),
                        "output": "",
                        "command": [],
                    }
                )
                continue
            try:
                results.append(
                    self._operation_runner(
                        app=self.app,
                        store=self.operation_repository,
                        server_id=int(item["id"]),
                        action="smoke",
                    )
                )
            except LabOperationError as exc:
                try:
                    results.append(json.loads(str(exc)))
                except json.JSONDecodeError:
                    results.append({"server": item, "operation": None, "error": str(exc)})
            except SimulatorValidationError as exc:
                results.append({"server": item, "operation": None, "error": str(exc)})
        return results


class LabServerWorkflowService:
    """Compatibility composition seam for the focused Lab use-case services."""

    def __init__(self, app: ApplicationPort, repository: LabRepositoryPort, *, operation_repository: LabOperationStorePort | None = None, health_checker: Callable[[LabRepositoryPort, int], dict[str, Any]], availability_decorator: Callable[[ApplicationPort, dict[str, Any]], dict[str, Any]], operation_runner: Callable[..., dict[str, Any]], operator_resolver: Callable[[], str]) -> None:
        operation_store = operation_repository or repository
        self.registry = LabRegistryService(app, repository, availability_decorator=availability_decorator)
        self.health = LabHealthService(app, repository, health_checker=health_checker, availability_decorator=availability_decorator)
        self.operations = LabOperationService(app, repository, operation_store, operation_runner=operation_runner)
        self.smoke = LabSmokeService(app, repository, operation_store, operation_runner=operation_runner, operator_resolver=operator_resolver)
        self.app = app

    def metadata(self) -> dict[str, list[str]]: return self.registry.metadata()
    def list_servers(self) -> list[dict[str, Any]]: return self.registry.list_servers()
    def create_server(self, payload: dict[str, Any]) -> dict[str, Any]: return self.registry.create_server(payload)
    def get_server(self, server_id: int) -> dict[str, Any]: return self.registry.get_server(server_id)
    def update_server(self, server_id: int, payload: dict[str, Any]) -> dict[str, Any]: return self.registry.update_server(server_id, payload)
    def check_server(self, server_id: int) -> dict[str, Any]: return self.health.check_server(server_id)
    def check_all_servers(self) -> list[dict[str, Any]]: return self.health.check_all_servers()
    def operation_history(self, server_id: int, *, limit: int = 20) -> list[dict[str, Any]]: return self.operations.operation_history(server_id, limit=limit)
    def execute_operation(self, server_id: int, action: str, *, lines: int = 200) -> dict[str, Any]: return self.operations.execute_operation(server_id, action, lines=lines)
    def smoke_all_servers(self) -> list[dict[str, Any]]: return self.smoke.smoke_all_servers()


class DashboardWorkflowService:
    """Coordinate dashboard snapshots, health checks, and grouped operations."""

    def __init__(
        self,
        app: ApplicationPort,
        repository: LabRepositoryPort,
        *,
        health_check: Callable[[LabRepositoryPort, str], list[dict[str, Any]]],
        operation_runner: Callable[..., dict[str, Any]],
    ) -> None:
        self.app = app
        self.repository = repository
        self._health_check = health_check
        self._operation_runner = operation_runner

    def _snapshot_payload(
        self, items: list[dict[str, Any]], resources: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "items": items,
            "summary": dashboard_summary(items, resources),
            "resources": resources,
            "events": dashboard_events(self.repository, items, resources),
        }

    def snapshot(self) -> dict[str, Any]:
        resources = collect_dashboard_resource_snapshot()
        items = dashboard_all_group_items(self.app, self.repository)
        return self._snapshot_payload(items, resources)

    def restart_preview(self, service_id: str) -> dict[str, Any]:
        return dashboard_group_item(self.app, self.repository, service_id)["restartPreview"]

    def check_all(self) -> dict[str, Any]:
        results = []
        for service_id in LAB_DASHBOARD_SERVICE_GROUPS:
            try:
                results.append(
                    {
                        "serviceId": service_id,
                        "servers": self._health_check(self.repository, service_id),
                    }
                )
            except (KeyError, SimulatorValidationError, LabOperationError) as exc:
                results.append({"serviceId": service_id, "error": str(exc)})
        return {"results": results, **self.snapshot()}

    def run_action(
        self, service_id: str, action: str, *, lines: int = 200
    ) -> dict[str, Any]:
        group, servers = dashboard_servers_for_group(self.repository, service_id)
        primary = next(
            (server for server in servers if server["name"] == group["primary"]),
            servers[0],
        )
        if action.strip().lower() == "check":
            checked = self._health_check(self.repository, service_id)
            return {
                "service": dashboard_group_item(self.app, self.repository, service_id),
                "servers": checked,
                "output": json.dumps(checked, indent=2),
            }
        operation_action = dashboard_action_for_group(group, action)
        result = self._operation_runner(
            app=self.app,
            store=self.repository,
            server_id=int(primary["id"]),
            action=operation_action,
            lines=lines,
            backing_services=dashboard_operation_services(group, operation_action),
        )
        return {
            "service": dashboard_group_item(self.app, self.repository, service_id),
            "operation": result["operation"],
            "output": result["output"],
        }

    def run_child_action(
        self,
        service_id: str,
        child_id: str,
        action: str,
        *,
        lines: int = 200,
    ) -> dict[str, Any]:
        group, servers = dashboard_servers_for_group(self.repository, service_id)
        child = dashboard_child_for_group(group, child_id)
        primary = next(
            (server for server in servers if server["name"] == group["primary"]),
            servers[0],
        )
        if action.strip().lower() == "check":
            return {
                "service": dashboard_group_item(self.app, self.repository, service_id),
                "child": dashboard_child_item(self.app, child),
            }
        operation_action = dashboard_action_for_group(group, action)
        result = self._operation_runner(
            app=self.app,
            store=self.repository,
            server_id=int(primary["id"]),
            action=operation_action,
            lines=lines,
            backing_services=[str(child["service"])],
            operation_service_name=str(child["displayName"]),
            refresh_health=False,
        )
        return {
            "service": dashboard_group_item(self.app, self.repository, service_id),
            "child": dashboard_child_item(self.app, child),
            "operation": result["operation"],
            "output": result["output"],
        }


def run_lab_operation(
    *,
    app: ApplicationPort,
    store: LabRepositoryPort,
    server_id: int,
    action: str,
    lines: int = 200,
    backing_services: list[str] | None = None,
    operation_service_name: str = "",
    refresh_health: bool = True,
) -> dict[str, Any]:
    server = store.get_lab_server(server_id)
    normalized_action = action.strip().lower()
    if normalized_action not in LAB_OPERATION_ACTIONS:
        raise SimulatorValidationError(f"Unsupported lab operation action: {normalized_action}.")
    operation = server["operation"]
    supported_actions = operation.get("supportedActions") or []
    if normalized_action not in supported_actions:
        raise SimulatorValidationError(f"{server['name']} does not support {normalized_action}.")
    started = time.monotonic()
    started_at = current_timestamp()
    output = ""
    command: list[str] = []
    result = "success"
    error_text = ""
    try:
        if normalized_action == "smoke":
            smoke_result = run_lab_smoke_check(
                app,
                store,
                server,
                auth_manager=MedplumAuthManager(
                    client_id=app.config["MEDPLUM_CLIENT_ID"],
                    client_secret=app.config["MEDPLUM_CLIENT_SECRET"],
                    scope=app.config["MEDPLUM_SCOPE"],
                    token_url=app.config["MEDPLUM_TOKEN_URL"],
                    refresh_grace_seconds=app.config["MEDPLUM_AUTH_GRACE_SECONDS"],
                ),
            )
            output = json.dumps(smoke_result, indent=2)
            command = ["smoke", smoke_result["profile"] or server["name"]]
            checks = {
                "process": store.get_lab_server(server_id)["checks"]["process"],
                "application": smoke_result["status"],
                "protocol": smoke_result["status"],
            }
            error_text = ""
            if smoke_result["requiredFailures"] or smoke_result["optionalFailures"]:
                first_failure = (smoke_result["requiredFailures"] + smoke_result["optionalFailures"])[0]
                error_text = str(first_failure.get("message", "Smoke check failed."))
            store.update_lab_server_health(
                server_id,
                overall_status=derive_lab_overall_status(checks),
                process_status=checks["process"],
                application_status=checks["application"],
                protocol_status=checks["protocol"],
                recent_error=error_text,
            )
        elif operation.get("controlType") == "docker-compose":
            adapter = DockerComposeLabOperationAdapter(app.config["LAB_DEPLOY_SCRIPT"])
            unavailable_reason = adapter.unavailable_reason()
            if unavailable_reason:
                raise LabOperationError(
                    f"Docker Compose operation '{normalized_action}' is unavailable: {unavailable_reason}"
                )
            targets = backing_services or [operation.get("backingService") or server["name"]]
            outputs = []
            commands = []
            for target in targets:
                adapter_result = adapter.run(
                    normalized_action,
                    target,
                    timeout_seconds=int(operation.get("timeoutSeconds") or 60),
                    lines=lines,
                )
                outputs.append(f"[{target}]\n{adapter_result['output']}".rstrip())
                commands.append(adapter_result["command"])
            output = "\n".join(outputs)
            command = [part for adapter_command in commands for part in adapter_command]
        else:
            adapter_result = run_internal_lab_operation(
                server,
                normalized_action,
                app=app,
                store=store,
                lines=lines,
            )
            output = adapter_result["output"]
            command = adapter_result["command"]
        if refresh_health and normalized_action in {"start", "stop", "restart"}:
            run_lab_server_health_check(store, server_id)
    except (LabOperationError, ValidationError, UpstreamFhirError) as exc:
        result = "failed"
        error_text = str(exc)
    completed_at = current_timestamp()
    duration_ms = int((time.monotonic() - started) * 1000)
    progress = (
        restart_progress_steps(result, error_text)
        if normalized_action == "restart"
        else [{"step": normalized_action, "status": "completed" if result == "success" else "failed"}]
    )
    history = store.record_lab_operation(
        server_id,
        service_name=operation_service_name or server["name"],
        action=normalized_action,
        operator=resolve_lab_operator(),
        result=result,
        duration_ms=duration_ms,
        progress=progress,
        error_text=error_text,
        started_at=started_at,
        completed_at=completed_at,
    )
    response = {
        "server": decorate_lab_operation_availability(app, store.get_lab_server(server_id)),
        "operation": history,
        "output": output,
        "command": command,
    }
    if result != "success":
        raise LabOperationError(json.dumps(response))
    return response


def run_lab_server_health_check(store: LabRepositoryPort, server_id: int) -> dict[str, Any]:
    server = store.get_lab_server(server_id)
    if not server["enabled"]:
        return store.update_lab_server_health(
            server_id,
            overall_status="Unknown",
            process_status="Unknown",
            application_status="Unknown",
            protocol_status="Unknown",
            recent_error="Server is disabled.",
        )
    application_status, application_error = run_lab_application_check(server)
    protocol_status, protocol_note = run_lab_protocol_check(server, application_status)
    process_status = "Unknown"
    operation = server.get("operation") or {}
    if application_status == "Healthy" and operation.get("controlType") == "docker-compose":
        process_status = "Healthy"
    elif operation.get("controlType") == "internal-tool":
        process_status = "Healthy"
    checks = {
        "process": process_status,
        "application": application_status,
        "protocol": protocol_status,
    }
    recent_error = application_error if application_status == "Down" else ""
    if not recent_error and protocol_status in {"Degraded", "Down"}:
        recent_error = protocol_note
    return store.update_lab_server_health(
        server_id,
        overall_status=derive_lab_overall_status(checks),
        process_status=checks["process"],
        application_status=checks["application"],
        protocol_status=checks["protocol"],
        recent_error=recent_error,
    )


def resolve_lab_operator() -> str:
    return (
        os.environ.get("USERNAME")
        or os.environ.get("USER")
        or os.environ.get("LOGNAME")
        or "local-user"
    ).strip() or "local-user"


def restart_progress_steps(result: str, error_text: str = "") -> list[dict[str, str]]:
    steps = ["stop", "start", "wait_for_port", "application_health", "smoke", "final_status"]
    if result == "success":
        return [{"step": step, "status": "completed"} for step in steps]
    return [
        {
            "step": step,
            "status": "failed" if step == "final_status" else "completed",
            **({"error": error_text} if step == "final_status" and error_text else {}),
        }
        for step in steps
    ]


def run_internal_lab_operation(
    server: dict[str, Any],
    action: str,
    *,
    app: ApplicationPort,
    store: LabRepositoryPort,
    lines: int = 200,
) -> dict[str, Any]:
    service_name = server["name"]
    if action not in {"status", "smoke", "logs"}:
        raise LabOperationError(f"{service_name} does not support {action}.")
    if service_name == "GDT Bridge":
        bridge_dirs = ensure_gdt_bridge_dirs(app.config["GDT_BRIDGE_PATH"])
        status = {
            "bridgePath": str(bridge_dirs["root"]),
            "folders": {name: str(path) for name, path in bridge_dirs.items() if name != "root"},
        }
    elif service_name == "HL7Tester":
        status = {
            "message": "HL7Tester is monitored as an external service in Healthcare Lab.",
            "host": server.get("host"),
            "port": server.get("port"),
        }
    elif service_name == "GDT Hospital":
        status = {
            "bridgeRoot": app.config["GDT_BRIDGE_PATH"],
            "message": "GDT workflow APIs live in ECG AP Simulator; Healthcare Lab monitors runtime health only.",
        }
    else:
        status = {"message": f"No internal operation adapter for {service_name}."}
    output = json.dumps(status, indent=2)
    if action == "logs":
        output = "\n".join(output.splitlines()[-max(1, lines):])
    return {"output": output, "returnCode": 0, "command": ["internal", service_name, action]}


def decorate_lab_operation_availability(app: ApplicationPort, server: dict[str, Any]) -> dict[str, Any]:
    item = {**server}
    operation = {**(server.get("operation") or {})}
    if operation.get("controlType") == "docker-compose":
        reason = DockerComposeLabOperationAdapter(app.config["LAB_DEPLOY_SCRIPT"]).unavailable_reason()
        if reason:
            actions = operation.get("supportedActions") or []
            unavailable_actions = [action for action in actions if action != "smoke"]
            operation["supportedActions"] = [action for action in actions if action == "smoke"]
            operation["unavailableActions"] = unavailable_actions
            operation["unavailableReason"] = reason
    item["operation"] = operation
    return item


def dashboard_group_item(app: ApplicationPort, store: LabRepositoryPort, service_id: str) -> dict[str, Any]:
    group, servers = dashboard_servers_for_group(store, service_id)
    primary = next((server for server in servers if server["name"] == group["primary"]), servers[0])
    decorated_primary = decorate_lab_operation_availability(app, primary)
    status = derive_dashboard_group_status(servers)
    supported = set(decorated_primary.get("operation", {}).get("supportedActions") or [])
    process_statuses = [server.get("checks", {}).get("process", "Unknown") for server in servers]
    application_statuses = [server.get("checks", {}).get("application", "Unknown") for server in servers]
    protocol_statuses = [server.get("checks", {}).get("protocol", "Unknown") for server in servers]
    return {
        "id": service_id,
        "label": group["label"],
        "protocol": group["protocol"],
        "backend": group["backend"],
        "status": status,
        "enabled": all(server.get("enabled") for server in servers),
        "lastCheckAt": max((server.get("lastCheckAt") or "" for server in servers), default=""),
        "checks": {
            "process": min(process_statuses, key=dashboard_health_rank) if process_statuses else "Unknown",
            "application": min(application_statuses, key=dashboard_health_rank) if application_statuses else "Unknown",
            "protocol": min(protocol_statuses, key=dashboard_health_rank) if protocol_statuses else "Unknown",
        },
        "capabilities": {
            "check": True,
            "enable": "start" in supported,
            "disable": "stop" in supported,
            "restart": "restart" in supported,
        },
        "restartPreview": {
            "risk": group["risk"],
            "summary": group["riskSummary"],
            "affectedServices": list(group["affectedServices"]),
        },
        "children": dashboard_child_items(app, group),
        "components": [
            {
                "name": server["name"],
                "status": server["overallStatus"],
                "role": "primary" if server["name"] == group["primary"] else "supporting",
            }
            for server in servers
        ],
    }


def dashboard_child_item(app: ApplicationPort, child: dict[str, Any]) -> dict[str, Any]:
    adapter = DockerComposeLabOperationAdapter(app.config["LAB_DEPLOY_SCRIPT"])
    unavailable_reason = adapter.unavailable_reason()
    try:
        runtime = adapter.inspect(str(child["service"]), timeout_seconds=3)
    except LabOperationError as exc:
        runtime = {
            "exists": False,
            "running": False,
            "state": "Unknown",
            "detail": str(exc),
            "containerName": "",
        }
    return {
        "id": child["id"],
        "name": child["displayName"],
        "role": child["role"],
        "composeService": child["service"],
        "status": "Healthy" if runtime["running"] else (
            "Down" if runtime["state"] != "Unknown" else "Unknown"
        ),
        "runtime": runtime,
        "capabilities": {
            "check": True,
            "enable": not bool(unavailable_reason),
            "disable": not bool(unavailable_reason),
            "restart": not bool(unavailable_reason),
        },
    }


def dashboard_child_items(app: ApplicationPort, group: dict[str, Any]) -> list[dict[str, Any]]:
    children = list(group.get("children", ()))
    if not children:
        return []
    with ThreadPoolExecutor(max_workers=len(children)) as executor:
        return list(executor.map(lambda child: dashboard_child_item(app, child), children))


def dashboard_all_group_items(app: ApplicationPort, store: LabRepositoryPort) -> list[dict[str, Any]]:
    service_ids = list(LAB_DASHBOARD_SERVICE_GROUPS)
    with ThreadPoolExecutor(max_workers=len(service_ids)) as executor:
        return list(
            executor.map(
                lambda service_id: dashboard_group_item(app, store, service_id),
                service_ids,
            )
        )


def run_dashboard_group_health_check(
    store: LabRepositoryPort,
    service_id: str,
    *,
    health_checker=run_lab_server_health_check,
) -> list[dict[str, Any]]:
    _group, servers = dashboard_servers_for_group(store, service_id)
    return [health_checker(store, int(server["id"])) for server in servers]


def dashboard_events(store: LabRepositoryPort, items: list[dict[str, Any]], resource_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for item in items:
        if item["lastCheckAt"]:
            events.append(
                {
                    "timestamp": item["lastCheckAt"],
                    "level": "info" if item["status"] == "Healthy" else "warn",
                    "serviceId": item["id"],
                    "message": f"{item['label']} health is {item['status']}.",
                }
            )
    for operation in store.list_lab_operations(limit=12):
        level = "info" if operation["result"] == "success" else "error"
        events.append(
            {
                "timestamp": operation["completedAt"] or operation["startedAt"],
                "level": level,
                "serviceId": "",
                "message": f"{operation['serviceName']} {operation['action']} {operation['result']}.",
            }
        )
    if resource_snapshot["status"] != "ok":
        events.append(
            {
                "timestamp": resource_snapshot["collectedAt"],
                "level": "warn",
                "serviceId": "",
                "message": f"Resource snapshot unavailable: {resource_snapshot['message']}",
            }
        )
    return sorted(events, key=lambda event: event["timestamp"], reverse=True)[:20]


def derive_lab_overall_status(checks: dict[str, str]) -> str:
    values = [checks.get(level, "Unknown") for level in ("process", "application", "protocol")]
    known = [value for value in values if value != "Unknown"]
    if not known:
        return "Unknown"
    if "Down" in known:
        return "Down"
    if "Degraded" in known or len(known) != len(values):
        return "Degraded"
    return "Healthy"


def run_lab_protocol_check(
    server: dict[str, Any], application_status: str
) -> tuple[str, str]:
    protocol = str(server.get("protocol") or "None")
    if protocol == "GDT" and application_status == "Healthy":
        return "Healthy", "File-based GDT contract is represented by the internal lab service."
    if protocol in {"None", "GDT"}:
        return "Unknown", "No Phase 1 protocol endpoint check configured."
    if application_status == "Healthy":
        return "Healthy", "Protocol smoke check passed through application reachability."
    if application_status == "Down":
        return "Unknown", "Protocol smoke check skipped because application check failed."
    return "Unknown", "Protocol smoke check is not implemented for this service."


def smoke_status_from_steps(steps: list[dict[str, Any]]) -> str:
    required = [step for step in steps if step.get("required", True)]
    optional = [step for step in steps if not step.get("required", True)]
    if any(step["status"] == "Down" for step in required):
        return "Down"
    if any(step["status"] == "Degraded" for step in steps):
        return "Degraded"
    if any(step["status"] == "Down" for step in optional):
        return "Degraded"
    known = [step for step in steps if step["status"] != "Unknown"]
    if not known:
        return "Unknown"
    if len(known) != len(steps):
        return "Degraded"
    return "Healthy"


MEDPLUM_AUTH_NOT_CONFIGURED_MESSAGE = (
    "Auth not configured: set MEDPLUM_CLIENT_ID and MEDPLUM_CLIENT_SECRET on lab-app."
)


def describe_medplum_token_failure(exc: Exception) -> str:
    return f"Token request failed: {exc}"


def describe_medplum_service_request_failure(exc: Exception) -> str:
    message = str(exc)
    if "Medplum returned HTTP 401:" in message:
        return f"FHIR data fetch unauthorized: {message}"
    return f"ServiceRequest fetch failed: {message}"


def describe_medplum_diagnostic_report_failure(exc: Exception) -> str:
    message = str(exc)
    if "Medplum returned HTTP 401:" in message:
        return f"FHIR DiagnosticReport fetch unauthorized: {message}"
    return f"DiagnosticReport fetch failed: {message}"


def run_gdt_bridge_smoke(app: ApplicationPort, server: dict[str, Any]) -> list[dict[str, Any]]:
    steps = [run_lab_application_check(server)]
    application_step = smoke_step("application_endpoint", steps[0][0], steps[0][1], required=False)
    try:
        bridge_dirs = validate_gdt_bridge_dirs(app.config["GDT_BRIDGE_PATH"])
        probe_path = bridge_dirs["root"] / ".lab-smoke-probe"
        probe_path.write_text("ok", encoding="utf-8")
        read_back = probe_path.read_text(encoding="utf-8")
        probe_path.unlink(missing_ok=True)
        folder_step = smoke_step(
            "folder_write_read",
            "Healthy" if read_back == "ok" else "Down",
            str(bridge_dirs["root"]),
        )
        structure_step = smoke_step("folder_structure", "Healthy", str(bridge_dirs["root"]))
        contract_step = smoke_step(
            "bridge_folder_contract", "Healthy", "GDT bridge folders are writable."
        )
    except (OSError, SimulatorValidationError) as exc:
        folder_step = smoke_step("folder_write_read", "Down", str(exc))
        structure_step = smoke_step("folder_structure", "Down", str(exc))
        contract_step = smoke_step("bridge_folder_contract", "Down", str(exc))
    openemr_source = app.extensions.get("openemr_procedure_order_source")
    openemr_status = openemr_source.status() if openemr_source else {"configured": False}
    return [
        structure_step,
        folder_step,
        contract_step,
        smoke_step(
            "openemr_source_status",
            "Healthy" if openemr_status.get("configured") else "Unknown",
            json.dumps(openemr_status),
            required=False,
        ),
        application_step,
    ]


def run_gdt_folder_contract_smoke(app: ApplicationPort) -> dict[str, Any]:
    try:
        bridge_dirs = validate_gdt_bridge_dirs(app.config["GDT_BRIDGE_PATH"])
        probe_path = bridge_dirs["root"] / ".lab-smoke-probe"
        probe_path.write_text("ok", encoding="utf-8")
        read_back = probe_path.read_text(encoding="utf-8")
        probe_path.unlink(missing_ok=True)
        if read_back != "ok":
            return smoke_step(
                "gdt_folder_contract",
                "Down",
                f"Read-back mismatch under {bridge_dirs['root']}.",
            )
        return smoke_step(
            "gdt_folder_contract",
            "Healthy",
            f"GDT bridge folders are writable at {bridge_dirs['root']}.",
        )
    except (OSError, SimulatorValidationError) as exc:
        return smoke_step("gdt_folder_contract", "Down", str(exc))


def run_openemr_gdt_backend_verify(app: ApplicationPort, server: dict[str, Any]) -> list[dict[str, Any]]:
    base_url = str(server.get("baseUrl") or "").rstrip("/")
    operation = server.get("operation") or {}
    backing_service = str(operation.get("backingService") or "").strip()
    smoke_base_url = base_url
    if operation.get("controlType") == "docker-compose":
        smoke_base_url = DOCKER_COMPOSE_APPLICATION_URLS.get(backing_service, base_url)
    steps = [run_http_smoke(smoke_base_url, "openemr_http")]
    openemr_source = app.extensions.get("openemr_procedure_order_source")
    if openemr_source is None:
        steps.extend(
            [
                smoke_step("openemr_db_connection", "Down", "OpenEMR procedure-order source is unavailable."),
                smoke_step("openemr_order_schema", "Unknown", "Skipped because source is unavailable."),
                smoke_step("openemr_ecg_orders", "Unknown", "Skipped because source is unavailable.", required=False),
            ]
        )
    else:
        verify_result = openemr_source.verify_order_query()
        connection = verify_result["connection"]
        schema = verify_result["schema"]
        orders = verify_result["orders"]
        steps.extend(
            [
                smoke_step("openemr_db_connection", connection["status"], connection["message"]),
                smoke_step("openemr_order_schema", schema["status"], schema["message"]),
                smoke_step(
                    "openemr_ecg_orders",
                    orders["status"],
                    orders["message"],
                    required=False,
                ),
            ]
        )
    steps.append(run_gdt_folder_contract_smoke(app))
    return steps


def run_lab_smoke_check(
    app: ApplicationPort,
    store: LabRepositoryPort,
    server: dict[str, Any],
    *,
    auth_manager: MedplumAuthManager | None = None,
) -> dict[str, Any]:
    profile = server["operation"].get("smokeProfile") or ""
    base_url = str(server.get("baseUrl") or "").rstrip("/")
    steps: list[dict[str, Any]]
    if profile == "medplum":
        metadata_url = f"{base_url}/metadata" if base_url else ""
        steps = [
            run_http_smoke(base_url, "http_reachability"),
            run_http_smoke(metadata_url, "fhir_metadata", required=True),
        ]
        if auth_manager is not None and auth_manager.is_configured() and base_url:
            try:
                auth_manager.get_access_token(base_url)
                steps.append(smoke_step("oauth_token", "Healthy", "Token acquired.", required=False))
            except (ValidationError, UpstreamFhirError) as exc:
                steps.append(smoke_step("oauth_token", "Down", describe_medplum_token_failure(exc), required=False))
        else:
            steps.append(smoke_step("oauth_token", "Unknown", MEDPLUM_AUTH_NOT_CONFIGURED_MESSAGE, required=False))
        if base_url:
            try:
                fetch_result = fetch_fhir_service_requests(
                    base_url,
                    "",
                    auth_manager=auth_manager if auth_manager and auth_manager.is_configured() else None,
                )
                steps.append(
                    smoke_step(
                        "service_request_fetch",
                        "Healthy" if fetch_result["resourceType"] == "Bundle" else "Degraded",
                        f"HTTP {fetch_result['status']}",
                        required=False,
                    )
                )
            except (ValidationError, UpstreamFhirError) as exc:
                steps.append(smoke_step("service_request_fetch", "Down", describe_medplum_service_request_failure(exc), required=False))
            try:
                diagnostic_result = fetch_fhir_diagnostic_report_bundle(
                    base_url,
                    "",
                    patient_reference="Patient/lab-smoke-probe",
                    auth_manager=auth_manager if auth_manager and auth_manager.is_configured() else None,
                )
                report_count = len(diagnostic_result["reports"])
                steps.append(
                    smoke_step(
                        "diagnostic_report_fetch",
                        "Healthy" if diagnostic_result["resourceType"] == "Bundle" else "Degraded",
                        f"HTTP {diagnostic_result['status']}; {report_count} report(s).",
                        required=False,
                    )
                )
            except (ValidationError, UpstreamFhirError) as exc:
                steps.append(smoke_step("diagnostic_report_fetch", "Down", describe_medplum_diagnostic_report_failure(exc), required=False))
        else:
            steps.append(smoke_step("service_request_fetch", "Unknown", "FHIR base URL is not configured.", required=False))
            steps.append(smoke_step("diagnostic_report_fetch", "Unknown", "FHIR base URL is not configured.", required=False))
    elif profile == "gdt-bridge":
        steps = run_gdt_bridge_smoke(app, server)
    elif profile == "dcm4chee":
        dcm4chee_profile = dcm4chee_profile_from_config(app.config)
        diagnostics = validate_dcm4chee_profile(dcm4chee_profile)
        dimse = dcm4chee_profile["dimse"]
        steps = [
            smoke_step(
                "connection_profile",
                diagnostics["status"],
                diagnostics["summary"],
            ),
            run_http_smoke(dcm4chee_profile["webUiUrl"], "dicom_archive_http"),
            run_tcp_smoke(dimse["host"], dimse["port"], "dicom_dimse", required=False),
        ]
    elif profile == "oie":
        check_config = server.get("checkConfig") or {}
        mllp_host = str(check_config.get("mllpHost") or "").strip()
        mllp_port = check_config.get("mllpPort")
        operation = server.get("operation") or {}
        backing_service = str(operation.get("backingService") or "").strip()
        smoke_base_url = base_url
        if operation.get("controlType") == "docker-compose":
            smoke_base_url = DOCKER_COMPOSE_APPLICATION_URLS.get(backing_service, base_url)
        if backing_service == "oie" and mllp_host in {"127.0.0.1", "localhost"}:
            mllp_host = "oie"
        steps = [
            run_http_smoke(smoke_base_url, "oie_http"),
            run_tcp_smoke(mllp_host, mllp_port, "mllp_endpoint", required=False),
        ]
    elif profile == "hl7tester":
        steps = [
            run_tcp_smoke(str(server.get("host") or ""), server.get("port"), "hl7_listener", required=False),
            smoke_step(
                "pdf_ed_tool",
                "Healthy",
                "tests/test_b64_pdf.py is available."
                if Path("tests/test_b64_pdf.py").exists()
                else "Tool not found.",
                required=False,
            ),
        ]
    elif profile == "gdt-hospital":
        steps = [
            smoke_step("gdt_order_store", "Healthy", f"{len(store.list_gdt_orders())} order(s)."),
            smoke_step("bridge_contract", "Healthy", app.config["GDT_BRIDGE_PATH"]),
        ]
    elif profile == "openemr":
        steps = run_openemr_gdt_backend_verify(app, server)
    else:
        steps = [smoke_step("adapter", "Unknown", "No smoke profile is configured.", required=False)]
    overall_status = smoke_status_from_steps(steps)
    return {
        "profile": profile,
        "status": overall_status,
        "steps": steps,
        "requiredFailures": [step for step in steps if step.get("required", True) and step["status"] == "Down"],
        "optionalFailures": [step for step in steps if not step.get("required", True) and step["status"] == "Down"],
    }
