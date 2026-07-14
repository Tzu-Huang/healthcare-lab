"""Medplum authentication and FHIR HTTP transport."""

from __future__ import annotations

import base64
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from backend.config import MEDPLUM_DEFAULT_AUTH_GRACE_SECONDS
from backend.domain.errors import UpstreamFhirError, ValidationError


def normalize_fhir_base_url(value: str) -> str:
    base_url = value.strip().rstrip("/")
    if not base_url:
        raise ValidationError("Medplum FHIR base URL is required.")
    if not base_url.startswith(("http://", "https://")):
        raise ValidationError("Medplum FHIR base URL must start with http:// or https://.")
    return base_url


def derive_medplum_token_url(base_url: str, override: str = "") -> str:
    if override.strip():
        return normalize_fhir_base_url(override)
    parsed = urllib.parse.urlparse(normalize_fhir_base_url(base_url))
    if not parsed.scheme or not parsed.netloc:
        raise ValidationError("Medplum FHIR base URL must include scheme and host.")
    return f"{parsed.scheme}://{parsed.netloc}/oauth2/token"


@dataclass(frozen=True)
class MedplumAccessToken:
    access_token: str
    expires_at: float


class MedplumAuthManager:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        scope: str = "",
        token_url: str = "",
        refresh_grace_seconds: int = MEDPLUM_DEFAULT_AUTH_GRACE_SECONDS,
    ) -> None:
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.scope = scope.strip()
        self.token_url = token_url.strip()
        self.refresh_grace_seconds = max(0, int(refresh_grace_seconds))
        self._cache: dict[str, MedplumAccessToken] = {}
        self._lock = threading.Lock()

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def status(self, base_url: str = "") -> dict[str, Any]:
        configured = self.is_configured()
        token_endpoint = ""
        if configured and base_url.strip():
            try:
                token_endpoint = derive_medplum_token_url(base_url, self.token_url)
            except ValidationError:
                token_endpoint = ""
        return {
            "configured": configured,
            "clientIdSuffix": self.client_id[-4:] if configured and len(self.client_id) >= 4 else self.client_id,
            "tokenEndpoint": token_endpoint,
            "scope": self.scope,
        }

    def invalidate(self, base_url: str) -> None:
        token_url = derive_medplum_token_url(base_url, self.token_url)
        with self._lock:
            self._cache.pop(token_url, None)

    def get_access_token(self, base_url: str, *, force_refresh: bool = False) -> str:
        if not self.is_configured():
            raise ValidationError(
                "Medplum client credentials are not configured. "
                "Set MEDPLUM_CLIENT_ID and MEDPLUM_CLIENT_SECRET on the Flask server."
            )
        token_url = derive_medplum_token_url(base_url, self.token_url)
        now = time.time()
        with self._lock:
            cached = self._cache.get(token_url)
            if cached and not force_refresh and (cached.expires_at - self.refresh_grace_seconds) > now:
                return cached.access_token
        token = self._request_new_token(token_url)
        with self._lock:
            self._cache[token_url] = token
        return token.access_token

    def _request_new_token(self, token_url: str) -> MedplumAccessToken:
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        if self.scope:
            payload["scope"] = self.scope
        request_payload = urllib.parse.urlencode(payload).encode("utf-8")
        basic_auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode("utf-8")).decode("ascii")
        api_request = urllib.request.Request(
            token_url,
            data=request_payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {basic_auth}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(api_request, timeout=15) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise UpstreamFhirError(f"Medplum token request returned HTTP {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise UpstreamFhirError(f"Medplum token request failed: {exc.reason}") from exc
        try:
            parsed_body = json.loads(response_body) if response_body else {}
        except json.JSONDecodeError as exc:
            raise UpstreamFhirError("Medplum token request returned a non-JSON response.") from exc
        access_token = str(parsed_body.get("access_token", "")).strip()
        token_type = str(parsed_body.get("token_type", "Bearer")).strip()
        expires_in = int(parsed_body.get("expires_in", 3600) or 3600)
        if not access_token:
            raise UpstreamFhirError("Medplum token request did not return access_token.")
        if token_type.lower() != "bearer":
            raise UpstreamFhirError(f"Medplum token request returned unsupported token type: {token_type}")
        return MedplumAccessToken(access_token=access_token, expires_at=time.time() + max(1, expires_in))


def request_fhir_raw(
    url: str,
    token: str,
    *,
    method: str,
    body: bytes,
    content_type: str,
    auth_manager: MedplumAuthManager | None = None,
    base_url: str = "",
) -> tuple[int, dict[str, Any], dict[str, str]]:
    def perform_request(access_token: str) -> tuple[int, dict[str, Any], dict[str, str]]:
        headers = {"Accept": "application/fhir+json, application/json", "Content-Type": content_type}
        if access_token.strip():
            headers["Authorization"] = f"Bearer {access_token.strip()}"
        api_request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(api_request, timeout=30) as response:
                response_body = response.read().decode("utf-8", errors="replace")
                status_code = response.status
                response_headers = dict(response.headers.items())
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise UpstreamFhirError(f"Medplum returned HTTP {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise UpstreamFhirError(f"Medplum request failed: {exc.reason}") from exc
        try:
            parsed_body = json.loads(response_body) if response_body else {}
        except json.JSONDecodeError:
            parsed_body = {"raw": response_body}
        return status_code, parsed_body, response_headers

    access_token = auth_manager.get_access_token(base_url or url) if auth_manager is not None else token.strip()
    try:
        return perform_request(access_token)
    except UpstreamFhirError as exc:
        if auth_manager is None or "Medplum returned HTTP 401:" not in str(exc):
            raise
        auth_manager.invalidate(base_url or url)
        return perform_request(auth_manager.get_access_token(base_url or url, force_refresh=True))


def request_fhir_json(
    url: str,
    token: str,
    method: str = "GET",
    body: bytes | None = None,
    content_type: str | None = None,
    *,
    auth_manager: MedplumAuthManager | None = None,
    base_url: str = "",
) -> tuple[int, dict[str, Any]]:
    def perform_request(access_token: str) -> tuple[int, dict[str, Any]]:
        headers = {"Accept": "application/fhir+json, application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        if access_token.strip():
            headers["Authorization"] = f"Bearer {access_token.strip()}"
        api_request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(api_request, timeout=15) as response:
                response_body = response.read().decode("utf-8")
                status_code = response.status
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            try:
                error_payload = json.loads(error_body) if error_body else {}
            except json.JSONDecodeError:
                error_payload = {"raw": error_body}
            raise UpstreamFhirError(
                f"Medplum returned HTTP {exc.code}: {error_body}",
                http_status=exc.code,
                response_payload=error_payload,
            ) from exc
        except urllib.error.URLError as exc:
            raise UpstreamFhirError(f"Medplum request failed: {exc.reason}") from exc
        try:
            parsed_body = json.loads(response_body) if response_body else {}
        except json.JSONDecodeError:
            parsed_body = {"raw": response_body}
        return status_code, parsed_body

    access_token = auth_manager.get_access_token(base_url or url) if auth_manager is not None else token.strip()
    try:
        return perform_request(access_token)
    except UpstreamFhirError as exc:
        if auth_manager is None or "Medplum returned HTTP 401:" not in str(exc):
            raise
        auth_manager.invalidate(base_url or url)
        return perform_request(auth_manager.get_access_token(base_url or url, force_refresh=True))
