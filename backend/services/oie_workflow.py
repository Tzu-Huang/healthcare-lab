"""OIE workflow coordination independent of Flask request state."""

from __future__ import annotations

import socket
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from backend.lab_store import (
    ORDER_STATUS_ACCEPTED,
    ORDER_STATUS_ERROR,
    ORDER_STATUS_REJECTED,
    ORDER_STATUS_TRANSPORT_ERROR,
)


class OieRepositoryPort(Protocol):
    def list_oie_local_adt_inventory(self) -> list[dict[str, Any]]: ...

    def list_oie_local_order_inventory(self) -> list[dict[str, Any]]: ...

    def list_oie_workbench(self) -> dict[str, Any]: ...

    def list_oie_results(self) -> list[dict[str, Any]]: ...

    def get_order_record(self, order_id: int) -> dict[str, Any]: ...

    def update_order_send_result(self, order_id: int, **values: Any) -> dict[str, Any]: ...


class OieListenerPort(Protocol):
    def status(self) -> dict[str, Any]: ...

    def start(self, *, host: str, port: int, framing: bool = True) -> dict[str, Any]: ...

    def stop(self) -> dict[str, Any]: ...


class OieTransportError(Exception):
    def __init__(self, message: str, item: dict[str, Any]) -> None:
        super().__init__(message)
        self.item = item


class OieWorkflowService:
    def __init__(
        self,
        repository: OieRepositoryPort,
        configuration: Mapping[str, Any],
        listener: OieListenerPort,
        *,
        result_handler: Callable[[OieRepositoryPort, str], tuple[str, dict[str, Any], int]],
        ack_parser: Callable[[str], dict[str, str]],
        order_sender_provider: Callable[[], Callable[..., str]],
    ) -> None:
        self._repository = repository
        self._configuration = configuration
        self._listener = listener
        self._result_handler = result_handler
        self._ack_parser = ack_parser
        self._order_sender_provider = order_sender_provider

    def local_adt_inventory(self) -> list[dict[str, Any]]:
        return self._repository.list_oie_local_adt_inventory()

    def local_order_inventory(self) -> list[dict[str, Any]]:
        return self._repository.list_oie_local_order_inventory()

    def workbench(self) -> dict[str, Any]:
        return self._repository.list_oie_workbench()

    def results(self) -> list[dict[str, Any]]:
        return self._repository.list_oie_results()

    def receive_result(self, payload: str) -> tuple[str, dict[str, Any], int]:
        if not payload.strip():
            raise ValueError("HL7 payload is required.")
        return self._result_handler(self._repository, payload)

    def listener_status(self) -> dict[str, Any]:
        return self._listener.status()

    def start_listener(self, payload: dict[str, Any]) -> dict[str, Any]:
        host = str(
            payload.get("host", self._configuration["OIE_MLLP_RESULT_HOST"]) or ""
        ).strip()
        try:
            port = int(payload.get("port", self._configuration["OIE_MLLP_RESULT_PORT"]))
        except (TypeError, ValueError) as exc:
            raise ValueError("Listener port must be numeric.") from exc
        return self._listener.start(
            host=host, port=port, framing=bool(payload.get("mllpFraming", True))
        )

    def stop_listener(self) -> dict[str, Any]:
        return self._listener.stop()

    def send_order(self, order_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        default_host = self._configuration["OIE_MLLP_ORDER_HOST"]
        default_port = self._configuration["OIE_MLLP_ORDER_PORT"]
        host = str(payload.get("host", default_host) or default_host).strip()
        try:
            port = int(payload.get("port", default_port) or default_port)
            timeout_seconds = float(payload.get("timeoutSeconds", 5) or 5)
        except (TypeError, ValueError) as exc:
            raise ValueError("OIE port and timeout must be numeric.") from exc
        if not host:
            raise ValueError("OIE host is required.")
        if not 1 <= port <= 65535:
            raise ValueError("OIE port must be between 1 and 65535.")
        if timeout_seconds <= 0:
            raise ValueError("OIE timeout must be positive.")

        order = self._repository.get_order_record(order_id)
        try:
            ack_payload = self._order_sender_provider()(
                order["payload"],
                host=host,
                port=port,
                timeout_seconds=timeout_seconds,
                framing=bool(payload.get("mllpFraming", True)),
            )
            ack = self._ack_parser(ack_payload)
            status = (
                ORDER_STATUS_ACCEPTED
                if ack["code"] == "AA"
                else ORDER_STATUS_REJECTED
                if ack["code"] == "AR"
                else ORDER_STATUS_ERROR
            )
            return self._repository.update_order_send_result(
                order_id,
                order_status=status,
                ack_code=ack["code"],
                ack_control_id=ack["controlId"],
                ack_text=ack["text"],
                ack_payload=ack_payload,
            )
        except (OSError, socket.timeout, TimeoutError) as exc:
            item = self._repository.update_order_send_result(
                order_id,
                order_status=ORDER_STATUS_TRANSPORT_ERROR,
                transport_error=str(exc),
            )
            raise OieTransportError(str(exc), item) from exc
