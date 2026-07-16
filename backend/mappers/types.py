"""Structural row types shared by pure presentation mappers."""

from __future__ import annotations

from typing import Any, Protocol


class RowMapping(Protocol):
    """Minimum persistence-neutral interface consumed by row mappers."""

    def __getitem__(self, key: str) -> Any: ...
