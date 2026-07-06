from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import http.client
import json
import subprocess
import socket
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .lab_store import SimulatorValidationError

DOCKER_SOCKET_PATH = "/var/run/docker.sock"
DOCKER_COMPOSE_PROJECT = "interoperability-lab"
RESOURCE_SNAPSHOT_CACHE_SECONDS = 10.0
RESOURCE_SNAPSHOT_MAX_WORKERS = 8
_RESOURCE_SNAPSHOT_CACHE: dict[str, Any] = {"expires_at": 0.0, "snapshot": None}
_RESOURCE_SNAPSHOT_CACHE_LOCK = threading.Lock()

LAB_DASHBOARD_SERVICE_GROUPS = {
    "hl7-v2-oie": {
        "label": "HL7 v2 / OIE",
        "primary": "OIE",
        "services": ("OIE", "HL7Tester"),
        "protocol": "HL7 v2",
        "backend": "Open Integration Engine",
        "risk": "medium",
        "riskSummary": "Restart interrupts MLLP listeners and queued HL7 result-return demos.",
        "affectedServices": ("OIE", "HL7Tester", "AP Listener"),
    },
    "fhir-medplum": {
        "label": "HL7 FHIR / Medplum",
        "primary": "Medplum",
        "services": ("Medplum",),
        "protocol": "FHIR R4",
        "backend": "Medplum",
        "risk": "high",
        "riskSummary": "Restart can interrupt OAuth token acquisition and active FHIR artifact submissions.",
        "affectedServices": ("Medplum", "FHIR ServiceRequest fetch", "FHIR result submission"),
    },
    "openemr-gdt": {
        "label": "OpenEMR / GDT",
        "primary": "OpenEMR",
        "services": ("OpenEMR", "GDT Bridge", "GDT Hospital"),
        "protocol": "GDT 2.1",
        "backend": "OpenEMR + shared-folder bridge",
        "risk": "medium",
        "riskSummary": "Restart can pause OpenEMR order reads and shared-folder import/export checks.",
        "affectedServices": ("OpenEMR", "GDT Bridge", "GDT Hospital"),
    },
    "dicom-dcm4chee": {
        "label": "dcm4chee / DICOM",
        "primary": "dcm4chee",
        "services": ("dcm4chee",),
        "protocol": "DICOM",
        "backend": "dcm4chee archive",
        "risk": "medium",
        "riskSummary": "Restart interrupts archive availability and DICOM workflow smoke checks.",
        "affectedServices": ("dcm4chee", "DICOM archive UI"),
    },
}


def current_dashboard_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def dashboard_health_rank(status: str) -> int:
    return {"Down": 0, "Degraded": 1, "Unknown": 2, "Healthy": 3}.get(status, 2)


def derive_dashboard_group_status(servers: list[dict[str, Any]]) -> str:
    if not servers:
        return "Unknown"
    statuses = [server.get("overallStatus", "Unknown") for server in servers]
    if "Down" in statuses:
        return "Down"
    if "Degraded" in statuses:
        return "Degraded"
    if statuses and all(status == "Healthy" for status in statuses):
        return "Healthy"
    return "Unknown"


def dashboard_action_for_group(group: dict[str, Any], action: str) -> str:
    normalized = action.strip().lower()
    if normalized == "enable":
        return "start"
    if normalized == "disable":
        return "stop"
    if normalized == "restart":
        return "restart"
    raise SimulatorValidationError(f"Unsupported dashboard action: {normalized}.")


