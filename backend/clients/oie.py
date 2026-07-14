"""OIE MLLP transport operations."""

from __future__ import annotations

import socket


def send_hl7_mllp_message(
    message: str,
    *,
    host: str,
    port: int,
    timeout_seconds: float,
    framing: bool = True,
) -> str:
    outgoing = (
        b"\x0b" + message.encode("utf-8") + b"\x1c\x0d"
        if framing
        else message.encode("utf-8")
    )
    received = bytearray()
    with socket.create_connection((host, int(port)), timeout_seconds) as connection:
        connection.settimeout(timeout_seconds)
        connection.sendall(outgoing)
        while True:
            chunk = connection.recv(4096)
            if not chunk:
                break
            received.extend(chunk)
            if framing and b"\x1c\x0d" in received:
                break
    payload = bytes(received)
    if framing:
        if payload.startswith(b"\x0b"):
            payload = payload[1:]
        if payload.endswith(b"\x1c\x0d"):
            payload = payload[:-2]
    return payload.decode("utf-8", errors="replace")
