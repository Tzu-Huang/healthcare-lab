"""Application adapters for the Settings readiness registry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from backend.domain.settings_readiness import (
    ActivationImpact,
    DiagnosticAssessment,
    DiagnosticState,
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
    def has_operator_configuration(self, profile_type: str) -> bool: ...


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
        if (
            not fields.get("enabled")
            or not fields.get("baseUrl")
            or not self._settings.has_operator_configuration("medplum")
        ):
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
        if desired.get("autoStart") and not runtime.get("running"):
            return ReadinessAssessment(ReadinessState.NEEDS_SETUP)
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

    def check(self) -> DiagnosticAssessment:
        current = self.assess()
        if current.state is not ReadinessState.READY:
            return DiagnosticAssessment(DiagnosticState.DEGRADED)
        report = self._diagnostics()
        if report.get("state") == "healthy":
            return DiagnosticAssessment(DiagnosticState.HEALTHY)
        return DiagnosticAssessment(DiagnosticState.DEGRADED)


class _GdtBridgeProvider:
    def __init__(
        self,
        settings: IntegrationSettingsReader,
        *,
        watcher_status: Callable[[], dict[str, Any]],
        activation_status: Callable[[], dict[str, str]],
        diagnostics: Callable[[], dict[str, Any]],
        check_diagnostics: Callable[[], dict[str, Any]],
    ) -> None:
        self._settings = settings
        self._watcher_status = watcher_status
        self._activation_status = activation_status
        self._diagnostics = diagnostics
        self._check_diagnostics = check_diagnostics

    def assess(self) -> ReadinessAssessment:
        fields = self._settings.get_public("gdt-bridge")["fields"]
        if not fields.get("enabled"):
            return ReadinessAssessment(ReadinessState.DISABLED)
        activation = self._activation_status()
        if activation.get("state") == "restart-required":
            impact = (
                ActivationImpact.CONTAINER_RECREATION
                if activation.get("activation") == "container-recreation"
                else ActivationImpact.APPLICATION_RESTART
            )
            return ReadinessAssessment(ReadinessState.RESTART_REQUIRED, impact)
        report = self._diagnostics()
        if report.get("state") != "healthy":
            return ReadinessAssessment(ReadinessState.DEGRADED)
        if not self._watcher_status().get("running"):
            return ReadinessAssessment(ReadinessState.DEGRADED)
        return ReadinessAssessment(ReadinessState.READY)

    def check(self) -> DiagnosticAssessment:
        readiness = self.assess()
        if readiness.state is ReadinessState.DISABLED:
            return DiagnosticAssessment(DiagnosticState.DISABLED)
        report = self._check_diagnostics()
        watcher_running = report.get("watcher", {}).get("state") == "running"
        checks = [
            {
                "role": str(item.get("role", "unknown")),
                "state": str(item.get("state", "failed")),
                "code": str(item.get("code", "unavailable")),
            }
            for item in report.get("checks", [])
        ]
        checks.append(
            {
                "role": "watcher",
                "state": "passed" if watcher_running else "failed",
                "code": "running" if watcher_running else "stopped",
            }
        )
        return DiagnosticAssessment(
            DiagnosticState.HEALTHY
            if report.get("state") == "healthy" and watcher_running
            else DiagnosticState.DEGRADED,
            tuple(checks),
        )


class _Dcm4cheeProvider:
    def __init__(
        self,
        settings: IntegrationSettingsReader,
        diagnostics: Callable[[], dict[str, Any]],
    ) -> None:
        self._settings = settings
        self._diagnostics = diagnostics
        self._latest_diagnostic: DiagnosticAssessment | None = None

    def assess(self) -> ReadinessAssessment:
        fields = self._settings.get_public("dcm4chee")["fields"]
        if not fields.get("enabled"):
            return ReadinessAssessment(ReadinessState.DISABLED)
        if (
            self._latest_diagnostic is not None
            and self._latest_diagnostic.state is DiagnosticState.DEGRADED
        ):
            return ReadinessAssessment(ReadinessState.DEGRADED)
        return ReadinessAssessment(ReadinessState.READY)

    def check(self) -> DiagnosticAssessment:
        fields = self._settings.get_public("dcm4chee")["fields"]
        if not fields.get("enabled"):
            self._latest_diagnostic = DiagnosticAssessment(DiagnosticState.DISABLED)
            return self._latest_diagnostic
        report = self._diagnostics()
        checks = tuple(
            {
                "role": str(item.get("role", "unknown")),
                "state": str(item.get("state", "failed")),
                "code": str(item.get("code", "unavailable")),
            }
            for item in report.get("checks", [])
        )
        self._latest_diagnostic = DiagnosticAssessment(
            DiagnosticState.HEALTHY
            if report.get("state") == "healthy"
            else DiagnosticState.DEGRADED,
            checks,
        )
        return self._latest_diagnostic


class _APDeviceProvider:
    def __init__(
        self,
        devices,
        *,
        environment: str,
        oie_desired: Callable[[], dict[str, Any]],
    ) -> None:
        self._devices = devices
        self._environment = environment
        self._oie_desired = oie_desired
        self._latest_diagnostic: DiagnosticAssessment | None = None

    def assess(self) -> ReadinessAssessment:
        profiles = self._devices.list(self._environment)
        if not profiles or not any(item.get("enabled") for item in profiles):
            return ReadinessAssessment(ReadinessState.DISABLED)
        effective = self._devices.effective(self._environment)
        if effective is None:
            return ReadinessAssessment(ReadinessState.NEEDS_SETUP)
        hl7 = effective.get("hl7", {})
        if hl7.get("enabled"):
            mappings = self._oie_desired().get("managedChannels", [])
            orm = next(
                (
                    item
                    for item in mappings
                    if item.get("logicalType") == "hlab-orm-to-ap"
                ),
                {},
            )
            if (
                str(orm.get("destinationHost")) != str(hl7.get("host"))
                or int(orm.get("destinationPort") or 0) != int(hl7.get("port") or 0)
            ):
                return ReadinessAssessment(ReadinessState.APPLY_REQUIRED)
        if (
            self._latest_diagnostic is not None
            and self._latest_diagnostic.state is DiagnosticState.DEGRADED
        ):
            return ReadinessAssessment(ReadinessState.DEGRADED)
        return ReadinessAssessment(ReadinessState.READY)

    def check(self) -> DiagnosticAssessment:
        effective = self._devices.effective(self._environment)
        if effective is None:
            state = (
                DiagnosticState.DISABLED
                if self.assess().state is ReadinessState.DISABLED
                else DiagnosticState.DEGRADED
            )
            self._latest_diagnostic = DiagnosticAssessment(state)
            return self._latest_diagnostic
        report = self._devices.diagnose(str(effective["id"]))
        checks = tuple(
            {
                "role": str(item.get("id", "unknown")),
                "state": str(item.get("state", "unavailable")),
                "code": str(item.get("code", "unavailable")),
            }
            for item in report.get("checks", [])
        )
        self._latest_diagnostic = DiagnosticAssessment(
            DiagnosticState.HEALTHY
            if report.get("state") == "healthy"
            else DiagnosticState.DEGRADED,
            checks,
        )
        return self._latest_diagnostic


def create_settings_readiness_service(
    settings: IntegrationSettingsReader,
    *,
    listener_status: Callable[[], dict[str, Any]],
    oie_diagnostics: Callable[[], dict[str, Any]],
    gdt_watcher_status: Callable[[], dict[str, Any]] | None = None,
    gdt_activation_status: Callable[[], dict[str, str]] | None = None,
    gdt_diagnostics: Callable[[], dict[str, Any]] | None = None,
    gdt_check_diagnostics: Callable[[], dict[str, Any]] | None = None,
    dcm4chee_diagnostics: Callable[[], dict[str, Any]] | None = None,
    ap_devices=None,
    ap_environment: str = "lab",
    oie_desired: Callable[[], dict[str, Any]] | None = None,
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
                _GdtBridgeProvider(
                    settings,
                    watcher_status=gdt_watcher_status or (lambda: {"running": False}),
                    activation_status=gdt_activation_status
                    or (lambda: {"state": "effective", "activation": "immediate"}),
                    diagnostics=gdt_diagnostics
                    or (lambda: {"state": "unavailable", "checks": []}),
                    check_diagnostics=gdt_check_diagnostics
                    or (lambda: {"state": "unavailable", "checks": []}),
                ),
            ),
            ReadinessRegistration(
                "dcm4chee",
                "dcm4chee",
                False,
                _Dcm4cheeProvider(
                    settings,
                    dcm4chee_diagnostics
                    or (lambda: {"state": "degraded", "checks": []}),
                ),
            ),
            ReadinessRegistration(
                "external-devices",
                "AP / External Devices",
                False,
                _APDeviceProvider(
                    ap_devices,
                    environment=ap_environment,
                    oie_desired=oie_desired or (lambda: {"managedChannels": []}),
                )
                if ap_devices is not None
                else _StaticProvider(ReadinessState.DISABLED),
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
