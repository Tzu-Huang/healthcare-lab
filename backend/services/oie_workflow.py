"""OIE workflow coordination independent of Flask request state."""

from __future__ import annotations

import socket
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, Protocol

from backend.domain.errors import ValidationError
from backend.domain.statuses import (
    ORDER_STATUS_ACCEPTED,
    ORDER_STATUS_ERROR,
    ORDER_STATUS_REJECTED,
    ORDER_STATUS_TRANSPORT_ERROR,
)

HL7_V2_MSH_SUFFIX = "2.5.1||||||UNICODE UTF-8"


class OieResultRepositoryPort(Protocol):
    def record_oie_result(
        self, raw_message: str, parsed: dict[str, str]
    ) -> dict[str, Any]: ...

    def record_oie_result_error(
        self, raw_message: str, message_type: str, error: str
    ) -> dict[str, Any]: ...

    def list_oie_results(self) -> list[dict[str, Any]]: ...


class OieCoordinationPort(Protocol):
    def list_oie_local_adt_inventory(self) -> list[dict[str, Any]]: ...

    def list_oie_local_order_inventory(self) -> list[dict[str, Any]]: ...


class OieInventoryCoordination:
    """Narrow patient/order inventory capability consumed by OIE workflows."""

    def __init__(self, patients, orders, *, patient_protocol: str, order_protocol: str):
        self._patients = patients
        self._orders = orders
        self._patient_protocol = patient_protocol
        self._order_protocol = order_protocol

    def list_oie_local_adt_inventory(self) -> list[dict[str, Any]]:
        return self._patients.list_patient_records(self._patient_protocol)

    def list_oie_local_order_inventory(self) -> list[dict[str, Any]]:
        return self._orders.list_order_records(self._order_protocol)

    def get_order_record(self, order_id: int) -> dict[str, Any]:
        return self._orders.get_order_record(order_id)

    def update_order_send_result(
        self,
        order_id: int,
        *,
        order_status: str,
        ack_code: str = "",
        ack_control_id: str = "",
        ack_text: str = "",
        ack_payload: str = "",
        transport_error: str = "",
    ) -> dict[str, Any]:
        return self._orders.update_order_send_result(
            order_id,
            order_status=order_status,
            ack_code=ack_code,
            ack_control_id=ack_control_id,
            ack_text=ack_text,
            ack_payload=ack_payload,
            transport_error=transport_error,
        )


class OieListenerPort(Protocol):
    def status(self) -> dict[str, Any]: ...

    def start(self, *, host: str, port: int, framing: bool = True) -> dict[str, Any]: ...

    def stop(self) -> dict[str, Any]: ...


class OieListenerConfigurationSource(Protocol):
    def get_result_listener_configuration(self) -> Mapping[str, Any]: ...


class OieTransportError(Exception):
    def __init__(self, message: str, item: dict[str, Any]) -> None:
        super().__init__(message)
        self.item = item


