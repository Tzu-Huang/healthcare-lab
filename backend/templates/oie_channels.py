"""Complete, constrained OIE 4.5.2 channel payload recipes."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from backend.domain.oie_channels import (
    Endpoint,
    InitialState,
    ManagedChannelConfig,
    ManagedChannelType,
    OIE_VERSION,
    QueuePolicy,
    UTF8_WIRE_VALUE,
    validate_route_set,
)


_ROOT = Path(__file__).resolve().parents[2]
_CANONICAL_EXPORTS = {
    ManagedChannelType.ORM_TO_AP: _ROOT / "docs" / "Dashboard_to_OIE_to_AP.xml",
    ManagedChannelType.ORU_TO_HLAB: _ROOT / "docs" / "AP_RESULT_TO_LAB.xml",
}

__all__ = [
    "compile_managed_routes",
    "compile_orm_to_ap",
    "compile_oru_to_hlab",
    "normalized_state",
    "normalized_state_from_payload",
    "orm_to_ap_config",
    "oru_to_hlab_config",
    "sanitized_canonical",
]


def orm_to_ap_config(
    ap_host: str,
    *,
    listener_host: str = "0.0.0.0",
    listener_port: int = 6600,
    destination_host: str | None = None,
    destination_port: int = 6671,
    send_timeout_ms: int = 5000,
    response_timeout_ms: int = 5000,
    enabled: bool = True,
    initial_state: InitialState = InitialState.STARTED,
    queue_enabled: bool = False,
    retry_count: int = 0,
    retry_interval_ms: int = 10_000,
) -> ManagedChannelConfig:
    return ManagedChannelConfig(
        logical_type=ManagedChannelType.ORM_TO_AP,
        display_name="HLAB_ORM_TO_AP",
        listener=Endpoint(listener_host, listener_port),
        destination=Endpoint(destination_host or ap_host, destination_port),
        send_timeout_ms=send_timeout_ms,
        response_timeout_ms=response_timeout_ms,
        queue=QueuePolicy(enabled=queue_enabled, retry_count=retry_count, retry_interval_ms=retry_interval_ms),
        enabled=enabled,
        initial_state=initial_state,
    )


def oru_to_hlab_config(
    *,
    listener_host: str = "0.0.0.0",
    listener_port: int = 6661,
    destination_host: str = "lab-app",
    destination_port: int = 6665,
    send_timeout_ms: int = 5000,
    response_timeout_ms: int = 5000,
    enabled: bool = True,
    initial_state: InitialState = InitialState.STARTED,
    queue_enabled: bool = True,
    retry_count: int = 0,
    retry_interval_ms: int = 10_000,
) -> ManagedChannelConfig:
    return ManagedChannelConfig(
        logical_type=ManagedChannelType.ORU_TO_HLAB,
        display_name="HLAB_ORU_TO_HLAB",
        listener=Endpoint(listener_host, listener_port),
        destination=Endpoint(destination_host, destination_port),
        send_timeout_ms=send_timeout_ms,
        response_timeout_ms=response_timeout_ms,
        queue=QueuePolicy(enabled=queue_enabled, retry_count=retry_count, retry_interval_ms=retry_interval_ms),
        enabled=enabled,
        initial_state=initial_state,
    )


def compile_managed_routes(ap_host: str, **orm_overrides: Any) -> tuple[str, str]:
    orm = orm_to_ap_config(ap_host, **orm_overrides)
    oru = oru_to_hlab_config()
    validate_route_set(orm, oru)
    return _render_channel(orm), _render_channel(oru)


def compile_orm_to_ap(
    ap_host: str,
    *,
    listener_host: str = "0.0.0.0",
    listener_port: int = 6600,
    destination_host: str | None = None,
    destination_port: int = 6671,
    send_timeout_ms: int = 5000,
    response_timeout_ms: int = 5000,
    enabled: bool = True,
    initial_state: InitialState = InitialState.STARTED,
    queue_enabled: bool = False,
    retry_count: int = 0,
    retry_interval_ms: int = 10_000,
) -> str:
    return _render_channel(
        orm_to_ap_config(
            ap_host,
            listener_host=listener_host,
            listener_port=listener_port,
            destination_host=destination_host,
            destination_port=destination_port,
            send_timeout_ms=send_timeout_ms,
            response_timeout_ms=response_timeout_ms,
            enabled=enabled,
            initial_state=initial_state,
            queue_enabled=queue_enabled,
            retry_count=retry_count,
            retry_interval_ms=retry_interval_ms,
        )
    )


def compile_oru_to_hlab(
    *,
    listener_host: str = "0.0.0.0",
    listener_port: int = 6661,
    destination_host: str = "lab-app",
    destination_port: int = 6665,
    send_timeout_ms: int = 5000,
    response_timeout_ms: int = 5000,
    enabled: bool = True,
    initial_state: InitialState = InitialState.STARTED,
    queue_enabled: bool = True,
    retry_count: int = 0,
    retry_interval_ms: int = 10_000,
) -> str:
    return _render_channel(
        oru_to_hlab_config(
            listener_host=listener_host,
            listener_port=listener_port,
            destination_host=destination_host,
            destination_port=destination_port,
            send_timeout_ms=send_timeout_ms,
            response_timeout_ms=response_timeout_ms,
            enabled=enabled,
            initial_state=initial_state,
            queue_enabled=queue_enabled,
            retry_count=retry_count,
            retry_interval_ms=retry_interval_ms,
        )
    )


def _render_channel(config: ManagedChannelConfig) -> str:
    validate_route_set(config)
    root = _canonical_root(config.logical_type)
    root.set("version", OIE_VERSION)
    _set(root, "id", "")
    _set(root, "name", config.display_name)
    _set(root, "description", config.marker)
    _set(root, "revision", "0")
    metadata = root.find("exportData/metadata")
    if metadata is not None:
        for server_field in ("lastModified", "userId"):
            node = metadata.find(server_field)
            if node is not None:
                metadata.remove(node)

    _set(root, "sourceConnector/properties/listenerConnectorProperties/host", config.listener.host)
    _set(root, "sourceConnector/properties/listenerConnectorProperties/port", config.listener.port)
    for node in root.findall(".//charsetEncoding"):
        node.text = UTF8_WIRE_VALUE

    destination = root.find("destinationConnectors/connector")
    if destination is None:
        raise RuntimeError("Canonical OIE export is missing its fixed destination connector.")
    _set(destination, "properties/remoteAddress", config.destination.host)
    _set(destination, "properties/remotePort", config.destination.port)
    _set(destination, "properties/sendTimeout", config.send_timeout_ms)
    _set(destination, "properties/responseTimeout", config.response_timeout_ms)
    _set(destination, "properties/queueOnResponseTimeout", _xml_bool(config.queue.queue_on_response_timeout))
    _set(destination, "properties/charsetEncoding", UTF8_WIRE_VALUE)
    _set(destination, "properties/destinationConnectorProperties/queueEnabled", _xml_bool(config.queue.enabled))
    _set(destination, "properties/destinationConnectorProperties/retryIntervalMillis", config.queue.retry_interval_ms)
    _set(destination, "properties/destinationConnectorProperties/retryCount", config.queue.retry_count)
    _set(destination, "properties/destinationConnectorProperties/queueBufferSize", config.queue.buffer_size)
    _set(destination, "properties/destinationConnectorProperties/validateResponse", "true")
    validation = "responseTransformer/inboundProperties/responseValidationProperties"
    _set(destination, f"{validation}/successfulACKCode", "AA,CA")
    _set(destination, f"{validation}/errorACKCode", "AE,CE")
    _set(destination, f"{validation}/rejectedACKCode", "AR,CR")
    _set(destination, f"{validation}/validateMessageControlId", "true")
    _set(root, "properties/initialState", config.initial_state.value)
    _set(root, "exportData/metadata/enabled", _xml_bool(config.enabled))
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def normalized_state(config: ManagedChannelConfig) -> dict[str, Any]:
    return {
        "logical_type": config.logical_type.value,
        "template_version": config.template_version,
        "marker": config.marker,
        "display_name": config.display_name,
        "listener": {"host": config.listener.host, "port": config.listener.port},
        "destination": {"host": config.destination.host, "port": config.destination.port},
        "protocol": {
            "source_mode": "MLLP",
            "destination_mode": "MLLP",
            "source_inbound_type": "HL7V2",
            "source_outbound_type": "HL7V2",
            "destination_inbound_type": "HL7V2",
            "destination_outbound_type": "HL7V2",
        },
        "charset": {
            "source": UTF8_WIRE_VALUE,
            "destination": UTF8_WIRE_VALUE,
        },
        "timeouts_ms": {
            "send": config.send_timeout_ms,
            "response": config.response_timeout_ms,
        },
        "queue": {
            "enabled": config.queue.enabled,
            "retry_interval": config.queue.retry_interval_ms,
            "retry_count": config.queue.retry_count,
            "buffer_size": config.queue.buffer_size,
            "queue_on_response_timeout": config.queue.queue_on_response_timeout,
        },
        "enabled": config.enabled,
        "initial_state": config.initial_state.value,
    }


def normalized_state_from_payload(payload: str) -> dict[str, Any]:
    root = ET.fromstring(payload)
    description = _text(root, "description")
    logical_value = _marker_value(description, "logical_type")
    logical_type = ManagedChannelType(logical_value)
    template_version = int(_marker_value(description, "template_version"))
    destination = root.find("destinationConnectors/connector")
    if destination is None:
        raise ValueError("payload destination connector is required.")
    queue = destination.find("properties/destinationConnectorProperties")
    if queue is None:
        raise ValueError("payload queue properties are required.")
    config = ManagedChannelConfig(
        logical_type=logical_type,
        display_name=_text(root, "name"),
        listener=Endpoint(
            _text(root, "sourceConnector/properties/listenerConnectorProperties/host"),
            int(_text(root, "sourceConnector/properties/listenerConnectorProperties/port")),
        ),
        destination=Endpoint(
            _text(destination, "properties/remoteAddress"),
            int(_text(destination, "properties/remotePort")),
        ),
        send_timeout_ms=int(_text(destination, "properties/sendTimeout")),
        response_timeout_ms=int(_text(destination, "properties/responseTimeout")),
        queue=QueuePolicy(
            enabled=_parse_xml_bool(_text(queue, "queueEnabled"), "queueEnabled"),
            retry_interval_ms=int(_text(queue, "retryIntervalMillis")),
            retry_count=int(_text(queue, "retryCount")),
            buffer_size=int(_text(queue, "queueBufferSize")),
            queue_on_response_timeout=_parse_xml_bool(
                _text(destination, "properties/queueOnResponseTimeout"),
                "queueOnResponseTimeout",
            ),
        ),
        enabled=_parse_xml_bool(
            _text(root, "exportData/metadata/enabled"),
            "enabled",
        ),
        initial_state=InitialState(_text(root, "properties/initialState")),
    )
    state = normalized_state(config)
    state["template_version"] = template_version
    state["marker"] = description
    state["protocol"] = {
        "source_mode": _text(
            root,
            "sourceConnector/properties/transmissionModeProperties/pluginPointName",
        ),
        "destination_mode": _text(
            destination,
            "properties/transmissionModeProperties/pluginPointName",
        ),
        "source_inbound_type": _text(
            root,
            "sourceConnector/transformer/inboundDataType",
        ),
        "source_outbound_type": _text(
            root,
            "sourceConnector/transformer/outboundDataType",
        ),
        "destination_inbound_type": _text(
            destination,
            "transformer/inboundDataType",
        ),
        "destination_outbound_type": _text(
            destination,
            "transformer/outboundDataType",
        ),
    }
    state["charset"] = {
        "source": _text(root, "sourceConnector/properties/charsetEncoding"),
        "destination": _text(destination, "properties/charsetEncoding"),
    }
    return state


def sanitized_canonical(logical_type: ManagedChannelType) -> str:
    """Return canonical evidence with runtime identity and environment data removed."""
    sample_host = "ap.internal" if logical_type is ManagedChannelType.ORM_TO_AP else "lab-app"
    config = orm_to_ap_config(sample_host) if logical_type is ManagedChannelType.ORM_TO_AP else oru_to_hlab_config()
    return _render_channel(config)


def _canonical_root(logical_type: ManagedChannelType) -> ET.Element:
    return deepcopy(ET.parse(_CANONICAL_EXPORTS[logical_type]).getroot())


def _set(parent: ET.Element, path: str, value: Any, *, required: bool = True) -> None:
    node = parent.find(path)
    if node is None:
        if required:
            raise RuntimeError(f"Canonical OIE export is missing {path}.")
        return
    node.text = str(value)


def _text(parent: ET.Element, path: str) -> str:
    node = parent.find(path)
    if node is None or node.text is None:
        raise ValueError(f"payload field {path} is required.")
    return node.text


def _marker_value(description: str, key: str) -> str:
    prefix = f"{key}="
    for segment in description.split("; "):
        if segment.startswith(prefix):
            return segment[len(prefix):]
    raise ValueError(f"managed marker is missing {key}.")


def _xml_bool(value: bool) -> str:
    return "true" if value else "false"


def _parse_xml_bool(value: str, field: str) -> bool:
    if value not in {"true", "false"}:
        raise ValueError(f"payload field {field} must be true or false.")
    return value == "true"
