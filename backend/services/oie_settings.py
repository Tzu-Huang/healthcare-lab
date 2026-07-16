"""OIE settings use cases independent of Flask request state."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol

from backend.clients.oie_management import OieManagementClient
from backend.domain.oie_management import OieManagementConfig, OieTlsMode


class OieSettingsRepositoryPort(Protocol):
    def get(self) -> dict[str, Any]: ...

    def update(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class OieManagementConfigurationSource(Protocol):
    def get_management_api_configuration(self) -> Mapping[str, Any]: ...


def create_oie_management_client(
    source: OieManagementConfigurationSource,
    *,
    client_factory: Callable[[OieManagementConfig], OieManagementClient] = OieManagementClient,
) -> OieManagementClient:
    """Adapt private persisted settings to the persistence-neutral client contract."""
    values = source.get_management_api_configuration()
    timeout = float(values["timeout_seconds"])
    base_url = str(values["base_url"])
    tls_mode = OieTlsMode.VERIFIED
    if base_url.lower().startswith("https://") and not values["tls_verify"]:
        tls_mode = OieTlsMode.LOCAL_SELF_SIGNED
    return client_factory(OieManagementConfig(
        base_url=base_url,
        username=str(values["username"]),
        password=str(values["password"]),
        tls_mode=tls_mode,
        connect_timeout=timeout,
        read_timeout=timeout,
    ))


class OieSettingsService:
    def __init__(self, repository: OieSettingsRepositoryPort) -> None:
        self._repository = repository

    def get_profile(self) -> dict[str, Any]:
        return self._repository.get()

    def update_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._repository.update(payload)
