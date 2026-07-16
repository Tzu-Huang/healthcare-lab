"""Persistence-neutral contracts for Healthcare Lab managed OIE channels."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Address
import re
from typing import Any

from .errors import ValidationError


MANAGED_MARKER = "Managed by Healthcare Lab"
TEMPLATE_VERSION = 1
OIE_VERSION = "4.5.2"
UTF8_WIRE_VALUE = "UTF-8"


class ManagedChannelType(str, Enum):
    ORM_TO_AP = "hlab-orm-to-ap"
    ORU_TO_HLAB = "hlab-oru-to-hlab"


class InitialState(str, Enum):
    STARTED = "STARTED"
    STOPPED = "STOPPED"
    PAUSED = "PAUSED"


@dataclass(frozen=True)
class Endpoint:
    host: str
    port: int


@dataclass(frozen=True)
class QueuePolicy:
    enabled: bool
    retry_interval_ms: int = 10_000
    retry_count: int = 0
    buffer_size: int = 1_000
    queue_on_response_timeout: bool = True


@dataclass(frozen=True)
class ManagedChannelConfig:
    logical_type: ManagedChannelType
    display_name: str
    listener: Endpoint
    destination: Endpoint
    send_timeout_ms: int = 5_000
    response_timeout_ms: int = 5_000
    queue: QueuePolicy = QueuePolicy(enabled=False)
    enabled: bool = True
    initial_state: InitialState = InitialState.STARTED
    template_version: int = TEMPLATE_VERSION

    def __post_init__(self) -> None:
        validate_host(self.listener.host, "listener.host", allow_wildcard=True)
        validate_port(self.listener.port, "listener.port")
        validate_host(self.destination.host, "destination.host")
        validate_port(self.destination.port, "destination.port")
        validate_timeout(self.send_timeout_ms, "send_timeout_ms")
        validate_timeout(self.response_timeout_ms, "response_timeout_ms")
        validate_bool(self.enabled, "enabled")
        validate_bool(self.queue.enabled, "queue.enabled")
        validate_bool(
            self.queue.queue_on_response_timeout,
            "queue.queue_on_response_timeout",
        )
        validate_timeout(self.queue.retry_interval_ms, "queue.retry_interval_ms")
        if type(self.queue.retry_count) is not int or self.queue.retry_count < 0:
            raise ValidationError("queue.retry_count must be a non-negative integer.")
        if type(self.queue.buffer_size) is not int or self.queue.buffer_size < 1:
            raise ValidationError("queue.buffer_size must be a positive integer.")
        if not isinstance(self.logical_type, ManagedChannelType):
            raise ValidationError("logical_type must be a supported managed channel type.")
        if not isinstance(self.initial_state, InitialState):
            raise ValidationError("initial_state must be STARTED, STOPPED, or PAUSED.")
        if self.template_version != TEMPLATE_VERSION:
            raise ValidationError(f"template_version must be {TEMPLATE_VERSION}.")

    @property
    def marker(self) -> str:
        return managed_marker(self.logical_type)


_DNS_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$", re.IGNORECASE)
_INTERNAL_SUFFIXES = (".internal", ".local", ".lan", ".home.arpa")


def validate_host(value: Any, field: str, *, allow_wildcard: bool = False) -> str:
    if not isinstance(value, str) or value != value.strip() or not value:
        raise ValidationError(f"{field} must be a non-empty host without whitespace.")
    if allow_wildcard and value == "0.0.0.0":
        return value
    if any(token in value for token in ("://", "/", "\\", "@", "?", "#")):
        raise ValidationError(
            f"{field} must be a host only; schemes, paths, credentials, and ports are not allowed."
        )
    try:
        address = IPv4Address(value)
    except ValueError:
        labels = value.rstrip(".").split(".")
        if not all(_DNS_LABEL.fullmatch(label) for label in labels):
            raise ValidationError(f"{field} must be a valid private IPv4 or internal DNS host.")
        lowered = value.rstrip(".").lower()
        if len(labels) > 1 and not lowered.endswith(_INTERNAL_SUFFIXES):
            raise ValidationError(f"{field} must be an internal DNS host, not a public name.")
    else:
        if not address.is_private:
            raise ValidationError(f"{field} must be a private IPv4 address.")
    return value


def validate_port(value: Any, field: str) -> int:
    if type(value) is not int or not 1 <= value <= 65_535:
        raise ValidationError(f"{field} must be an integer from 1 through 65535.")
    return value


def validate_timeout(value: Any, field: str) -> int:
    if type(value) is not int or value < 1:
        raise ValidationError(f"{field} must be a positive integer in milliseconds.")
    return value


def validate_bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise ValidationError(f"{field} must be a boolean.")
    return value


def validate_route_set(*configs: ManagedChannelConfig) -> tuple[ManagedChannelConfig, ...]:
    ports: dict[int, str] = {}
    for config in configs:
        previous = ports.get(config.listener.port)
        if previous is not None:
            raise ValidationError(
                "listener.port conflict: "
                f"{previous} and {config.logical_type.value} both use {config.listener.port}."
            )
        ports[config.listener.port] = config.logical_type.value
    return configs


def managed_marker(logical_type: ManagedChannelType) -> str:
    return (
        f"{MANAGED_MARKER}; logical_type={logical_type.value}; "
        f"template_version={TEMPLATE_VERSION}"
    )


def is_managed_description(value: str, logical_type: ManagedChannelType) -> bool:
    return value == managed_marker(logical_type)
