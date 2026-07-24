"""Secret-safe helpers for the ZAC-78 disposable release verification.

The live matrix can feed text captured from APIs, logs, wrappers, and evidence
files through :func:`assert_bounded_evidence` before retaining it.  The helper
intentionally uses synthetic values that are invalid for real integrations.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from backend.repositories.database import SQLiteDatabase
from backend.repositories.schema import APPLICATION_MIGRATIONS

LEGACY_SCHEMA_VERSION = 8
LEGACY_SCHEMA_PROVENANCE = (
    "APPLICATION_MIGRATIONS[0:8], immediately before migration 9 "
    "'add-typed-integration-settings'"
)

SYNTHETIC_CANARIES = {
    "secret": "ZAC78-SECRET-DO-NOT-RETAIN",
    "authorization": "Bearer ZAC78-AUTH-DO-NOT-RETAIN",
    "phi": "ZAC78-PATIENT-DO-NOT-RETAIN",
    "raw_message": "MSH|^~\\&|ZAC78-RAW-DO-NOT-RETAIN",
    "fhir_body": '{"resourceType":"Patient","id":"ZAC78-FHIR-DO-NOT-RETAIN"}',
    "upstream_body": "ZAC78-UPSTREAM-BODY-DO-NOT-RETAIN",
}


def create_canonical_legacy_database(path: Path) -> None:
    """Create the canonical pre-unified-Settings schema without product data."""
    SQLiteDatabase(
        path, migrations=APPLICATION_MIGRATIONS[:LEGACY_SCHEMA_VERSION]
    ).initialize()


def assert_bounded_evidence(value: Any, *, canaries: Mapping[str, str] = SYNTHETIC_CANARIES) -> str:
    """Serialize evidence and reject any exact sensitive synthetic canary."""
    rendered = (
        value
        if isinstance(value, str)
        else json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    )
    def contains(candidate: Any, canary: str) -> bool:
        if isinstance(candidate, Mapping):
            return any(
                contains(key, canary) or contains(item, canary)
                for key, item in candidate.items()
            )
        if isinstance(candidate, (list, tuple, set)):
            return any(contains(item, canary) for item in candidate)
        return canary in str(candidate)

    leaked = [
        category
        for category, canary in canaries.items()
        if canary in rendered or contains(value, canary)
    ]
    if leaked:
        raise AssertionError(
            "Unsafe ZAC-78 evidence contains synthetic canary categories: "
            + ", ".join(sorted(leaked))
        )
    return rendered