def dashboard_servers_for_group(store: Any, service_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    group = LAB_DASHBOARD_SERVICE_GROUPS.get(service_id)
    if not group:
        raise KeyError(service_id)
    by_name = {item["name"]: item for item in store.list_lab_servers()}
    servers = [by_name[name] for name in group["services"] if name in by_name]
    if not servers:
        raise KeyError(service_id)
    return group, servers


def dashboard_summary(items: list[dict[str, Any]], resource_snapshot: dict[str, Any]) -> dict[str, Any]:
    attention = [item for item in items if item["status"] in {"Degraded", "Down"}]
    running = [item for item in items if item["enabled"] and item["status"] != "Down"]
    return {
        "total": len(items),
        "running": len(running),
        "attention": len(attention),
        "resourceStatus": resource_snapshot["status"],
        "cpuPercent": resource_snapshot["totals"]["cpuPercent"],
        "memoryPercent": resource_snapshot["totals"]["memoryPercent"],
    }


def parse_docker_stats_percent(value: str) -> float:
    text = str(value or "").strip().replace("%", "")
    try:
        return round(float(text), 1)
    except ValueError:
        return 0.0


def parse_docker_memory_usage(value: str) -> tuple[float, float]:
    raw = str(value or "").split("/", 1)
    if len(raw) != 2:
        return 0.0, 0.0
    return parse_size_to_mib(raw[0]), parse_size_to_mib(raw[1])


def parse_size_to_mib(value: str) -> float:
    text = str(value or "").strip()
    units = {
        "b": 1 / (1024 * 1024),
        "kib": 1 / 1024,
        "kb": 1 / 1024,
        "mib": 1,
        "mb": 1,
        "gib": 1024,
        "gb": 1024,
    }
    for unit, multiplier in units.items():
        if text.lower().endswith(unit):
            number = text[: -len(unit)].strip()
            try:
                return round(float(number) * multiplier, 1)
            except ValueError:
                return 0.0
    try:
        return round(float(text), 1)
    except ValueError:
        return 0.0


class DockerSocketHttpConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str = DOCKER_SOCKET_PATH, timeout: int = 8):
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.socket_path)


def docker_socket_available(socket_path: str = DOCKER_SOCKET_PATH) -> bool:
    return hasattr(socket, "AF_UNIX") and Path(socket_path).exists()


def docker_socket_json_request(path: str, *, socket_path: str = DOCKER_SOCKET_PATH) -> Any:
    connection = DockerSocketHttpConnection(socket_path)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        body = response.read()
    finally:
        connection.close()
    if response.status != 200:
        detail = body.decode("utf-8", errors="replace").strip()
        raise OSError(f"Docker socket returned HTTP {response.status}. {detail}")
    return json.loads(body.decode("utf-8") or "{}")


def parse_docker_socket_cpu_percent(stats: dict[str, Any]) -> float:
    cpu_stats = stats.get("cpu_stats") or {}
    precpu_stats = stats.get("precpu_stats") or {}
    cpu_usage = cpu_stats.get("cpu_usage") or {}
    precpu_usage = precpu_stats.get("cpu_usage") or {}
    cpu_delta = float(cpu_usage.get("total_usage") or 0) - float(
        precpu_usage.get("total_usage") or 0
    )
    system_delta = float(cpu_stats.get("system_cpu_usage") or 0) - float(
        precpu_stats.get("system_cpu_usage") or 0
    )
    online_cpus = cpu_stats.get("online_cpus") or len(cpu_usage.get("percpu_usage") or []) or 1
    if cpu_delta <= 0 or system_delta <= 0:
        return 0.0
    return round((cpu_delta / system_delta) * float(online_cpus) * 100.0, 1)


def parse_docker_socket_memory_usage(stats: dict[str, Any]) -> tuple[float, float]:
    memory_stats = stats.get("memory_stats") or {}
    usage = float(memory_stats.get("usage") or 0)
    stats_block = memory_stats.get("stats") or {}
    usage -= float(stats_block.get("cache") or 0)
    limit = float(memory_stats.get("limit") or 0)
    mib = 1024 * 1024
    return round(max(0.0, usage) / mib, 1), round(max(0.0, limit) / mib, 1)


def collect_docker_socket_container_stats(item: dict[str, Any]) -> dict[str, Any] | None:
    container_id = item.get("Id")
    if not container_id:
        return None
    stats = docker_socket_json_request(f"/containers/{container_id}/stats?stream=false")
    name = (item.get("Names") or [container_id[:12]])[0].lstrip("/")
    cpu = parse_docker_socket_cpu_percent(stats)
    mem_used, mem_limit = parse_docker_socket_memory_usage(stats)
    return {
        "name": name,
        "cpuPercent": cpu,
        "memoryUsedMiB": mem_used,
        "memoryLimitMiB": mem_limit,
    }


