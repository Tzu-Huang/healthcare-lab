"""Closed, value-free contracts for the Settings readiness workspace."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class ReadinessState(str, Enum):
    READY = "ready"
    NEEDS_SETUP = "needs-setup"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    RESTART_REQUIRED = "restart-required"


class ActivationImpact(str, Enum):
    IMMEDIATE = "immediate"
    APPLICATION_RESTART = "application-restart"
    CONTAINER_RECREATION = "container-recreation"


class DiagnosticState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


_SUMMARIES = {
    ReadinessState.READY: "Configured and available.",
    ReadinessState.NEEDS_SETUP: "Setup is required.",
    ReadinessState.DEGRADED: "Configured, but a bounded check needs attention.",
    ReadinessState.DISABLED: "Optional integration is disabled.",
    ReadinessState.RESTART_REQUIRED: "Saved changes are waiting for activation.",
}

_ACTIONS = {
    ReadinessState.READY: None,
    ReadinessState.NEEDS_SETUP: "configure",
    ReadinessState.DEGRADED: "review-diagnostics",
    ReadinessState.DISABLED: None,
    ReadinessState.RESTART_REQUIRED: "review-activation",
}


@dataclass(frozen=True)
class ReadinessAssessment:
    """Provider result that cannot carry configuration values or arbitrary text."""

    state: ReadinessState
    activation_impact: ActivationImpact = ActivationImpact.IMMEDIATE


@dataclass(frozen=True)
class DiagnosticAssessment:
    state: DiagnosticState
    checks: tuple[dict[str, str], ...] = ()


class ReadinessProvider(Protocol):
    def assess(self) -> ReadinessAssessment: ...


@dataclass(frozen=True)
class ReadinessRegistration:
    integration_id: str
    label: str
    required: bool
    provider: ReadinessProvider

    def __post_init__(self) -> None:
        if not self.integration_id or not self.label:
            raise ValueError("Readiness registration metadata must be non-blank.")
        if self.integration_id.lower() == "openemr":
            raise ValueError("OpenEMR is not a supported Settings registration.")


def project_section(
    registration: ReadinessRegistration, assessment: ReadinessAssessment
) -> dict[str, Any]:
    """Return the stable public projection; provider-owned values are excluded."""

    return {
        "id": registration.integration_id,
        "label": registration.label,
        "required": registration.required,
        "state": assessment.state.value,
        "summary": _SUMMARIES[assessment.state],
        "activationImpact": assessment.activation_impact.value,
        "action": _ACTIONS[assessment.state],
    }


def project_diagnostic(
    registration: ReadinessRegistration, assessment: DiagnosticAssessment
) -> dict[str, Any]:
    summaries = {
        DiagnosticState.HEALTHY: "Bounded checks passed.",
        DiagnosticState.DEGRADED: "A bounded check needs attention.",
        DiagnosticState.UNAVAILABLE: "No bounded diagnostic is available yet.",
        DiagnosticState.DISABLED: "Diagnostics are disabled with this optional integration.",
    }
    result = {
        "id": registration.integration_id,
        "label": registration.label,
        "state": assessment.state.value,
        "summary": summaries[assessment.state],
    }
    if assessment.checks:
        result["checks"] = [dict(item) for item in assessment.checks]
    return result
