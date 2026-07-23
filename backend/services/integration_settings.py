"""Application-facing typed settings bootstrap, mutation, and effective reads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from backend.domain.integration_settings import (
    MEDPLUM_PROFILE_TYPE,
    SecretMutation,
    medplum_bootstrap_candidate,
    preserve_secret,
    remove_secret,
    replace_secret,
    validate_profile,
)
from backend.repositories.integration_settings import IntegrationSettingsRepository


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
    def __init__(self, repository: IntegrationSettingsRepository) -> None:
        self._repository = repository

    def bootstrap_medplum(self, configuration: Mapping[str, Any]) -> bool:
        profile = medplum_bootstrap_candidate(configuration)
        return self._repository.create_if_missing(
            profile,
            secrets={"clientSecret": str(configuration.get("MEDPLUM_CLIENT_SECRET", ""))},
            bootstrap_source="legacy-environment-and-inventory",
        )

    def get_public(self, profile_type: str) -> dict[str, Any]:
        return self._repository.get_public(profile_type)

    def get_effective(self, profile_type: str) -> Any:
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
        profile = validate_profile(profile_type, fields)
        mutations: dict[str, SecretMutation] = {
            "clientSecret": preserve_secret(),
        }
        for field, value in (secret_replacements or {}).items():
            mutations[field] = replace_secret(value)
        return self._repository.replace(
            profile, secret_mutations=mutations, actor=actor
        )

    def remove_secret(
        self,
        profile_type: str,
        field: str,
        *,
        actor: str = "local-operator",
    ) -> dict[str, Any]:
        private = self._repository.get_private(profile_type)
        profile = validate_profile(profile_type, private["fields"])
        return self._repository.replace(
            profile,
            secret_mutations={field: remove_secret()},
            actor=actor,
        )
