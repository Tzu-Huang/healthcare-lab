"""Non-destructive, secret-safe OIE live preflight and MLLP smoke helper."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable


MLLP_START = b"\x0b"
MLLP_END = b"\x1c\x0d"
ACK_CODES = {"AA", "AE", "AR", "CA", "CE", "CR"}


def safe_error(exc: BaseException) -> str:
    """Return a bounded error category without leaking addresses or payloads."""
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "operation timed out"
    if isinstance(exc, ConnectionRefusedError):
        return "connection refused"
    if isinstance(exc, socket.gaierror):
        return "host resolution failed"
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return safe_error(exc.reason if isinstance(exc.reason, BaseException) else OSError())
    return re.sub(r"[^a-zA-Z0-9 ._-]", "", type(exc).__name__)[:80] or "operation failed"


def tcp_probe(host: str, port: int, timeout: float) -> dict[str, Any]:
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
        classification, detail = "pass", "TCP reachable"
    except (TimeoutError, socket.timeout) as exc:
        classification, detail = "blocked", safe_error(exc)
    except OSError as exc:
        classification, detail = "unavailable", safe_error(exc)
    return {
        "classification": classification,
        "detail": detail,
        "elapsedMs": round((time.monotonic() - started) * 1000),
    }


def parse_ack(payload: bytes) -> dict[str, Any]:
    raw = payload.removeprefix(MLLP_START)
    if raw.endswith(MLLP_END):
        raw = raw[: -len(MLLP_END)]
    text = raw.decode("utf-8", errors="replace")
    segments = [segment for segment in re.split(r"[\r\n]+", text) if segment]
    msa = next((segment.split("|") for segment in segments if segment.startswith("MSA|")), None)
    if not msa or len(msa) < 3 or msa[1] not in ACK_CODES:
        return {"classification": "fail", "detail": "valid MSA ACK not found"}
    control_id = msa[2]
    return {
        "classification": "pass" if msa[1] in {"AA", "CA"} else "fail",
        "detail": "ACK accepted" if msa[1] in {"AA", "CA"} else "ACK rejected",
        "ackCode": msa[1],
        "controlIdHash": hashlib.sha256(control_id.encode()).hexdigest()[:12],
    }


def send_fixture(path: Path, host: str, port: int, timeout: float) -> dict[str, Any]:
    try:
        payload = b"\r".join(path.read_bytes().decode("utf-8-sig").splitlines()).encode("utf-8")
    except (OSError, UnicodeError) as exc:
        return {"classification": "unavailable", "detail": safe_error(exc)}
    if not payload.startswith(b"MSH|") or b"\r" not in payload:
        return {"classification": "fail", "detail": "fixture is not a supported HL7 message"}
    try:
        response = bytearray()
        with socket.create_connection((host, port), timeout=timeout) as connection:
            connection.settimeout(timeout)
            connection.sendall(MLLP_START + payload + MLLP_END)
            while MLLP_END not in response:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                response.extend(chunk)
                if len(response) > 65536:
                    return {"classification": "fail", "detail": "ACK exceeded size limit"}
        return parse_ack(bytes(response))
    except (TimeoutError, socket.timeout) as exc:
        return {"classification": "blocked", "detail": safe_error(exc)}
    except OSError as exc:
        return {"classification": "unavailable", "detail": safe_error(exc)}


def poll_diagnostics(
    url: str,
    timeout: float,
    interval: float,
    *,
    fetch: Callable[[str, float], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    def default_fetch(target: str, request_timeout: float) -> dict[str, Any]:
        with urllib.request.urlopen(target, timeout=request_timeout) as response:
            return json.load(response)

    reader = fetch or default_fetch
    deadline = time.monotonic() + timeout
    last_state = "unavailable"
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {"classification": "blocked", "detail": "diagnostics polling timed out", "state": last_state}
        try:
            body = reader(url, min(remaining, 2.0))
            item = body.get("item", {}) if isinstance(body, dict) else {}
            last_state = str(item.get("state") or "unavailable")
            if last_state in {"healthy", "degraded"}:
                return {
                    "classification": "pass" if last_state == "healthy" else "fail",
                    "detail": "diagnostics available",
                    "state": last_state,
                }
        except (OSError, ValueError, urllib.error.URLError):
            last_state = "unavailable"
        if interval:
            time.sleep(min(interval, max(0, deadline - time.monotonic())))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="Host for local published endpoints")
    parser.add_argument("--ap-host", default="127.0.0.1")
    parser.add_argument("--hlab-host", help="HLAB listener host; defaults to --host")
    parser.add_argument("--management-port", type=int, default=10443)
    parser.add_argument("--orm-port", type=int, default=6600)
    parser.add_argument("--oru-port", type=int, default=6661)
    parser.add_argument("--hlab-port", type=int, default=6665)
    parser.add_argument("--ap-port", type=int, default=6671)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--diagnostics-url")
    parser.add_argument("--diagnostics-timeout", type=float, default=10.0)
    parser.add_argument("--fixture", type=Path, help="Explicit HL7 fixture to send to OIE port 6600")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    endpoints = {
        "oie-management": (args.host, args.management_port),
        "oie-orm-ingress": (args.host, args.orm_port),
        "oie-oru-ingress": (args.host, args.oru_port),
        "hlab-result-listener": (args.hlab_host or args.host, args.hlab_port),
        "ap-orm-listener": (args.ap_host, args.ap_port),
    }
    results: dict[str, Any] = {
        "tcp": {name: tcp_probe(host, port, args.timeout) for name, (host, port) in endpoints.items()}
    }
    if args.diagnostics_url:
        results["diagnostics"] = poll_diagnostics(args.diagnostics_url, args.diagnostics_timeout, 0.25)
    else:
        results["diagnostics"] = {"classification": "unavailable", "detail": "not configured"}
    if args.fixture:
        results["mllp"] = send_fixture(args.fixture, args.host, args.orm_port, args.timeout)
    else:
        results["mllp"] = {"classification": "unavailable", "detail": "fixture not provided"}
    classifications = [item["classification"] for item in results["tcp"].values()]
    if args.diagnostics_url:
        classifications.append(results["diagnostics"]["classification"])
    if args.fixture:
        classifications.append(results["mllp"]["classification"])
    results["classification"] = "fail" if "fail" in classifications else ("blocked" if "blocked" in classifications else ("unavailable" if "unavailable" in classifications else "pass"))
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0 if results["classification"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
