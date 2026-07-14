from __future__ import annotations

import http.client
import json
import shutil
import socket
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any

from .domain.errors import LabOperationError
from .domain.lab import LAB_OPERATION_ACTIONS

DOCKER_SOCKET_PATH = "/var/run/docker.sock"
DOCKER_COMPOSE_PROJECT = "interoperability-lab"
DOCKER_SOCKET_STOP_GRACE_SECONDS = 10


class DockerSocketHttpConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str = DOCKER_SOCKET_PATH):
        super().__init__("localhost")
        self.socket_path = socket_path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.socket_path)


class DockerSocketLabOperationAdapter:
    def __init__(
        self,
        socket_path: str = DOCKER_SOCKET_PATH,
        project_name: str = DOCKER_COMPOSE_PROJECT,
    ):
        self.socket_path = socket_path
        self.project_name = project_name

    def is_available(self) -> bool:
        return hasattr(socket, "AF_UNIX") and Path(self.socket_path).exists()

    def request(self, method: str, path: str) -> tuple[int, bytes]:
        connection = DockerSocketHttpConnection(self.socket_path)
        try:
            connection.request(method, path)
            response = connection.getresponse()
            return response.status, response.read()
        except OSError as exc:
            raise LabOperationError(f"Docker socket request failed: {exc}") from exc
        finally:
            connection.close()

    def containers_for_service(self, service_name: str) -> list[dict[str, Any]]:
        filters = {
            "label": [
                f"com.docker.compose.project={self.project_name}",
                f"com.docker.compose.service={service_name}",
            ]
        }
        query = urllib.parse.urlencode({"all": "1", "filters": json.dumps(filters)})
        status, body = self.request("GET", f"/containers/json?{query}")
        if status != 200:
            raise LabOperationError(
                f"Docker socket returned HTTP {status} while listing containers."
            )
        try:
            containers = json.loads(body.decode("utf-8") or "[]")
        except json.JSONDecodeError as exc:
            raise LabOperationError("Docker socket returned invalid container JSON.") from exc
        return containers if isinstance(containers, list) else []

    def inspect(self, service_name: str) -> dict[str, Any]:
        if not self.is_available():
            raise LabOperationError(f"Docker socket is not available at {self.socket_path}.")
        containers = self.containers_for_service(service_name)
        if not containers:
            return {
                "exists": False,
                "running": False,
                "state": "Missing",
                "detail": "No Compose container exists for this service.",
                "containerName": "",
            }
        container = containers[0]
        state = str(container.get("State") or "unknown").lower()
        container_id = str(container.get("Id") or "")
        name = (container.get("Names") or [container_id[:12]])[0].lstrip("/")
        return {
            "exists": True,
            "running": state == "running",
            "state": "Running" if state == "running" else state.title(),
            "detail": str(container.get("Status") or state),
            "containerName": name,
        }

    def run(
        self,
        action: str,
        backing_service: str,
        *,
        timeout_seconds: int,
        lines: int = 200,
    ) -> dict[str, Any]:
        if action not in {"start", "stop", "restart"}:
            raise LabOperationError(f"Docker socket adapter does not support {action}.")
        if not self.is_available():
            raise LabOperationError(f"Docker socket is not available at {self.socket_path}.")
        containers = self.containers_for_service(backing_service)
        if not containers:
            raise LabOperationError(f"No compose container found for service '{backing_service}'.")
        command = ["docker-socket", action, backing_service]
        output_lines = []
        for container in containers:
            container_id = container.get("Id") or ""
            name = (container.get("Names") or [container_id[:12]])[0].lstrip("/")
            if not container_id:
                continue
            endpoint = f"/containers/{container_id}/{action}"
            if action in {"stop", "restart"}:
                stop_grace_seconds = min(
                    max(1, int(timeout_seconds)),
                    DOCKER_SOCKET_STOP_GRACE_SECONDS,
                )
                endpoint = f"{endpoint}?t={stop_grace_seconds}"
            status, body = self.request("POST", endpoint)
            if status not in {204, 304}:
                detail = body.decode("utf-8", errors="replace").strip()
                raise LabOperationError(
                    f"Docker socket {action} failed for {name}: HTTP {status}. {detail}"
                )
            state = "already in requested state" if status == 304 else "ok"
            output_lines.append(f"{action} {name}: {state}")
        return {"output": "\n".join(output_lines), "returnCode": 0, "command": command}


