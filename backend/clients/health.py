"""HTTP and TCP reachability probes for lab services."""

from __future__ import annotations

import socket
import urllib.error
import urllib.request
from typing import Any

DOCKER_COMPOSE_APPLICATION_URLS = {
    "oie": "http://oie:8080",
    "medplum": "http://medplum:8103/fhir/R4",
    "openemr": "http://openemr:80",
    "dcm4chee": "http://dcm4chee:8080/dcm4chee-arc/ui2",
}


def run_lab_application_check(
    server: dict[str, Any], timeout_seconds: float = 2.0
) -> tuple[str, str]:
    base_url = str(server.get("baseUrl") or "").strip()
    operation = server.get("operation") or {}
    backing_service = str(operation.get("backingService") or "").strip()
    urls = []
    if (
        operation.get("controlType") == "docker-compose"
        and backing_service in DOCKER_COMPOSE_APPLICATION_URLS
    ):
        urls.append(DOCKER_COMPOSE_APPLICATION_URLS[backing_service])
    if base_url and base_url not in urls:
        urls.append(base_url)
    host = str(server.get("host") or "").strip()
    port = server.get("port")
    last_error = ""
    for url in urls:
        try:
            request_obj = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(request_obj, timeout=timeout_seconds) as response:
                if 200 <= int(response.status) < 500:
                    return "Healthy", ""
                return "Down", f"HTTP {response.status}"
        except urllib.error.HTTPError as exc:
            if 400 <= int(exc.code) < 500:
                return "Healthy", f"HTTP {exc.code}"
            return "Down", f"{url}: HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = f"{url}: {exc}"
            continue
    if (
        not urls
        and operation.get("controlType") == "internal-tool"
        and backing_service == "lab-app"
    ):
        return "Healthy", "Internal lab tool is provided by lab-app."
    if host and port:
        try:
            with socket.create_connection((host, int(port)), timeout_seconds):
                return "Healthy", ""
        except (OSError, socket.timeout) as exc:
            return "Down", str(exc)
    if urls:
        return "Down", last_error
    return "Unknown", "No application endpoint configured."


def smoke_step(name: str, status: str, message: str = "", *, required: bool = True) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "message": message,
        "required": required,
    }


def run_http_smoke(
    url: str,
    name: str,
    *,
    required: bool = True,
    timeout_seconds: float = 3,
) -> dict[str, Any]:
    if not url:
        return smoke_step(name, "Unknown", "Endpoint is not configured.", required=required)
    try:
        request_obj = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request_obj, timeout=timeout_seconds) as response:
            if 200 <= int(response.status) < 500:
                return smoke_step(name, "Healthy", f"HTTP {response.status}", required=required)
            return smoke_step(name, "Down", f"HTTP {response.status}", required=required)
    except urllib.error.HTTPError as exc:
        if 400 <= int(exc.code) < 500:
            return smoke_step(name, "Healthy", f"HTTP {exc.code}", required=required)
        return smoke_step(name, "Down", f"HTTP {exc.code}", required=required)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return smoke_step(name, "Down", str(exc), required=required)


def run_tcp_smoke(host: str, port: Any, name: str, *, required: bool = True) -> dict[str, Any]:
    if not host or not port:
        return smoke_step(name, "Unknown", "Host or port is not configured.", required=required)
    try:
        port_number = int(port)
    except (TypeError, ValueError):
        return smoke_step(name, "Down", "Port must be an integer between 1 and 65535.", required=required)
    if not 1 <= port_number <= 65535:
        return smoke_step(name, "Down", "Port must be an integer between 1 and 65535.", required=required)
    try:
        with socket.create_connection((host, port_number), 3):
            return smoke_step(name, "Healthy", "TCP reachable.", required=required)
    except (OSError, socket.timeout) as exc:
        return smoke_step(name, "Down", str(exc), required=required)
