"""Persistence-neutral record types used by domain projections."""

from __future__ import annotations

from typing import Any, Protocol


class IndexedRecord(Protocol):
    """A mapping-like persistence record addressable by string column names."""

    def __getitem__(self, key: str) -> Any: ...
