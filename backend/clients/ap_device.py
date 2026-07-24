"""Bounded transport probes for AP/external-device diagnostics."""

from __future__ import annotations

import socket


def probe_tcp(host: str, port: int, timeout_seconds: float) -> bool:
    with socket.create_connection((host, port), timeout=timeout_seconds):
        return True
