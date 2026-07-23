"""Independent, bounded, and redacted dcm4chee connectivity diagnostics."""

from __future__ import annotations

import json
import socket
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from backend.clients.dcm4chee_diagnostics import (
    MAX_QIDO_RESPONSE_BYTES,
    http_get,
    tcp_connect,
)


DEFAULT_DIAGNOSTIC_TIMEOUT_SECONDS = 2.0

HttpProbe = Callable[[str, float], Mapping[str, Any]]
TcpProbe = Callable[[str, int, float], Any]


class Dcm4cheeDiagnostics:
    """Run redacted endpoint checks against one effective profile snapshot."""

    def __init__(
        self,
        profile: Any | None = None,
        *,
        timeout_seconds: float = DEFAULT_DIAGNOSTIC_TIMEOUT_SECONDS,
        http_probe: HttpProbe | None = None,
        tcp_probe: TcpProbe | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self._profile = profile
        self._timeout_seconds = float(timeout_seconds)
        self._http_probe = http_probe or http_get
        self._tcp_probe = tcp_probe or tcp_connect

    def run(self, profile: Any | None = None) -> dict[str, Any]:
        effective_profile = self._profile if profile is None else profile
        checks = [
            self._check_web_ui(_value(effective_profile, "webUiUrl")),
            self._check_qido(_value(effective_profile, "dicomweb", "qidoRsUrl")),
            self._check_tcp(
                "hl7-tcp",
                _value(effective_profile, "hl7", "host"),
                _value(effective_profile, "hl7", "port"),
            ),
            self._check_tcp(
                "dimse-tcp",
                _value(effective_profile, "dimse", "host"),
                _value(effective_profile, "dimse", "port"),
            ),
        ]
        return {
            "state": (
                "healthy"
                if all(check["state"] == "passed" for check in checks)
                else "degraded"
            ),
            "checks": checks,
        }

    def _check_web_ui(self, value: Any) -> dict[str, Any]:
        url = _text(value)
        if not url:
            return _result("web-ui-http", "failed", "not-configured")
        try:
            response = self._http_probe(url, self._timeout_seconds)
            status = _http_status(response)
            if 100 <= status <= 499:
                return _result(
                    "web-ui-http", "passed", "http-reachable", http_status=status
                )
            return _result(
                "web-ui-http", "failed", "http-error", http_status=status
            )
        except (TimeoutError, socket.timeout):
            return _result("web-ui-http", "failed", "timed-out")
        except Exception:
            return _result("web-ui-http", "failed", "unreachable")

    def _check_qido(self, value: Any) -> dict[str, Any]:
        url = _text(value)
        if not url:
            return _result("qido-rs", "failed", "not-configured")
        try:
            response = self._http_probe(_qido_metadata_url(url), self._timeout_seconds)
            status = _http_status(response)
            if not 200 <= status <= 299:
                return _result(
                    "qido-rs", "failed", "http-error", http_status=status
                )
            body = response.get("body", b"")
            if isinstance(body, str):
                body = body.encode("utf-8")
            if not isinstance(body, bytes) or len(body) > MAX_QIDO_RESPONSE_BYTES:
                return _result("qido-rs", "failed", "invalid-response")
            metadata = json.loads(body.decode("utf-8"))
            if not isinstance(metadata, list):
                return _result("qido-rs", "failed", "invalid-response")
            return _result(
                "qido-rs", "passed", "metadata-reachable", http_status=status
            )
        except (TimeoutError, socket.timeout):
            return _result("qido-rs", "failed", "timed-out")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return _result("qido-rs", "failed", "invalid-response")
        except Exception:
            return _result("qido-rs", "failed", "unreachable")

    def _check_tcp(self, role: str, host_value: Any, port_value: Any) -> dict[str, str]:
        host = _text(host_value)
        try:
            port = int(port_value)
        except (TypeError, ValueError):
            port = 0
        if not host or not 1 <= port <= 65_535:
            return _result(role, "failed", "not-configured")
        try:
            connection = self._tcp_probe(host, port, self._timeout_seconds)
            close = getattr(connection, "close", None)
            if callable(close):
                close()
            return _result(role, "passed", "transport-reachable")
        except (TimeoutError, socket.timeout):
            return _result(role, "failed", "timed-out")
        except Exception:
            return _result(role, "failed", "unreachable")


def diagnose_dcm4chee(
    profile: Any,
    *,
    timeout_seconds: float = DEFAULT_DIAGNOSTIC_TIMEOUT_SECONDS,
    http_probe: HttpProbe | None = None,
    tcp_probe: TcpProbe | None = None,
) -> dict[str, Any]:
    return Dcm4cheeDiagnostics(
        profile,
        timeout_seconds=timeout_seconds,
        http_probe=http_probe,
        tcp_probe=tcp_probe,
    ).run()


def _qido_metadata_url(base_url: str) -> str:
    parts = urlsplit(base_url)
    path = parts.path.rstrip("/")
    if not path.endswith("/studies"):
        path += "/studies"
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["limit"] = "1"
    return urlunsplit((parts.scheme, parts.netloc, path, urlencode(query), ""))


def _value(source: Any, *path: str) -> Any:
    value = source
    for part in path:
        if isinstance(value, Mapping):
            value = value.get(part)
        else:
            value = getattr(value, part, None)
        if value is None:
            break
    return value


def _text(value: Any) -> str:
    return str(value or "").strip()


def _http_status(response: Mapping[str, Any]) -> int:
    try:
        return int(response.get("status", 0))
    except (TypeError, ValueError):
        return 0


def _result(
    role: str,
    state: str,
    code: str,
    *,
    http_status: int | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"role": role, "state": state, "code": code}
    if http_status is not None:
        result["httpStatus"] = http_status
    return result
