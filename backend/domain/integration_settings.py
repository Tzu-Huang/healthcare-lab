"""Typed integration settings contracts and closed profile registrations."""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

MEDPLUM_PROFILE_TYPE = "medplum"
MEDPLUM_PROFILE_NAME = "local-medplum"
MEDPLUM_DEFAULT_WEB_UI_URL = "http://127.0.0.1:3000"
MEDPLUM_DEFAULT_TIMEOUT_SECONDS = 10
MEDPLUM_MAX_TIMEOUT_SECONDS = 300
MEDPLUM_FIELDS = frozenset(
    {
        "baseUrl",
        "webUiUrl",
        "clientId",
        "scope",
        "tokenUrl",
        "authGraceSeconds",
        "timeoutSeconds",
        "enabled",
    }
)
MEDPLUM_SECRET_FIELDS = frozenset({"clientSecret"})
GDT_BRIDGE_PROFILE_TYPE = "gdt-bridge"
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


@dataclass(frozen=True)
class SettingsValidationIssue:
    field: str
    code: str
    reason: str


class TypedSettingsValidationError(ValueError):
    """Stable value-free settings validation failure."""

    def __init__(self, issues: list[SettingsValidationIssue]):
        self.issues = tuple(issues)
        super().__init__("Integration settings validation failed.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": "settings_validation_failed",
            "fields": [
                {"field": issue.field, "code": issue.code, "reason": issue.reason}
                for issue in self.issues
            ],
        }


class SecretAction(str, Enum):
    PRESERVE = "preserve"
    REPLACE = "replace"
    REMOVE = "remove"


@dataclass(frozen=True, repr=False)
class SecretMutation:
    action: SecretAction
    value: str = ""

    def __post_init__(self) -> None:
        if self.action is SecretAction.REPLACE and not self.value:
            raise ValueError("Replacement secret must be non-blank.")
        if self.action is not SecretAction.REPLACE and self.value:
            raise ValueError("Only replacement mutations carry a value.")

    def __repr__(self) -> str:
        return f"SecretMutation(action={self.action.value!r}, configured={bool(self.value)!r})"


def preserve_secret() -> SecretMutation:
    return SecretMutation(SecretAction.PRESERVE)


def replace_secret(value: Any) -> SecretMutation:
    text = "" if value is None else str(value)
    return preserve_secret() if not text.strip() else SecretMutation(SecretAction.REPLACE, text)


def remove_secret() -> SecretMutation:
    return SecretMutation(SecretAction.REMOVE)


@dataclass(frozen=True)
class TypedProfile:
    profile_type: str
    profile_name: str
    schema_version: int
    fields: dict[str, Any]


def _url_issue(field: str, value: Any, *, required: bool) -> SettingsValidationIssue | None:
    normalized = str(value or "").strip()
    if not normalized and not required:
        return None
    parsed = urllib.parse.urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return SettingsValidationIssue(
            field, "invalid_url", f"{field} must be an absolute HTTP or HTTPS URL."
        )
    return None