def compose_oie_workbench(
    patients: list[dict[str, Any]],
    orders: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    orders_by_patient: dict[int, list[dict[str, Any]]] = {}
    results_by_patient: dict[int, list[dict[str, Any]]] = {}
    for order in orders:
        orders_by_patient.setdefault(int(order["patientRecordId"]), []).append(order)
    visible_patient_ids = {int(patient["id"]) for patient in patients}
    unmatched_results = []
    for result in results:
        patient_id = result.get("matchedPatientRecordId")
        if patient_id and int(patient_id) in visible_patient_ids:
            results_by_patient.setdefault(int(patient_id), []).append(result)
        else:
            unmatched_results.append(result)
    items = []
    for patient in patients:
        patient_id = int(patient["id"])
        patient_orders = orders_by_patient.get(patient_id, [])
        patient_results = results_by_patient.get(patient_id, [])
        item = {
            **patient, "orders": patient_orders, "results": patient_results,
            "orderCount": len(patient_orders), "resultCount": len(patient_results),
        }
        item["summary"] = {
            **item["summary"], "orderCount": len(patient_orders),
            "resultCount": len(patient_results),
        }
        items.append(item)
    return {"patients": items, "unmatchedResults": unmatched_results}


class OieWorkflowService:
    def __init__(
        self,
        result_repository: OieResultRepositoryPort,
        coordination: OieCoordinationPort,
        configuration: Mapping[str, Any],
        listener: OieListenerPort,
        *,
        listener_configuration_source: OieListenerConfigurationSource,
        result_handler: Callable[[OieResultRepositoryPort, str], tuple[str, dict[str, Any], int]],
        ack_parser: Callable[[str], dict[str, str]],
        order_sender_provider: Callable[[], Callable[..., str]],
    ) -> None:
        self._results = result_repository
        self._coordination = coordination
        self._configuration = configuration
        self._listener = listener
        self._listener_configuration_source = listener_configuration_source
        self._result_handler = result_handler
        self._ack_parser = ack_parser
        self._order_sender_provider = order_sender_provider

    def local_adt_inventory(self) -> list[dict[str, Any]]:
        return self._coordination.list_oie_local_adt_inventory()

    def local_order_inventory(self) -> list[dict[str, Any]]:
        return self._coordination.list_oie_local_order_inventory()

    def workbench(self) -> dict[str, Any]:
        return compose_oie_workbench(
            self.local_adt_inventory(), self.local_order_inventory(), self.results()
        )

    def results(self) -> list[dict[str, Any]]:
        return self._results.list_oie_results()

    def receive_result(self, payload: str) -> tuple[str, dict[str, Any], int]:
        if not payload.strip():
            raise ValueError("HL7 payload is required.")
        return self._result_handler(self._results, payload)

    def listener_status(self) -> dict[str, Any]:
        return self._listener.status()

    def _listener_configuration(self) -> tuple[str, int, bool, bool]:
        values = self._listener_configuration_source.get_result_listener_configuration()
        host = str(values["host"]).strip()
        port = int(values["port"])
        framing = bool(values["mllp_framing"])
        auto_start = bool(values["auto_start"])
        return host, port, framing, auto_start

    def start_listener(self) -> dict[str, Any]:
        host, port, framing, _auto_start = self._listener_configuration()
        return self._listener.start(
            host=host, port=port, framing=framing
        )

    def retry_listener(self) -> dict[str, Any]:
        return self.start_listener()

    def auto_start_listener(self) -> dict[str, Any]:
        _host, _port, _framing, auto_start = self._listener_configuration()
        if not auto_start:
            return self._listener.status()
        try:
            return self.start_listener()
        except ValidationError:
            return self._listener.status()

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

        order = self._coordination.get_order_record(order_id)
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
            return self._coordination.update_order_send_result(
                order_id,
                order_status=status,
                ack_code=ack["code"],
                ack_control_id=ack["controlId"],
                ack_text=ack["text"],
                ack_payload=ack_payload,
            )
        except (OSError, socket.timeout, TimeoutError) as exc:
            item = self._coordination.update_order_send_result(
                order_id,
                order_status=ORDER_STATUS_TRANSPORT_ERROR,
                transport_error=str(exc),
            )
            raise OieTransportError(str(exc), item) from exc


def mllp_frame(message: str) -> bytes:
    return b"\x0b" + message.encode("utf-8") + b"\x1c\x0d"


def hl7_message_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def mllp_unframe(payload: bytes) -> str:
    text = payload.decode("utf-8", errors="replace")
    if text.startswith("\x0b"):
        text = text[1:]
    if text.endswith("\x1c\r"):
        text = text[:-2]
    elif text.endswith("\x1c"):
        text = text[:-1]
    return text


def parse_hl7_ack(payload: str) -> dict[str, str]:
    result = {"code": "", "controlId": "", "text": ""}
    for segment in payload.replace("\n", "\r").split("\r"):
        fields = segment.split("|")
        if fields and fields[0] == "MSA":
            result["code"] = fields[1].strip() if len(fields) > 1 else ""
            result["controlId"] = fields[2].strip() if len(fields) > 2 else ""
            result["text"] = fields[3].strip() if len(fields) > 3 else ""
            break
    return result


def _hl7_segments(payload: str) -> list[list[str]]:
    return [
        segment.split("|")
        for segment in payload.replace("\n", "\r").split("\r")
        if segment.strip()
    ]


def _first_component(value: str) -> str:
    return str(value or "").split("^", 1)[0].strip()


def _hl7_message_code(value: str) -> str:
    components = str(value or "").split("^")
    return "^".join(part.strip() for part in components[:2] if part.strip())


def parse_oru_summary(payload: str) -> dict[str, str]:
    segments = _hl7_segments(payload)
    if not segments or segments[0][0] != "MSH":
        raise ValidationError("HL7 payload must start with an MSH segment.")
    summary = {
        "messageType": "",
        "messageControlId": "",
        "patientMrn": "",
        "placerOrderNumber": "",
        "fillerOrderNumber": "",
    }
    for fields in segments:
        segment_id = fields[0]
        if segment_id == "MSH":
            summary["messageType"] = _hl7_message_code(fields[8] if len(fields) > 8 else "")
            summary["messageControlId"] = fields[9].strip() if len(fields) > 9 else ""
        elif segment_id == "PID":
            summary["patientMrn"] = _first_component(fields[3] if len(fields) > 3 else "")
        elif segment_id == "OBR":
            summary["placerOrderNumber"] = _first_component(fields[2] if len(fields) > 2 else "")
            summary["fillerOrderNumber"] = _first_component(fields[3] if len(fields) > 3 else "")
    if not summary["messageType"]:
        raise ValidationError("HL7 MSH-9 message type is required.")
    return summary


def build_hl7_ack(
    inbound_payload: str,
    *,
    code: str,
    text: str = "",
    message_control_id: str = "",
) -> str:
    inbound_msh = next(
        (fields for fields in _hl7_segments(inbound_payload) if fields and fields[0] == "MSH"),
        [],
    )
    sending_app = inbound_msh[4] if len(inbound_msh) > 4 and inbound_msh[4] else "HEALTHCARE_LAB"
    sending_facility = inbound_msh[5] if len(inbound_msh) > 5 and inbound_msh[5] else "LAB_APP"
    receiving_app = inbound_msh[2] if len(inbound_msh) > 2 and inbound_msh[2] else "OIE"
    receiving_facility = inbound_msh[3] if len(inbound_msh) > 3 and inbound_msh[3] else "HL7LAB"
    control_id = message_control_id
    if not control_id and len(inbound_msh) > 9:
        control_id = inbound_msh[9].strip()
    inbound_message = inbound_msh[8] if len(inbound_msh) > 8 else ""
    inbound_components = str(inbound_message or "").split("^")
    ack_trigger = inbound_components[1].strip() if len(inbound_components) > 1 and inbound_components[1].strip() else "R01"
    ack_time = hl7_message_timestamp()
    ack_control_id = f"ACK{ack_time}"
    segments = [
        (
            "MSH|^~\\&|"
            f"{sending_app}|{sending_facility}|{receiving_app}|{receiving_facility}|"
            f"{ack_time}||ACK^{ack_trigger}^ACK|{ack_control_id}|P|{HL7_V2_MSH_SUFFIX}"
        ),
        f"MSA|{code}|{control_id}|{text}",
    ]
    if code in {"AE", "AR", "CE", "CR"}:
        error_code = "200^Unsupported message type^HL70357" if code in {"AR", "CR"} else "102^Data type error^HL70357"
        segments.append(f"ERR||MSH^1^9^1^1|{error_code}|E")
    return "\r".join(segments)


def accept_oie_result_payload(
    store: OieResultRepositoryPort, payload: str
) -> tuple[str, dict[str, Any], int]:
    try:
        parsed = parse_oru_summary(payload)
        if parsed["messageType"] not in {"ORU^R01", "ORU^W01"}:
            item = store.record_oie_result_error(
                payload,
                parsed["messageType"],
                f"Unsupported message type: {parsed['messageType'] or 'unknown'}.",
            )
            ack = build_hl7_ack(
                payload,
                code="AR",
                text=item["error"],
                message_control_id=parsed.get("messageControlId", ""),
            )
            return ack, item, 400
        if not parsed["messageControlId"]:
            raise ValidationError("HL7 MSH-10 message control ID is required.")
        try:
            item = store.record_oie_result(payload, parsed)
        except ValidationError:
            raise
        except Exception:
            error = "Result persistence failed."
            try:
                item = store.record_oie_result_error(payload, parsed["messageType"], error)
            except Exception:
                # The ACK contract must survive a storage outage so OIE can keep
                # this delivery queued. Do not reflect storage exception text.
                item = {
                    "messageControlId": parsed["messageControlId"],
                    "messageType": parsed["messageType"],
                    "parseStatus": "error",
                    "error": error,
                }
            return (
                build_hl7_ack(
                    payload,
                    code="AE",
                    text=error,
                    message_control_id=parsed["messageControlId"],
                ),
                item,
                500,
            )
        text = "Duplicate result ignored." if item.get("duplicate") else "Result accepted."
        ack = build_hl7_ack(
            payload,
            code="AA",
            text=text,
            message_control_id=parsed.get("messageControlId", ""),
        )
        return ack, item, 200
    except ValidationError as exc:
        item = store.record_oie_result_error(payload, "", str(exc))
        return build_hl7_ack(payload, code="AE", text=str(exc)), item, 400
