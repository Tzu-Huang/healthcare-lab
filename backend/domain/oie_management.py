"""Persistence-neutral contracts for the OIE Management API client."""

from __future__ import annotations

import math
import urllib.parse
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


SUPPORTED_OIE_VERSION = "4.5.2"


class OieTlsMode(StrEnum):
    VERIFIED = "verified"
    LOCAL_SELF_SIGNED = "local-self-signed"


class OieErrorCategory(StrEnum):
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    TLS = "tls"
    CONNECTION = "connection"
    TIMEOUT = "timeout"
    REVISION_CONFLICT = "revision-conflict"
    VALIDATION = "validation"
    UNSUPPORTED_VERSION = "unsupported-version"
    SERVER = "server"
    UNEXPECTED_RESPONSE = "unexpected-response"
    UNAUTHENTICATED = "unauthenticated"


class OieManagementError(RuntimeError):
    """Stable, secret-safe client failure."""

    def __init__(
        self,
        category: OieErrorCategory,
        detail: str,
        *,
        http_status: int | None = None,
    ) -> None:
        self.category = category
        self.detail = detail[:240]
        self.http_status = http_status
        super().__init__(f"{category.value}: {self.detail}")

    def __repr__(self) -> str:
        return (
            f"OieManagementError(category={self.category.value!r}, "
            f"detail={self.detail!r}, http_status={self.http_status!r})"
        )


@dataclass(frozen=True)
class OieManagementConfig:
    base_url: str
    username: str
    password: str = field(repr=False)
    tls_mode: OieTlsMode = OieTlsMode.VERIFIED
    connect_timeout: float = 5.0
    read_timeout: float = 15.0

    def __post_init__(self) -> None:
        base_url = self.base_url.strip().rstrip("/")
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise OieManagementError(
                OieErrorCategory.VALIDATION,
                "OIE base URL must contain an http or https scheme and host.",
            )
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise OieManagementError(
                OieErrorCategory.VALIDATION,
                "OIE base URL must not contain credentials, query, or fragment data.",
            )
        if not self.username.strip() or not self.password:
            raise OieManagementError(
                OieErrorCategory.VALIDATION,
                "OIE username and password are required.",
            )
        for label, value in (
            ("connect timeout", self.connect_timeout),
            ("read timeout", self.read_timeout),
        ):
            if not math.isfinite(value) or value <= 0:
                raise OieManagementError(
                    OieErrorCategory.VALIDATION, f"OIE {label} must be positive and finite."
                )
        if self.tls_mode is OieTlsMode.LOCAL_SELF_SIGNED and parsed.scheme != "https":
            raise OieManagementError(
                OieErrorCategory.VALIDATION,
                "Local self-signed mode requires an https OIE base URL.",
            )
        object.__setattr__(self, "base_url", base_url)
        object.__setattr__(self, "username", self.username.strip())


@dataclass(frozen=True)
class OieResult:
    operation: str
    identifier: str = ""
    revision: int | None = None
    status: str = ""
    values: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OieVersionSupport:
    version: str
    supported: bool


def classify_oie_version(version: str) -> OieVersionSupport:
    normalized = version.strip()
    if not normalized:
        raise OieManagementError(
            OieErrorCategory.UNEXPECTED_RESPONSE, "OIE server version was empty."
        )
    return OieVersionSupport(normalized, normalized == SUPPORTED_OIE_VERSION)