def collect_dashboard_resource_snapshot_from_socket() -> dict[str, Any]:
    filters = {"label": [f"com.docker.compose.project={DOCKER_COMPOSE_PROJECT}"]}
    query = urllib.parse.urlencode({"filters": json.dumps(filters)})
    containers_payload = docker_socket_json_request(f"/containers/json?{query}")
    if not isinstance(containers_payload, list):
        containers_payload = []
    containers: list[dict[str, Any]] = []
    cpu_total = 0.0
    mem_used_total = 0.0
    mem_limit_total = 0.0
    max_workers = min(RESOURCE_SNAPSHOT_MAX_WORKERS, max(1, len(containers_payload)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(collect_docker_socket_container_stats, item)
            for item in containers_payload
        ]
        for future in as_completed(futures):
            container = future.result()
            if container is None:
                continue
            containers.append(container)
            cpu_total += container["cpuPercent"]
            mem_used_total += container["memoryUsedMiB"]
            mem_limit_total += container["memoryLimitMiB"]
    containers.sort(key=lambda container: container["name"])
    memory_percent = round((mem_used_total / mem_limit_total) * 100, 1) if mem_limit_total else 0.0
    return {
        "status": "ok" if containers else "unavailable",
        "message": "" if containers else "Docker socket returned no container rows.",
        "totals": {
            "cpuPercent": round(cpu_total, 1),
            "memoryUsedMiB": round(mem_used_total, 1),
            "memoryLimitMiB": round(mem_limit_total, 1),
            "memoryPercent": memory_percent,
        },
        "containers": containers,
        "collectedAt": current_dashboard_timestamp(),
    }


def collect_dashboard_resource_snapshot_from_cli() -> dict[str, Any]:
    command = [
        "docker",
        "stats",
        "--no-stream",
        "--format",
        "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}",
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )
    if completed.returncode != 0:
        return dashboard_resource_fallback(completed.stderr.strip() or completed.stdout.strip())
    containers = []
    cpu_total = 0.0
    mem_used_total = 0.0
    mem_limit_total = 0.0
    for line in completed.stdout.splitlines():
        columns = line.split("\t")
        if len(columns) != 3:
            continue
        cpu = parse_docker_stats_percent(columns[1])
        mem_used, mem_limit = parse_docker_memory_usage(columns[2])
        containers.append(
            {
                "name": columns[0],
                "cpuPercent": cpu,
                "memoryUsedMiB": mem_used,
                "memoryLimitMiB": mem_limit,
            }
        )
        cpu_total += cpu
        mem_used_total += mem_used
        mem_limit_total += mem_limit
    memory_percent = round((mem_used_total / mem_limit_total) * 100, 1) if mem_limit_total else 0.0
    return {
        "status": "ok" if containers else "unavailable",
        "message": "" if containers else "Docker stats returned no container rows.",
        "totals": {
            "cpuPercent": round(cpu_total, 1),
            "memoryUsedMiB": round(mem_used_total, 1),
            "memoryLimitMiB": round(mem_limit_total, 1),
            "memoryPercent": memory_percent,
        },
        "containers": containers,
        "collectedAt": current_dashboard_timestamp(),
    }


def collect_dashboard_resource_snapshot() -> dict[str, Any]:
    now = time.monotonic()
    with _RESOURCE_SNAPSHOT_CACHE_LOCK:
        cached_snapshot = _RESOURCE_SNAPSHOT_CACHE["snapshot"]
        if cached_snapshot is not None and now < _RESOURCE_SNAPSHOT_CACHE["expires_at"]:
            return cached_snapshot
    if docker_socket_available():
        try:
            snapshot = collect_dashboard_resource_snapshot_from_socket()
            if snapshot["status"] == "ok":
                with _RESOURCE_SNAPSHOT_CACHE_LOCK:
                    _RESOURCE_SNAPSHOT_CACHE["snapshot"] = snapshot
                    _RESOURCE_SNAPSHOT_CACHE["expires_at"] = (
                        time.monotonic() + RESOURCE_SNAPSHOT_CACHE_SECONDS
                    )
            return snapshot
        except (OSError, TimeoutError, json.JSONDecodeError) as exc:
            return dashboard_resource_fallback(f"Docker socket stats unavailable: {exc}")
    try:
        snapshot = collect_dashboard_resource_snapshot_from_cli()
        if snapshot["status"] == "ok":
            with _RESOURCE_SNAPSHOT_CACHE_LOCK:
                _RESOURCE_SNAPSHOT_CACHE["snapshot"] = snapshot
                _RESOURCE_SNAPSHOT_CACHE["expires_at"] = (
                    time.monotonic() + RESOURCE_SNAPSHOT_CACHE_SECONDS
                )
        return snapshot
    except (OSError, subprocess.TimeoutExpired) as exc:
        return dashboard_resource_fallback(str(exc))


def dashboard_resource_fallback(message: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "message": message or "Docker stats are unavailable in this runtime.",
        "totals": {
            "cpuPercent": 0.0,
            "memoryUsedMiB": 0.0,
            "memoryLimitMiB": 0.0,
            "memoryPercent": 0.0,
        },
        "containers": [],
        "collectedAt": current_dashboard_timestamp(),
    }
