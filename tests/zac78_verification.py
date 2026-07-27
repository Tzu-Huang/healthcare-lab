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

RECOVERY_ACTIONS = {
    ("medplum", "invalid-configuration"): "Review the saved FHIR and OAuth fields, then run Save-and-test again.",
    ("medplum", "connection-failure"): "Restore FHIR endpoint reachability, then run Save-and-test again.",
    ("medplum", "authorization-failure"): "Replace the Medplum client secret, then run Save-and-test again.",
    ("medplum", "oauth-unavailable"): "Resolve the OAuth failure before retrying the authenticated read.",
    ("gdt-bridge", "missing"): "Provision the documented GDT bridge directories, then rerun diagnostics.",
    ("gdt-bridge", "write-failed"): "Restore write permission on the diagnostic directory, then rerun diagnostics.",
    ("gdt-bridge", "delete-failed"): "Restore delete permission on the diagnostic directory, then rerun diagnostics.",
    ("dcm4chee", "unreachable"): "Restore the configured endpoint or transport, then rerun dcm4chee diagnostics.",
    ("dcm4chee", "timed-out"): "Restore endpoint responsiveness, then rerun dcm4chee diagnostics.",
    ("dcm4chee", "invalid-response"): "Correct the DICOMweb endpoint response, then rerun dcm4chee diagnostics.",
    ("ap-device", "invalid_ae_title"): "Enter a printable DICOM AE title of at most 16 characters, then save again.",
    ("ap-device", "unreachable"): "Restore the configured AP transport, then rerun device diagnostics.",
    ("oie", "probe-failure"): "Review the affected OIE diagnostic guidance, then rerun diagnostics.",
    ("oie", "connection"): "Restore OIE Management API connectivity, then rerun diagnostics.",
    ("oie", "port-conflict"): "Correct endpoint ownership, then rerun OIE diagnostics.",
    ("oie", "not-deployed"): "Apply or redeploy the managed OIE channel, then rerun diagnostics.",
    ("oie", "destination-errors"): "Restore the destination and retry retained messages, then rerun diagnostics.",
}


def create_canonical_legacy_database(path: Path) -> None:
    """Create the canonical pre-unified-Settings schema without product data."""
    SQLiteDatabase(
        path, migrations=APPLICATION_MIGRATIONS[:LEGACY_SCHEMA_VERSION]
    ).initialize()


def project_bounded_failure(
    integration: str, layer: str, category: str
) -> dict[str, str]:
    """Project a closed layer/category/recovery triple for retained evidence."""
    recovery = RECOVERY_ACTIONS.get((integration, category))
    if recovery is None:
        raise ValueError(
            f"Unsupported ZAC-78 failure projection: {integration}/{category}"
        )
    return {
        "integration": integration,
        "layer": layer,
        "category": category,
        "recovery": recovery,
    }


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
