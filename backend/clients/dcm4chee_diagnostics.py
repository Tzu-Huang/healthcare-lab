"""Bounded HTTP and TCP transports for dcm4chee diagnostics."""

from __future__ import annotations

import socket
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from backend.clients.dcm4chee import open_secured

MAX_QIDO_RESPONSE_BYTES = 65_536


def http_get(
    url: str, timeout: float, profile: dict[str, Any] | None = None
) -> Mapping[str, Any]:
    request = Request(
        url,
        headers={"Accept": "application/dicom+json, application/json"},
        method="GET",
    )
    try:
        response_context = (
            open_secured(request, profile, timeout=timeout)
            if profile is not None
            else urlopen(request, timeout=timeout)
        )
        with response_context as response:
            return {
                "status": response.status,
                "body": response.read(MAX_QIDO_RESPONSE_BYTES + 1),
            }
    except HTTPError as exc:
        return {"status": exc.code, "body": b""}


def tcp_connect(host: str, port: int, timeout: float) -> Any:
    return socket.create_connection((host, port), timeout=timeout)
