"""Bounded, value-free diagnostics for a configured Medplum connection."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.clients.medplum import (
    MedplumAuthManager,
    normalize_fhir_base_url,
    request_fhir_json,
)


FhirRequest = Callable[..., tuple[int, dict[str, Any]]]


class MedplumDiagnosticService:
    """Run ordered probes while exposing only allowlisted diagnostic values."""

    def __init__(
        self,
        *,
        enabled: bool,
        base_url: str,
        auth_manager: MedplumAuthManager,
        timeout_seconds: int,
        fhir_request: FhirRequest = request_fhir_json,
    ) -> None:
        self._enabled = bool(enabled)
        self._base_url = base_url
        self._auth_manager = auth_manager
        self._timeout_seconds = max(1, int(timeout_seconds))
        self._fhir_request = fhir_request

    def diagnose(self) -> dict[str, Any]:
        if not self._enabled:
            stages = [
                self._stage(name, "disabled", "disabled", "Medplum is disabled.")
                for name in ("metadata", "oauth", "authenticated-read")
            ]
            return {"state": "disabled", "stages": stages}

        try:
            base_url = normalize_fhir_base_url(self._base_url)
        except Exception:
            stages = [
                self._stage(name, "failed", "invalid-configuration", "Medplum configuration is invalid.")
                for name in ("metadata", "oauth", "authenticated-read")
            ]
            return {"state": "failed", "stages": stages}

        metadata = self._probe_metadata(base_url)
        oauth = self._probe_oauth(base_url)
        authenticated = self._probe_authenticated_read(base_url, oauth)
        stages = [metadata, oauth, authenticated]
        state = "healthy" if all(item["state"] == "passed" for item in stages) else "degraded"
        return {"state": state, "stages": stages}

    def _probe_metadata(self, base_url: str) -> dict[str, str]:
        try:
            status, _ = self._fhir_request(
                f"{base_url}/metadata",
                "",
                timeout_seconds=self._timeout_seconds,
            )
            if 200 <= status < 300:
                return self._stage("metadata", "passed", "reachable", "FHIR metadata is reachable.")
            return self._stage("metadata", "failed", "http-error", "FHIR metadata request failed.")
        except Exception:
            return self._stage("metadata", "failed", "connection-failure", "FHIR metadata request failed.")

    def _probe_oauth(self, base_url: str) -> dict[str, str]:
        if not self._auth_manager.is_configured():
            return self._stage(
                "oauth", "failed", "not-configured", "Medplum OAuth credentials are not configured."
            )
        try:
            self._auth_manager.get_access_token(base_url, force_refresh=True)
            return self._stage("oauth", "passed", "authorized", "OAuth token acquisition succeeded.")
        except Exception:
            return self._stage("oauth", "failed", "authorization-failure", "OAuth token acquisition failed.")

    def _probe_authenticated_read(
        self, base_url: str, oauth: dict[str, str]
    ) -> dict[str, str]:
        if oauth["state"] != "passed":
            return self._stage(
                "authenticated-read",
                "skipped",
                "oauth-unavailable",
                "Authenticated FHIR read was not attempted.",
            )
        try:
            token = self._auth_manager.get_access_token(base_url)
            status, _ = self._fhir_request(
                f"{base_url}/Patient?_count=1",
                token,
                timeout_seconds=self._timeout_seconds,
            )
            if 200 <= status < 300:
                return self._stage(
                    "authenticated-read", "passed", "readable", "Authenticated FHIR read succeeded."
                )
            return self._stage(
                "authenticated-read", "failed", "http-error", "Authenticated FHIR read failed."
            )
        except Exception:
            return self._stage(
                "authenticated-read", "failed", "read-failure", "Authenticated FHIR read failed."
            )

    @staticmethod
    def _stage(name: str, state: str, category: str, summary: str) -> dict[str, str]:
        return {
            "stage": name,
            "state": state,
            "category": category,
            "summary": summary[:160],
        }
