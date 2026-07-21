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
    OieChannelDocument,
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
        if tls_mode is OieTlsMode.VERIFIED:
            context = ssl.create_default_context()
        elif tls_mode is OieTlsMode.LOCAL_SELF_SIGNED:
            context = ssl._create_unverified_context()  # explicitly selected local-lab policy
        else:
            raise OieManagementError(
                OieErrorCategory.VALIDATION, "Unknown OIE TLS mode; refusing insecure fallback."
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
        self._version_support: OieVersionSupport | None = None

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
        try:
            status = str(self._json_mapping(response).get("status", "")).strip().upper()
        except OieManagementError:
            self._authenticated = False
            self._version_support = None
            self._transport.clear()
            raise
        if status not in {"SUCCESS", "SUCCESS_GRACE_PERIOD"}:
            self._authenticated = False
            self._transport.clear()
            if status == "FAIL_VERSION_MISMATCH":
                category = OieErrorCategory.UNSUPPORTED_VERSION
                detail = "OIE rejected login because the client version is incompatible."
            elif status in {"FAIL", "FAIL_EXPIRED", "FAIL_LOCKED_OUT"}:
                category = OieErrorCategory.AUTHENTICATION
                detail = "OIE rejected the configured credentials."
            else:
                category = OieErrorCategory.UNEXPECTED_RESPONSE
                detail = "OIE login returned an unknown status."
            raise OieManagementError(category, detail)
        self._authenticated = True
        self._version_support = None
        return OieResult("login")

    def logout(self) -> OieResult:
        try:
            if self._authenticated:
                self._send("POST", "/users/_logout")
            return OieResult("logout")
        finally:
            self._authenticated = False
            self._version_support = None
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
        value = self._json_mapping(self._send("GET", "/users/current"))
        self._require_fields(value, "current user", {"id": (int, str), "username": str})
        return self._mapping_value_result("current-user", value)

    def system_info(self) -> OieResult:
        value = self._json_mapping(self._send("GET", "/system/info"))
        self._require_fields(value, "system information", {"jvmVersion": str, "osName": str, "dbName": str})
        return self._mapping_value_result("system-info", value)

    def server_version(self) -> OieVersionSupport:
        response = self._send("GET", "/server/version")
        return classify_oie_version(response.body.decode("utf-8", errors="replace"))

    def require_supported_version(self) -> OieVersionSupport:
        support = self._version_support or self.server_version()
        if not support.supported:
            raise OieManagementError(
                OieErrorCategory.UNSUPPORTED_VERSION,
                f"OIE version {support.version!r} is unsupported; expected 4.5.2.",
            )
        self._version_support = support
        return support

    def list_channels(self) -> OieResult:
        return self._sequence_result(
            "list-channels", self._send("GET", "/channels"),
            required={"id": str, "revision": int},
        )

    def get_channel(self, channel_id: str) -> OieResult:
        channel_id = self._identifier(channel_id)
        value = self._json_mapping(self._send("GET", f"/channels/{self._quote(channel_id)}"))
        self._require_fields(value, "channel", {"id": str, "revision": int})
        return self._mapping_value_result("get-channel", value, channel_id)

    def get_channel_complete(self, channel_id: str) -> OieChannelDocument:
        """Return complete Channel XML through a payload-hiding internal contract."""
        channel_id = self._identifier(channel_id)
        value = self._json(self._send("GET", f"/channels/{self._quote(channel_id)}"))
        if not isinstance(value, Mapping):
            raise OieManagementError(
                OieErrorCategory.UNEXPECTED_RESPONSE, "OIE Channel response was not an object."
            )
        self._require_fields(value, "channel", {"id": str, "revision": int})
        payload = next(
            (value.get(key) for key in ("payload", "xml", "channelXml")
             if isinstance(value.get(key), str) and value.get(key).strip()),
            None,
        )
        if payload is None:
            raise OieManagementError(
                OieErrorCategory.UNEXPECTED_RESPONSE,
                "OIE Channel response did not contain complete XML.",
            )
        return OieChannelDocument(
            identifier=str(value["id"]), name=str(value.get("name", "")),
            revision=int(value["revision"]), payload=payload,
            status=str(value.get("status", "")),
        )

    def channel_status(self, channel_id: str) -> OieResult:
        channel_id = self._identifier(channel_id)
        value = self._json_mapping(
            self._send("GET", f"/channels/{self._quote(channel_id)}/status")
        )
        self._require_fields(value, "channel status", {"channelId": str, "state": str})
        return OieResult("channel-status", channel_id, status=str(value["state"]), values=value)

    def destination_statistics(self, channel_id: str) -> OieResult:
        """Return bounded destination totals, explicitly marking unsupported APIs.

        OIE distributions differ in whether the Channel statistics resource is
        enabled. A missing resource is therefore a supported diagnostic outcome,
        not a zero-message result.
        """
        channel_id = self._identifier(channel_id)
        try:
            response = self._send(
                "GET", f"/channels/{self._quote(channel_id)}/statistics"
            )
        except OieManagementError as exc:
            if exc.http_status in {400, 404, 405}:
                return OieResult(
                    "destination-statistics", channel_id, status="unsupported",
                    values={"availability": "unsupported"},
                )
            raise
        value = self._json(response)
        normalized = self._normalize_destination_statistics(value)
        return OieResult(
            "destination-statistics", channel_id, status="available", values=normalized
        )

    def ports_in_use(self) -> OieResult:
        return self._sequence_result(
            "ports-in-use", self._send("GET", "/channels/portsInUse"),
            required={"id": str, "name": str, "port": (str, int)},
        )

    @classmethod
    def _normalize_destination_statistics(cls, value: Any) -> Mapping[str, Any]:
        candidates: list[Mapping[str, Any]] = []
        if isinstance(value, Mapping):
            candidates.append(value)
            for key in ("statistics", "destination", "destinationStatistics"):
                nested = value.get(key)
                if isinstance(nested, Mapping):
                    candidates.append(nested)
                elif isinstance(nested, list):
                    candidates.extend(item for item in nested if isinstance(item, Mapping))
        elif isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, Mapping))
        if not candidates:
            raise OieManagementError(
                OieErrorCategory.UNEXPECTED_RESPONSE,
                "OIE destination statistics response lacked required structure.",
            )

        def total(keys: tuple[str, ...]) -> int | None:
            found: list[int] = []
            for item in candidates:
                for key in keys:
                    raw = item.get(key)
                    if isinstance(raw, bool):
                        continue
                    try:
                        number = int(raw)
                    except (TypeError, ValueError):
                        continue
                    if number >= 0:
                        found.append(number)
                        break
            return sum(found) if found else None

        queued = total(("queued", "queuedCount", "queuedMessages"))
        errors = total(("error", "errors", "errorCount", "errorMessages"))
        if queued is None or errors is None:
            raise OieManagementError(
                OieErrorCategory.UNEXPECTED_RESPONSE,
                "OIE destination statistics response lacked queued/error totals.",
            )
        return {"availability": "available", "queued": queued, "errors": errors}

    def create_channel(self, channel: Mapping[str, Any] | str) -> OieResult:
        response = self._send_channel("POST", "/channels/", channel)
        self._require_boolean_success(response)
        identifier = str(channel.get("id", "")) if isinstance(channel, Mapping) else ""
        return OieResult("create-channel", identifier=identifier)

    def update_channel(
        self, channel_id: str, channel: Mapping[str, Any] | str, *, override: bool = False
    ) -> OieResult:
        channel_id = self._identifier(channel_id)
        query = urllib.parse.urlencode({"override": str(override).lower()})
        response = self._send_channel(
            "PUT", f"/channels/{self._quote(channel_id)}?{query}", channel
        )
        self._require_boolean_success(response)
        return OieResult("update-channel", identifier=channel_id)

    def delete_channel(self, channel_id: str) -> OieResult:
        channel_id = self._identifier(channel_id)
        self.require_supported_version()
        self._send("DELETE", f"/channels/{self._quote(channel_id)}")
        return OieResult("delete-channel", identifier=channel_id)

    def deploy(self, channel_id: str) -> OieResult:
        return self._primitive("deploy", channel_id, "_deploy")

    def redeploy_all(self) -> OieResult:
        self.require_supported_version()
        self._send("POST", "/channels/_redeployAll")
        return OieResult("redeploy-all")

    def undeploy(self, channel_id: str) -> OieResult:
        return self._primitive("undeploy", channel_id, "_undeploy")

    def _primitive(self, operation: str, channel_id: str, action: str) -> OieResult:
        channel_id = self._identifier(channel_id)
        self.require_supported_version()
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
        self.require_supported_version()
        return self._send(
            method, path, body=body,
            content_type="application/json",
        )

    def _send_channel(
        self, method: str, path: str, value: Mapping[str, Any] | str
    ) -> HttpResponse:
        if isinstance(value, str):
            if not value.strip().startswith("<channel"):
                raise OieManagementError(
                    OieErrorCategory.VALIDATION,
                    "Channel XML payload must contain a channel root.",
                )
            self.require_supported_version()
            return self._send(
                method, path, body=value.encode("utf-8"),
                content_type="application/xml",
            )
        return self._send_json(method, path, value)

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

    @staticmethod
    def _require_fields(
        value: Mapping[str, Any],
        label: str,
        required: Mapping[str, type | tuple[type, ...]],
    ) -> None:
        invalid = [
            key for key, expected in required.items()
            if key not in value
            or not isinstance(value[key], expected)
            or (isinstance(value[key], str) and not value[key].strip())
        ]
        if invalid:
            raise OieManagementError(
                OieErrorCategory.UNEXPECTED_RESPONSE,
                f"OIE {label} response lacked required structure.",
            )

    def _mapping_value_result(
        self, operation: str, value: Mapping[str, Any], identifier: str = ""
    ) -> OieResult:
        result_id = identifier or str(value.get("id", ""))
        revision_value = value.get("revision")
        revision = revision_value if isinstance(revision_value, int) else None
        status = str(value.get("status", ""))
        return OieResult(operation, result_id, revision, status, value)

    def _sequence_result(
        self,
        operation: str,
        response: HttpResponse,
        *,
        required: Mapping[str, type | tuple[type, ...]],
    ) -> OieResult:
        value = self._json(response)
        if not isinstance(value, list):
            raise OieManagementError(
                OieErrorCategory.UNEXPECTED_RESPONSE, "OIE response was not a list."
            )
        normalized = []
        for item in value:
            if not isinstance(item, Mapping):
                raise OieManagementError(
                    OieErrorCategory.UNEXPECTED_RESPONSE,
                    f"OIE {operation} response contained an invalid item.",
                )
            redacted = self._redact_mapping(item)
            self._require_fields(redacted, operation, required)
            normalized.append(redacted)
        return OieResult(operation, values={"items": tuple(normalized)})

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
