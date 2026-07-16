"""Authenticated, cookie-aware OIE 4.5.2 Management API boundary."""

from __future__ import annotations

import http.cookiejar
import json
import logging
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from backend.domain.oie_management import (
    OieErrorCategory,
    OieManagementConfig,
    OieManagementError,
    OieResult,
    OieTlsMode,
    OieVersionSupport,
    classify_oie_version,
)


LOGGER = logging.getLogger(__name__)
REQUESTED_WITH = "XMLHttpRequest"
MAX_RESPONSE_BYTES = 1_048_576
MAX_PUBLIC_STRING = 512
SENSITIVE_KEY_PARTS = (
    "authorization", "cookie", "credential", "password", "secret", "session", "token",
)


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes = b""
    headers: Mapping[str, str] | None = None


class OieTransport(Protocol):
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        connect_timeout: float,
        read_timeout: float,
    ) -> HttpResponse: ...

    def clear(self) -> None: ...

    def close(self) -> None: ...


class UrllibOieTransport:
    """Per-client urllib opener and cookie jar; never shared globally."""

    def __init__(self, tls_mode: OieTlsMode) -> None:
        self._cookies = http.cookiejar.CookieJar()
        context = (
            ssl.create_default_context()
            if tls_mode is OieTlsMode.VERIFIED
            else ssl._create_unverified_context()  # explicitly selected local-lab policy
        )
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookies),
            urllib.request.HTTPSHandler(context=context),
        )

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        connect_timeout: float,
        read_timeout: float,
    ) -> HttpResponse:
        request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
        with self._opener.open(request, timeout=connect_timeout) as response:
            self._set_read_timeout(response, read_timeout)
            payload = response.read(MAX_RESPONSE_BYTES + 1)
            if len(payload) > MAX_RESPONSE_BYTES:
                raise OieManagementError(
                    OieErrorCategory.UNEXPECTED_RESPONSE, "OIE response exceeded the client limit."
                )
            return HttpResponse(response.status, payload, dict(response.headers.items()))

    @staticmethod
    def _set_read_timeout(response: Any, timeout: float) -> None:
        raw = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
        if raw is not None:
            raw.settimeout(timeout)

    def clear(self) -> None:
        self._cookies.clear()

    def close(self) -> None:
        self.clear()


