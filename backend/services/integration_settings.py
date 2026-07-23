"""Application-facing typed settings bootstrap, mutation, and effective reads."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Protocol

from backend.domain.integration_settings import (
    MEDPLUM_PROFILE_TYPE,
    PROFILE_SECRET_FIELDS,
    SecretMutation,
    SettingsValidationIssue,
    TypedSettingsValidationError,
    medplum_bootstrap_candidate,
    preserve_secret,
    remove_secret,
    replace_secret,
    validate_profile,
)
from backend.domain.errors import SimulatorValidationError
from backend.services.oie_settings import OieSettingsService

OIE_PROFILE_TYPE = "oie"


class IntegrationSettingsRepositoryPort(Protocol):
    def create_if_missing(self, profile, *, secrets, bootstrap_source, actor="startup-bootstrap") -> bool: ...
    def get_private(self, profile_type: str) -> dict[str, Any]: ...
    def replace(self, profile, *, secret_mutations, actor="local-operator") -> dict[str, Any]: ...


class OieSettingsAdapter:
    """Adapt the specialized OIE profile without replacing its persistence model."""

    def __init__(self, service: OieSettingsService, repository: Any) -> None:
        self._service = service
        self._repository = repository

    def get_public(self) -> dict[str, Any]:
        profile = self._service.get_profile()
        management = profile.get("managementApi", {})
        configured = bool(management.get("passwordConfigured"))
        return {
            "profileType": OIE_PROFILE_TYPE,
            "profileName": profile.get("profileName", "local-oie"),
            "schemaVersion": 1,
            "fields": profile,
            "secrets": {"managementApi.password": {"configured": configured}},
        }

    def get_effective(self) -> dict[str, Any]:
        return {
            "profileType": OIE_PROFILE_TYPE,
            "managementApi": dict(
                self._repository.get_management_api_configuration()
            ),
            "resultListener": dict(
                self._repository.get_result_listener_configuration()
            ),
            "managedChannels": self._service.get_profile().get(
                "managedChannels", []
            ),
        }

    def replace(
        self,
        fields: Mapping[str, Any],
        *,
        secret_replacements: Mapping[str, Any],
    ) -> dict[str, Any]:
        unknown_secrets = sorted(
            set(secret_replacements) - {"managementApi.password"}
        )
        if unknown_secrets:
            raise TypedSettingsValidationError(
                [
                    SettingsValidationIssue(
                        f"secrets.{field}",
                        "unknown_field",
                        "The secret field is not supported.",
                    )
                    for field in unknown_secrets
                ]
            )
        payload = dict(fields)
        management = dict(payload.get("managementApi") or {})
        replacement = secret_replacements.get("managementApi.password")
        if replacement is not None and str(replacement).strip():
            management["password"] = str(replacement)
        else:
            management.pop("password", None)
        payload["managementApi"] = management
        try:
            self._service.update_profile(payload)
        except SimulatorValidationError as exc:
            raise _typed_oie_validation_error(str(exc)) from exc
        return self.get_public()

    def remove_secret(self, field: str) -> dict[str, Any]:
        if field != "managementApi.password":
            raise TypedSettingsValidationError(
                [
                    SettingsValidationIssue(
                        f"secrets.{field}",
                        "unknown_field",
                        "The secret field is not supported.",
                    )
                ]
            )
        self._service.remove_management_api_password()
        return self.get_public()


def _typed_oie_validation_error(message: str) -> TypedSettingsValidationError:
    field = "fields"
    mappings = (
        ("baseUrl", "managementApi.baseUrl"),
        ("username", "managementApi.username"),
        ("password", "managementApi.password"),
        ("timeoutSeconds", "managementApi.timeoutSeconds"),
        ("tlsVerify", "managementApi.tlsVerify"),
        ("resultListener host", "resultListener.host"),
        ("resultListener port", "resultListener.port"),
        ("mllpFraming", "resultListener.mllpFraming"),
        ("autoStart", "resultListener.autoStart"),
        ("managedChannels", "managedChannels"),
        ("managementApi", "managementApi"),
    )
    channel_path = re.search(r"managedChannels\[\d+\](?:\.[A-Za-z]+)?", message)
    if channel_path:
        field = channel_path.group(0)
    else:
        for token, path in mappings:
            if token in message:
                field = path
                break
    return TypedSettingsValidationError(
        [
            SettingsValidationIssue(
                field,
                "invalid_value",
                "The field value is invalid.",
            )
        ]
    )


@dataclass(frozen=True, repr=False)
class MedplumEffectiveSettings:
    base_url: str
    client_id: str
    client_secret: str
    scope: str
    token_url: str
    auth_grace_seconds: int
    enabled: bool

    def __repr__(self) -> str:
        return (
            "MedplumEffectiveSettings("
            f"base_url={self.base_url!r}, client_id={self.client_id!r}, "
            f"client_secret_configured={bool(self.client_secret)!r}, "
            f"scope={self.scope!r}, token_url={self.token_url!r}, "
            f"auth_grace_seconds={self.auth_grace_seconds!r}, enabled={self.enabled!r})"
        )


class IntegrationSettingsService:
    def __init__(
        self,
        repository: IntegrationSettingsRepositoryPort,
        *,
        oie_adapter: OieSettingsAdapter | None = None,
    ) -> None:
        self._repository = repository
        self._oie = oie_adapter

    def bootstrap_medplum(self, configuration: Mapping[str, Any]) -> bool:
        profile = medplum_bootstrap_candidate(configuration)
        return self._repository.create_if_missing(
            profile,
            secrets={"clientSecret": str(configuration.get("MEDPLUM_CLIENT_SECRET", ""))},
            bootstrap_source="legacy-environment-and-inventory",
        )

    def get_public(self, profile_type: str) -> dict[str, Any]:
        if profile_type == OIE_PROFILE_TYPE and self._oie is not None:
            return self._oie.get_public()
        private = self._repository.get_private(profile_type)
        return {
            "profileType": private["profileType"],
            "profileName": private["profileName"],
            "schemaVersion": private["schemaVersion"],
            "fields": private["fields"],
            "secrets": {
                field: {"configured": bool(private["secrets"].get(field))}
                for field in sorted(PROFILE_SECRET_FIELDS[profile_type])
            },
        }

    def get_effective(self, profile_type: str) -> Any:
        if profile_type == OIE_PROFILE_TYPE and self._oie is not None:
            return self._oie.get_effective()
        if profile_type != MEDPLUM_PROFILE_TYPE:
            raise KeyError(profile_type)
        private = self._repository.get_private(profile_type)
        fields = private["fields"]
        return MedplumEffectiveSettings(
            base_url=str(fields["baseUrl"]),
            client_id=str(fields["clientId"]),
            client_secret=str(private["secrets"].get("clientSecret", "")),
            scope=str(fields["scope"]),
            token_url=str(fields["tokenUrl"]),
            auth_grace_seconds=int(fields["authGraceSeconds"]),
            enabled=bool(fields["enabled"]),
        )

    def replace(
        self,
        profile_type: str,
        fields: Mapping[str, Any],
        *,
        secret_replacements: Mapping[str, Any] | None = None,
        actor: str = "local-operator",
    ) -> dict[str, Any]:
        if profile_type == OIE_PROFILE_TYPE and self._oie is not None:
            return self._oie.replace(
                fields, secret_replacements=secret_replacements or {}
            )
        profile = validate_profile(profile_type, fields)
        mutations: dict[str, SecretMutation] = {
            "clientSecret": preserve_secret(),
        }
        for field, value in (secret_replacements or {}).items():
            mutations[field] = replace_secret(value)
        self._repository.replace(
            profile, secret_mutations=mutations, actor=actor
        )
        return self.get_public(profile_type)

    def remove_secret(
        self,
        profile_type: str,
        field: str,
        *,
        actor: str = "local-operator",
    ) -> dict[str, Any]:
        if profile_type == OIE_PROFILE_TYPE:
            if self._oie is None:
                raise KeyError(profile_type)
            return self._oie.remove_secret(field)
        private = self._repository.get_private(profile_type)
        profile = validate_profile(profile_type, private["fields"])
        self._repository.replace(
            profile,
            secret_mutations={field: remove_secret()},
            actor=actor,
        )
        return self.get_public(profile_type)