def validate_medplum_profile(payload: Mapping[str, Any]) -> TypedProfile:
    unknown = sorted(set(payload) - MEDPLUM_FIELDS)
    issues = [
        SettingsValidationIssue(field, "unknown_field", f"{field} is not supported.")
        for field in unknown
    ]
    missing = sorted(MEDPLUM_FIELDS - set(payload))
    issues.extend(
        SettingsValidationIssue(field, "required", f"{field} is required.")
        for field in missing
    )
    base_url_issue = _url_issue("baseUrl", payload.get("baseUrl"), required=True)
    web_ui_url_issue = _url_issue("webUiUrl", payload.get("webUiUrl"), required=True)
    token_url_issue = _url_issue("tokenUrl", payload.get("tokenUrl"), required=False)
    issues.extend(
        issue for issue in (base_url_issue, web_ui_url_issue, token_url_issue) if issue
    )

    raw_auth_grace = payload.get("authGraceSeconds")
    if (
        not isinstance(raw_auth_grace, int)
        or isinstance(raw_auth_grace, bool)
        or raw_auth_grace <= 0
    ):
        auth_grace = 0
        issues.append(
            SettingsValidationIssue(
                "authGraceSeconds",
                "invalid_positive_integer",
                "authGraceSeconds must be a positive integer.",
            )
        )
    else:
        auth_grace = raw_auth_grace
    raw_timeout = payload.get("timeoutSeconds")
    if (
        not isinstance(raw_timeout, int)
        or isinstance(raw_timeout, bool)
        or not 1 <= raw_timeout <= MEDPLUM_MAX_TIMEOUT_SECONDS
    ):
        timeout_seconds = 0
        issues.append(
            SettingsValidationIssue(
                "timeoutSeconds",
                "invalid_bounded_integer",
                (
                    "timeoutSeconds must be an integer between "
                    f"1 and {MEDPLUM_MAX_TIMEOUT_SECONDS}."
                ),
            )
        )
    else:
        timeout_seconds = raw_timeout
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        issues.append(
            SettingsValidationIssue("enabled", "invalid_boolean", "enabled must be a boolean.")
        )
    for field in ("clientId", "scope"):
        if field in payload and not isinstance(payload[field], str):
            issues.append(
                SettingsValidationIssue(field, "invalid_string", f"{field} must be a string.")
            )
    if issues:
        raise TypedSettingsValidationError(issues)
    return TypedProfile(
        profile_type=MEDPLUM_PROFILE_TYPE,
        profile_name=MEDPLUM_PROFILE_NAME,
        schema_version=1,
        fields={
            "baseUrl": str(payload["baseUrl"]).strip().rstrip("/"),
            "webUiUrl": str(payload["webUiUrl"]).strip().rstrip("/"),
            "clientId": str(payload["clientId"]).strip(),
            "scope": str(payload["scope"]).strip(),
            "tokenUrl": str(payload["tokenUrl"]).strip().rstrip("/"),
            "authGraceSeconds": auth_grace,
            "timeoutSeconds": timeout_seconds,
            "enabled": enabled,
        },
    )


PROFILE_VALIDATORS = {MEDPLUM_PROFILE_TYPE: validate_medplum_profile}
PROFILE_FIELDS = {
    MEDPLUM_PROFILE_TYPE: MEDPLUM_FIELDS,
    GDT_BRIDGE_PROFILE_TYPE: GDT_BRIDGE_FIELDS,
}
PROFILE_SECRET_FIELDS = {
    MEDPLUM_PROFILE_TYPE: MEDPLUM_SECRET_FIELDS,
    GDT_BRIDGE_PROFILE_TYPE: frozenset(),
}


def validate_profile(profile_type: str, payload: Mapping[str, Any]) -> TypedProfile:
    if profile_type == GDT_BRIDGE_PROFILE_TYPE:
        # Lazy import keeps the feature profile dependent on the shared
        # validation primitives without creating an import cycle.
        from backend.domain.gdt_bridge_profile import validate_gdt_bridge_profile

        return validate_gdt_bridge_profile(payload)
    try:
        validator = PROFILE_VALIDATORS[profile_type]
    except KeyError as exc:
        raise TypedSettingsValidationError(
            [
                SettingsValidationIssue(
                    "profileType", "unknown_profile", "The profile type is not supported."
                )
            ]
        ) from exc
    return validator(payload)


def medplum_bootstrap_candidate(configuration: Mapping[str, Any]) -> TypedProfile:
    return validate_medplum_profile(
        {
            "baseUrl": configuration.get(
                "MEDPLUM_FHIR_BASE_URL", "http://medplum:8103/fhir/R4"
            ),
            "webUiUrl": configuration.get(
                "MEDPLUM_WEB_UI_URL", MEDPLUM_DEFAULT_WEB_UI_URL
            ),
            "clientId": configuration.get("MEDPLUM_CLIENT_ID", ""),
            "scope": configuration.get("MEDPLUM_SCOPE", ""),
            "tokenUrl": configuration.get("MEDPLUM_TOKEN_URL", ""),
            "authGraceSeconds": configuration.get("MEDPLUM_AUTH_GRACE_SECONDS", 300),
            "timeoutSeconds": configuration.get(
                "MEDPLUM_TIMEOUT_SECONDS", MEDPLUM_DEFAULT_TIMEOUT_SECONDS
            ),
            "enabled": True,
        }
    )
