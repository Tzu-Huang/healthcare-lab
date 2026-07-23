"""Registry and aggregation service for bounded Settings readiness."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from backend.domain.settings_readiness import (
    ActivationImpact,
    DiagnosticAssessment,
    DiagnosticState,
    ReadinessAssessment,
    ReadinessRegistration,
    ReadinessState,
    project_diagnostic,
    project_section,
)


class SettingsReadinessRegistry:
    def __init__(self, registrations: Iterable[ReadinessRegistration] = ()):
        self._registrations: dict[str, ReadinessRegistration] = {}
        for registration in registrations:
            self.register(registration)

    def register(self, registration: ReadinessRegistration) -> None:
        if registration.integration_id in self._registrations:
            raise ValueError(
                f"Duplicate readiness registration: {registration.integration_id}"
            )
        self._registrations[registration.integration_id] = registration

    def registrations(self) -> tuple[ReadinessRegistration, ...]:
        return tuple(self._registrations.values())


class SettingsReadinessService:
    def __init__(self, registry: SettingsReadinessRegistry):
        self._registry = registry

    def get_readiness(self) -> dict[str, Any]:
        sections = []
        for registration in self._registry.registrations():
            try:
                assessment = registration.provider.assess()
                if not isinstance(assessment, ReadinessAssessment):
                    raise TypeError("Provider returned an unsupported assessment.")
            except Exception:
                # Provider failures stay local, value-free, and do not discard peers.
                assessment = ReadinessAssessment(
                    ReadinessState.DEGRADED, ActivationImpact.IMMEDIATE
                )
            sections.append(project_section(registration, assessment))

        complete = all(
            section["state"] == ReadinessState.READY.value
            if section["required"]
            else section["state"]
            in {ReadinessState.READY.value, ReadinessState.DISABLED.value}
            for section in sections
        )
        next_action = next(
            (
                {"sectionId": section["id"], "action": section["action"]}
                for section in sections
                if (
                    section["required"]
                    and section["state"] != ReadinessState.READY.value
                )
                or (
                    not section["required"]
                    and section["state"]
                    not in {
                        ReadinessState.READY.value,
                        ReadinessState.DISABLED.value,
                    }
                )
            ),
            None,
        )
        return {
            "complete": complete,
            "nextAction": next_action,
            "sections": sections,
        }

    def run_checks(self) -> dict[str, Any]:
        results = []
        for registration in self._registry.registrations():
            try:
                check = getattr(registration.provider, "check", None)
                if callable(check):
                    assessment = check()
                else:
                    readiness = registration.provider.assess()
                    state = (
                        DiagnosticState.DISABLED
                        if readiness.state is ReadinessState.DISABLED
                        else DiagnosticState.UNAVAILABLE
                    )
                    assessment = DiagnosticAssessment(state)
                if not isinstance(assessment, DiagnosticAssessment):
                    raise TypeError("Provider returned an unsupported diagnostic.")
            except Exception:
                assessment = DiagnosticAssessment(DiagnosticState.DEGRADED)
            results.append(project_diagnostic(registration, assessment))
        return {
            "summary": "Registered bounded checks completed.",
            "results": results,
        }
