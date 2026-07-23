"""Application adapters for the Settings readiness registry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from backend.domain.settings_readiness import (
    ActivationImpact,
    ReadinessAssessment,
    ReadinessRegistration,
    ReadinessState,
)
from backend.services.settings_readiness import (
    SettingsReadinessRegistry,
    SettingsReadinessService,
)


class IntegrationSettingsReader(Protocol):
    def get_public(self, profile_type: str) -> dict[str, Any]: ...


class _StaticProvider:
    def __init__(self, state: ReadinessState):
        self._state = state

    def assess(self) -> ReadinessAssessment:
        return ReadinessAssessment(self._state)


class _MedplumProvider:
    def __init__(self, settings: IntegrationSettingsReader):
        self._settings = settings

    def assess(self) -> ReadinessAssessment:
        fields = self._settings.get_public("medplum")["fields"]
        if not fields.get("enabled") or not fields.get("baseUrl"):
            return ReadinessAssessment(ReadinessState.NEEDS_SETUP)
        return ReadinessAssessment(ReadinessState.READY)


class _OieProvider:
    def __init__(
        self,
        settings: IntegrationSettingsReader,
        *,
        listener_status: Callable[[], dict[str, Any]],
        diagnostics: Callable[[], dict[str, Any]],
    ):
        self._settings = settings
        self._listener_status = listener_status
        self._diagnostics = diagnostics

    def assess(self) -> ReadinessAssessment:
        public = self._settings.get_public("oie")
        fields = public["fields"]
        management = fields.get("managementApi", {})
        secret = public.get("secrets", {}).get("managementApi.password", {})
        if (
            not management.get("baseUrl")
            or not management.get("username")
            or not secret.get("configured")
        ):
            return ReadinessAssessment(ReadinessState.NEEDS_SETUP)
        desired = fields.get("resultListener", {})
        runtime = self._listener_status()
        if runtime.get("running") and (
            str(runtime.get("host")) != str(desired.get("host"))
            or int(runtime.get("port", 0)) != int(desired.get("port", 0))
            or runtime.get("mllpFraming") != desired.get("mllpFraming")
        ):
            return ReadinessAssessment(
                ReadinessState.RESTART_REQUIRED,
                ActivationImpact.APPLICATION_RESTART,
            )
        return ReadinessAssessment(ReadinessState.READY)

    def check(self) -> ReadinessAssessment:
        current = self.assess()
        if current.state is not ReadinessState.READY:
            return current
        report = self._diagnostics()
        if report.get("state") == "healthy":
            return current
        return ReadinessAssessment(ReadinessState.DEGRADED)


def create_settings_readiness_service(
    settings: IntegrationSettingsReader,
    *,
    listener_status: Callable[[], dict[str, Any]],
    oie_diagnostics: Callable[[], dict[str, Any]],
) -> SettingsReadinessService:
    registry = SettingsReadinessRegistry(
        (
            ReadinessRegistration(
                "medplum", "Medplum", True, _MedplumProvider(settings)
            ),
            ReadinessRegistration(
                "oie",
                "OIE",
                True,
                _OieProvider(
                    settings,
                    listener_status=listener_status,
                    diagnostics=oie_diagnostics,
                ),
            ),
            ReadinessRegistration(
                "gdt-bridge",
                "GDT Bridge",
                False,
                _StaticProvider(ReadinessState.DISABLED),
            ),
            ReadinessRegistration(
                "dcm4chee",
                "dcm4chee",
                False,
                _StaticProvider(ReadinessState.DISABLED),
            ),
            ReadinessRegistration(
                "external-devices",
                "AP / External Devices",
                False,
                _StaticProvider(ReadinessState.DISABLED),
            ),
            ReadinessRegistration(
                "deployment",
                "Deployment & Diagnostics",
                True,
                _StaticProvider(ReadinessState.READY),
            ),
        )
    )
    return SettingsReadinessService(registry)
