"""OIE settings use cases independent of Flask request state."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from backend.clients.oie_management import OieManagementClient
from backend.domain.oie_management import OieManagementConfig, OieTlsMode


class OieSettingsRepositoryPort(Protocol):
    def get(self) -> dict[str, Any]: ...

    def update(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def get_result_listener_configuration(self) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class OieSettingsUpdateResult:
    profile: dict[str, Any]
    runtime_reload_required: bool


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
    def __init__(
        self,
        repository: OieSettingsRepositoryPort,
        *,
        management_client_factory: Callable[
            [OieManagementConfigurationSource], OieManagementClient
        ] = create_oie_management_client,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._management_client_factory = management_client_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get_profile(self) -> dict[str, Any]:
        return self._repository.get()

    def update_profile(self, payload: dict[str, Any]) -> OieSettingsUpdateResult:
        before = self._repository.get().get("resultListener")
        profile = self._repository.update(payload)
        return OieSettingsUpdateResult(
            profile=profile,
            runtime_reload_required=before != profile.get("resultListener"),
        )

    def test_connection(self) -> dict[str, str]:
        """Test persisted OIE credentials and return only presentation-safe fields.

        Stable ``OieManagementError`` failures intentionally pass through for the
        API boundary to classify. The low-level client owns all upstream response
        redaction, while this projection selects only the values the Settings UI
        is permitted to display.
        """
        client = self._management_client_factory(self._repository)
        try:
            client.login()
            version = client.require_supported_version()
            user = client.current_user()
            return {
                "status": "connected",
                "version": version.version,
                "currentUser": str(user.values["username"]),
                "tlsMode": client.config.tls_mode.value,
                "testedAt": self._tested_at(),
            }
        finally:
            client.close()

    def _tested_at(self) -> str:
        tested_at = self._clock()
        if tested_at.tzinfo is None:
            tested_at = tested_at.replace(tzinfo=timezone.utc)
        return tested_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
