"""Canonical runtime access to persisted Medplum settings and in-memory auth."""

from __future__ import annotations

from typing import Any, Protocol

from backend.clients.medplum import MedplumAuthManager
from backend.services.medplum_diagnostics import MedplumDiagnosticService


class EffectiveSettingsReader(Protocol):
    def get_effective(self, profile_type: str) -> Any: ...


class MedplumRuntimeProvider:
    def __init__(self, settings: EffectiveSettingsReader) -> None:
        self._settings = settings
        self._fingerprint: tuple[Any, ...] | None = None
        self._auth_manager: MedplumAuthManager | None = None

    def settings(self) -> Any:
        return self._settings.get_effective("medplum")

    def base_url(self) -> str:
        current = self.settings()
        return current.base_url if current.enabled else ""

    def auth_manager(self) -> MedplumAuthManager:
        current = self.settings()
        fingerprint = (
            current.enabled,
            current.base_url,
            current.client_id,
            current.client_secret,
            current.scope,
            current.token_url,
            current.auth_grace_seconds,
            current.timeout_seconds,
        )
        if self._auth_manager is None or fingerprint != self._fingerprint:
            self._auth_manager = MedplumAuthManager(
                client_id=current.client_id if current.enabled else "",
                client_secret=current.client_secret if current.enabled else "",
                scope=current.scope,
                token_url=current.token_url,
                refresh_grace_seconds=current.auth_grace_seconds,
                timeout_seconds=current.timeout_seconds,
            )
            self._fingerprint = fingerprint
        return self._auth_manager

    def diagnose(self) -> dict[str, Any]:
        current = self.settings()
        return MedplumDiagnosticService(
            enabled=current.enabled,
            base_url=current.base_url,
            auth_manager=self.auth_manager(),
            timeout_seconds=current.timeout_seconds,
        ).diagnose()
