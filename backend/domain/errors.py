"""Typed application errors shared across backend boundaries."""

from __future__ import annotations

from typing import Any


class ValidationError(ValueError):
    """Raised when application input or configuration is invalid."""


class SimulatorValidationError(ValueError):
    """Raised when simulator workflow input is invalid."""


class LabOperationError(RuntimeError):
    """Raised when a lab lifecycle or smoke operation fails."""


class UpstreamFhirError(RuntimeError):
    """FHIR transport or upstream response failure."""

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        response_payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.response_payload = response_payload or {}
        self.attempt_recorded = False


class UpstreamDcm4cheeError(RuntimeError):
    """DICOMweb transport or upstream response failure."""

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        response_body: str = "",
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.response_body = response_body
