"""Shared application timestamp factories."""

from __future__ import annotations

from datetime import datetime


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def hl7_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")