class OieManagementClient:
    def __init__(self, config: OieManagementConfig, transport: OieTransport | None = None) -> None:
        self.config = config
        self._transport = transport or UrllibOieTransport(config.tls_mode)
        self._authenticated = False
        self._closed = False

    def __repr__(self) -> str:
        return (
            f"OieManagementClient(base_url={self.config.base_url!r}, "
            f"username={self.config.username!r}, authenticated={self._authenticated!r})"
        )

    def __enter__(self) -> "OieManagementClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def login(self) -> OieResult:
        body = urllib.parse.urlencode(
            {"username": self.config.username, "password": self.config.password}
        ).encode("utf-8")
        response = self._send(
            "POST", "/users/_login", body=body,
            content_type="application/x-www-form-urlencoded", require_auth=False,
        )
        self._authenticated = True
        if response.body:
            self._json_mapping(response)
        return OieResult("login")

    def logout(self) -> OieResult:
        try:
            if self._authenticated:
                self._send("POST", "/users/_logout")
            return OieResult("logout")
        finally:
            self._authenticated = False
            self._transport.clear()

    def close(self) -> None:
        if self._closed:
            return
        try:
            self.logout()
        except OieManagementError:
            LOGGER.debug("Remote OIE logout failed during cleanup.")
        finally:
            self._transport.close()
            self._closed = True

    def current_user(self) -> OieResult:
        return self._mapping_result("current-user", self._send("GET", "/users/current"))

    def system_info(self) -> OieResult:
        return self._mapping_result("system-info", self._send("GET", "/system/info"))

    def server_version(self) -> OieVersionSupport:
        response = self._send("GET", "/server/version")
        return classify_oie_version(response.body.decode("utf-8", errors="replace"))

    def require_supported_version(self) -> OieVersionSupport:
        support = self.server_version()
        if not support.supported:
            raise OieManagementError(
                OieErrorCategory.UNSUPPORTED_VERSION,
                f"OIE version {support.version!r} is unsupported; expected 4.5.2.",
            )
        return support

    def list_channels(self) -> OieResult:
        return self._sequence_result("list-channels", self._send("GET", "/channels"))

    def get_channel(self, channel_id: str) -> OieResult:
        channel_id = self._identifier(channel_id)
        return self._mapping_result(
            "get-channel", self._send("GET", f"/channels/{self._quote(channel_id)}"), channel_id
        )

    def channel_status(self, channel_id: str) -> OieResult:
        channel_id = self._identifier(channel_id)
        return self._mapping_result(
            "channel-status",
            self._send("GET", f"/channels/{self._quote(channel_id)}/status"),
            channel_id,
        )

    def ports_in_use(self) -> OieResult:
        return self._sequence_result("ports-in-use", self._send("GET", "/channels/portsInUse"))

    def create_channel(self, channel: Mapping[str, Any]) -> OieResult:
        response = self._send_json("POST", "/channels/", channel)
        self._require_boolean_success(response)
        return OieResult("create-channel", identifier=str(channel.get("id", "")))

    def update_channel(
        self, channel_id: str, channel: Mapping[str, Any], *, override: bool = False
    ) -> OieResult:
        channel_id = self._identifier(channel_id)
        query = urllib.parse.urlencode({"override": str(override).lower()})
        response = self._send_json(
            "PUT", f"/channels/{self._quote(channel_id)}?{query}", channel
        )
        self._require_boolean_success(response)
        return OieResult("update-channel", identifier=channel_id)

    def delete_channel(self, channel_id: str) -> OieResult:
        channel_id = self._identifier(channel_id)
        self._send("DELETE", f"/channels/{self._quote(channel_id)}")
        return OieResult("delete-channel", identifier=channel_id)

    def deploy(self, channel_id: str) -> OieResult:
        return self._primitive("deploy", channel_id, "_deploy")

    def redeploy(self, channel_id: str) -> OieResult:
        return self._primitive("redeploy", channel_id, "_deploy")

    def undeploy(self, channel_id: str) -> OieResult:
        return self._primitive("undeploy", channel_id, "_undeploy")

    def _primitive(self, operation: str, channel_id: str, action: str) -> OieResult:
        channel_id = self._identifier(channel_id)
        self._send("POST", f"/channels/{self._quote(channel_id)}/{action}")
        return OieResult(operation, identifier=channel_id)

    def _send_json(self, method: str, path: str, value: Mapping[str, Any]) -> HttpResponse:
        if not isinstance(value, Mapping):
            raise OieManagementError(OieErrorCategory.VALIDATION, "Channel payload must be a mapping.")
        try:
            body = json.dumps(value, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError):
            raise OieManagementError(
                OieErrorCategory.VALIDATION, "Channel payload must be JSON serializable."
            ) from None
        return self._send(
            method, path, body=body,
            content_type="application/json",
        )

    def _send(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        content_type: str = "",
        require_auth: bool = True,
    ) -> HttpResponse:
        if self._closed:
            raise OieManagementError(OieErrorCategory.UNAUTHENTICATED, "OIE client is closed.")
        if require_auth and not self._authenticated:
            raise OieManagementError(
                OieErrorCategory.UNAUTHENTICATED, "OIE operation requires an authenticated session."
            )
        headers = {"Accept": "application/json", "X-Requested-With": REQUESTED_WITH}
        if content_type:
            headers["Content-Type"] = content_type
        try:
            response = self._transport.request(
                method=method,
                url=f"{self.config.base_url}/api{path}",
                headers=headers,
                body=body,
                connect_timeout=self.config.connect_timeout,
                read_timeout=self.config.read_timeout,
            )
        except OieManagementError:
            raise
        except urllib.error.HTTPError as exc:
            raise self._http_error(exc.code, method) from None
        except (ssl.SSLError, ssl.CertificateError) as exc:
            raise OieManagementError(OieErrorCategory.TLS, "OIE TLS verification failed.") from None
        except (TimeoutError, socket.timeout):
            raise OieManagementError(OieErrorCategory.TIMEOUT, "OIE request timed out.") from None
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (ssl.SSLError, ssl.CertificateError)):
                category, detail = OieErrorCategory.TLS, "OIE TLS verification failed."
            elif isinstance(exc.reason, (TimeoutError, socket.timeout)):
                category, detail = OieErrorCategory.TIMEOUT, "OIE request timed out."
            else:
                category, detail = OieErrorCategory.CONNECTION, "OIE connection failed."
            raise OieManagementError(category, detail) from None
        except (ConnectionError, OSError):
            raise OieManagementError(OieErrorCategory.CONNECTION, "OIE connection failed.") from None
        if not 200 <= response.status < 300:
            raise self._http_error(response.status, method)
        return response

    @staticmethod
    def _http_error(status: int, method: str) -> OieManagementError:
        if status == 401:
            category = OieErrorCategory.AUTHENTICATION
        elif status == 403:
            category = OieErrorCategory.PERMISSION
        elif status in {409, 412} and method == "PUT":
            category = OieErrorCategory.REVISION_CONFLICT
        elif status in {400, 404, 405, 422}:
            category = OieErrorCategory.VALIDATION
        elif status >= 500:
            category = OieErrorCategory.SERVER
        else:
            category = OieErrorCategory.UNEXPECTED_RESPONSE
        return OieManagementError(category, f"OIE returned HTTP {status}.", http_status=status)

    @staticmethod
    def _json(response: HttpResponse) -> Any:
        if not response.body:
            raise OieManagementError(
                OieErrorCategory.UNEXPECTED_RESPONSE, "OIE response body was empty."
            )
        try:
            return json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OieManagementError(
                OieErrorCategory.UNEXPECTED_RESPONSE, "OIE returned malformed JSON."
            ) from None

    def _json_mapping(self, response: HttpResponse, *, allow_empty: bool = False) -> Mapping[str, Any]:
        if allow_empty and not response.body:
            return {}
        value = self._json(response)
        if not isinstance(value, dict):
            raise OieManagementError(
                OieErrorCategory.UNEXPECTED_RESPONSE, "OIE response was not an object."
            )
        return self._redact_mapping(value)

    def _mapping_result(self, operation: str, response: HttpResponse, identifier: str = "") -> OieResult:
        value = self._json_mapping(response)
        result_id = identifier or str(value.get("id", ""))
        revision_value = value.get("revision")
        revision = revision_value if isinstance(revision_value, int) else None
        status = str(value.get("status", ""))
        return OieResult(operation, result_id, revision, status, value)

    def _sequence_result(self, operation: str, response: HttpResponse) -> OieResult:
        value = self._json(response)
        if not isinstance(value, list):
            raise OieManagementError(
                OieErrorCategory.UNEXPECTED_RESPONSE, "OIE response was not a list."
            )
        return OieResult(operation, values={"items": tuple(self._redact_value(item) for item in value)})

    @classmethod
    def _redact_mapping(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            str(key): "[REDACTED]"
            if any(part in str(key).lower() for part in SENSITIVE_KEY_PARTS)
            else cls._redact_value(item)
            for key, item in value.items()
        }

    @classmethod
    def _redact_value(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return cls._redact_mapping(value)
        if isinstance(value, list):
            return tuple(cls._redact_value(item) for item in value)
        if isinstance(value, str) and len(value) > MAX_PUBLIC_STRING:
            return f"{value[:MAX_PUBLIC_STRING]}...[TRUNCATED]"
        return value

    @staticmethod
    def _require_boolean_success(response: HttpResponse) -> None:
        text = response.body.decode("utf-8", errors="replace").strip().lower()
        if text in {"true", '"true"'}:
            return
        try:
            if json.loads(text) is True:
                return
        except (json.JSONDecodeError, ValueError):
            pass
        raise OieManagementError(
            OieErrorCategory.UNEXPECTED_RESPONSE, "OIE mutation did not confirm success."
        )

    @staticmethod
    def _identifier(value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise OieManagementError(OieErrorCategory.VALIDATION, "Channel identifier is required.")
        return normalized

    @staticmethod
    def _quote(value: str) -> str:
        return urllib.parse.quote(value, safe="")