class DockerComposeLabOperationAdapter:
    def __init__(self, script_path: str | Path):
        self.script_path = Path(script_path)

    def unavailable_reason(self) -> str:
        if DockerSocketLabOperationAdapter().is_available():
            return ""
        if not self.script_path.exists():
            return f"Lab operation script was not found: {self.script_path}"
        if shutil.which("powershell") is None:
            return "PowerShell is not available in this runtime."
        if shutil.which("docker") is None:
            return "Docker CLI is not available in this runtime."
        return ""

    def build_command(self, action: str, backing_service: str, *, lines: int = 200) -> list[str]:
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.script_path),
            action,
            backing_service,
        ]
        if action == "logs":
            command.extend(["-Lines", str(lines)])
        return command

    @staticmethod
    def parse_compose_ps_json(output: str | None) -> list[dict[str, Any]]:
        text = (output or "").strip()
        if not text:
            return []
        try:
            payload = json.loads(text)
            return payload if isinstance(payload, list) else [payload]
        except json.JSONDecodeError:
            rows = []
            for line in text.splitlines():
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise LabOperationError("Docker Compose returned invalid service status JSON.") from exc
                if isinstance(item, dict):
                    rows.append(item)
            return rows

    def inspect(self, backing_service: str, *, timeout_seconds: int = 30) -> dict[str, Any]:
        socket_adapter = DockerSocketLabOperationAdapter()
        if socket_adapter.is_available():
            return socket_adapter.inspect(backing_service)
        reason = self.unavailable_reason()
        if reason:
            raise LabOperationError(reason)
        command = self.build_command("inspect", backing_service)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(1, int(timeout_seconds)),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise LabOperationError(
                f"Service status check timed out after {timeout_seconds} seconds."
            ) from exc
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise LabOperationError(detail or "Docker Compose service status check failed.")
        rows = self.parse_compose_ps_json(completed.stdout)
        if not rows:
            return {
                "exists": False,
                "running": False,
                "state": "Missing",
                "detail": "No Compose container exists for this service.",
                "containerName": "",
            }
        row = rows[0]
        state = str(row.get("State") or "unknown").lower()
        return {
            "exists": True,
            "running": state == "running",
            "state": "Running" if state == "running" else state.title(),
            "detail": str(row.get("Status") or state),
            "containerName": str(row.get("Name") or ""),
        }

    def run(
        self,
        action: str,
        backing_service: str,
        *,
        timeout_seconds: int,
        lines: int = 200,
    ) -> dict[str, Any]:
        if action not in LAB_OPERATION_ACTIONS:
            raise LabOperationError(f"Unsupported operation action: {action}.")
        socket_adapter = DockerSocketLabOperationAdapter()
        if socket_adapter.is_available() and action in {"start", "stop", "restart"}:
            return socket_adapter.run(
                action,
                backing_service or "all",
                timeout_seconds=timeout_seconds,
                lines=lines,
            )
        if not self.script_path.exists():
            raise LabOperationError(f"Lab operation script was not found: {self.script_path}")
        command = self.build_command(action, backing_service or "all", lines=lines)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(1, int(timeout_seconds)),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise LabOperationError(
                f"Operation timed out after {timeout_seconds} seconds."
            ) from exc
        output = "\n".join(
            value for value in (completed.stdout.strip(), completed.stderr.strip()) if value
        )
        if completed.returncode != 0:
            raise LabOperationError(output or f"Operation exited with {completed.returncode}.")
        return {"output": output, "returnCode": completed.returncode, "command": command}
