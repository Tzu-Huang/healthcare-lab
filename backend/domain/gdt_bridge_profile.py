"""Typed, value-safe contract for the persisted GDT Bridge runtime profile."""

from __future__ import annotations

import re
from pathlib import PurePath
from typing import Any, Mapping

from backend.domain.integration_settings import (
    SettingsValidationIssue,
    TypedProfile,
    TypedSettingsValidationError,
)

GDT_BRIDGE_PROFILE_TYPE = "gdt-bridge"
GDT_BRIDGE_PROFILE_NAME = "local-gdt-bridge"
GDT_BRIDGE_SCHEMA_VERSION = 1
GDT_BRIDGE_APPLICATION_PATH = "/data/gdt-bridge"
GDT_BRIDGE_FILENAME_PROFILES = frozenset({"permissive", "gdt21", "gdt35"})
GDT_BRIDGE_IMPORT_SUCCESS_MODES = frozenset({"archive", "delete"})
GDT_BRIDGE_FIELDS = frozenset(
    {
        "enabled",
        "applicationPath",
        "receiverId",
        "senderId",
        "filenameProfile",
        "importSuccessMode",
        "pollSeconds",
        "stableSeconds",
    }
)
GDT_BRIDGE_SECRET_FIELDS = frozenset()
GDT_BRIDGE_DEFAULT_FIELDS: dict[str, Any] = {
    "enabled": True,
    "applicationPath": GDT_BRIDGE_APPLICATION_PATH,
    "receiverId": "",
    "senderId": "",
    "filenameProfile": "permissive",
    "importSuccessMode": "archive",
    "pollSeconds": 2.0,
    "stableSeconds": 1.0,
}

_IDENTITY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{0,32}$")


def _issue(field: str, code: str, reason: str) -> SettingsValidationIssue:
    return SettingsValidationIssue(field, code, reason)


def _bounded_number(
    payload: Mapping[str, Any],
    field: str,
    *,
    minimum: float,
    maximum: float,
    issues: list[SettingsValidationIssue],
) -> float:
    value = payload.get(field)
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not minimum <= float(value) <= maximum
    ):
        issues.append(
            _issue(
                field,
                "invalid_bounded_number",
                f"{field} must be a number between {minimum:g} and {maximum:g}.",
            )
        )
        return minimum
    return float(value)


def validate_gdt_bridge_profile(payload: Mapping[str, Any]) -> TypedProfile:
    """Validate a complete public profile and return its canonical projection."""
    issues = [
        _issue(field, "unknown_field", f"{field} is not supported.")
        for field in sorted(set(payload) - GDT_BRIDGE_FIELDS)
    ]
    issues.extend(
        _issue(field, "required", f"{field} is required.")
        for field in sorted(GDT_BRIDGE_FIELDS - set(payload))
    )

    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        issues.append(_issue("enabled", "invalid_boolean", "enabled must be a boolean."))

    application_path = payload.get("applicationPath")
    if not isinstance(application_path, str) or not application_path.strip():
        issues.append(
            _issue(
                "applicationPath",
                "invalid_absolute_path",
                "applicationPath must be a non-empty absolute path.",
            )
        )
        normalized_path = ""
    else:
        normalized_path = application_path.strip().replace("\\", "/").rstrip("/") or "/"
        if not (
            normalized_path.startswith("/")
            or re.match(r"^[A-Za-z]:/", normalized_path)
        ) or ".." in PurePath(normalized_path).parts:
            issues.append(
                _issue(
                    "applicationPath",
                    "invalid_absolute_path",
                    "applicationPath must be an absolute path without parent traversal.",
                )
            )

    identities: dict[str, str] = {}
    for field in ("receiverId", "senderId"):
        value = payload.get(field)
        if not isinstance(value, str) or not _IDENTITY_PATTERN.fullmatch(value.strip()):
            issues.append(
                _issue(
                    field,
                    "invalid_identity",
                    f"{field} must contain at most 32 letters, digits, hyphens, or underscores.",
                )
            )
            identities[field] = ""
        else:
            identities[field] = value.strip()

    filename_profile = payload.get("filenameProfile")
    if filename_profile not in GDT_BRIDGE_FILENAME_PROFILES:
        issues.append(
            _issue(
                "filenameProfile",
                "invalid_choice",
                "filenameProfile must be permissive, gdt21, or gdt35.",
            )
        )
    import_success_mode = payload.get("importSuccessMode")
    if import_success_mode not in GDT_BRIDGE_IMPORT_SUCCESS_MODES:
        issues.append(
            _issue(
                "importSuccessMode",
                "invalid_choice",
                "importSuccessMode must be archive or delete.",
            )
        )
    if filename_profile != "permissive":
        for field in ("receiverId", "senderId"):
            if not identities[field]:
                issues.append(
                    _issue(
                        field,
                        "required_for_filename_profile",
                        f"{field} is required for a strict filename profile.",
                    )
                )

    poll_seconds = _bounded_number(
        payload, "pollSeconds", minimum=0.25, maximum=300, issues=issues
    )
    stable_seconds = _bounded_number(
        payload, "stableSeconds", minimum=0, maximum=300, issues=issues
    )
    if issues:
        raise TypedSettingsValidationError(issues)

    return TypedProfile(
        profile_type=GDT_BRIDGE_PROFILE_TYPE,
        profile_name=GDT_BRIDGE_PROFILE_NAME,
        schema_version=GDT_BRIDGE_SCHEMA_VERSION,
        fields={
            "enabled": enabled,
            "applicationPath": normalized_path,
            **identities,
            "filenameProfile": filename_profile,
            "importSuccessMode": import_success_mode,
            "pollSeconds": poll_seconds,
            "stableSeconds": stable_seconds,
        },
    )


def gdt_bridge_bootstrap_candidate(configuration: Mapping[str, Any]) -> TypedProfile:
    """Build the one-time persisted candidate from legacy runtime configuration."""
    return validate_gdt_bridge_profile(
        {
            "enabled": configuration.get("GDT_BRIDGE_ENABLED", True),
            "applicationPath": configuration.get(
                "GDT_BRIDGE_PATH", GDT_BRIDGE_APPLICATION_PATH
            ),
            "receiverId": configuration.get("GDT_BRIDGE_RECEIVER_ID", ""),
            "senderId": configuration.get("GDT_BRIDGE_SENDER_ID", ""),
            "filenameProfile": configuration.get(
                "GDT_BRIDGE_FILENAME_PROFILE", "permissive"
            ),
            "importSuccessMode": configuration.get(
                "GDT_BRIDGE_IMPORT_SUCCESS_MODE", "archive"
            ),
            "pollSeconds": configuration.get("GDT_BRIDGE_WATCH_POLL_SECONDS", 2),
            "stableSeconds": configuration.get("GDT_BRIDGE_STABLE_SECONDS", 1),
        }
    )
