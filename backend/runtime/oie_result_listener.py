"""MLLP result listener lifecycle."""

from __future__ import annotations

import socket
import threading
from datetime import datetime, timezone
from typing import Any, Protocol

from backend.domain.errors import ValidationError


class OieResultStorePort(Protocol):
    def record_oie_result(
        self, raw_message: str, parsed: dict[str, str]
    ) -> dict[str, Any]: ...

    def record_oie_result_error(
        self, raw_message: str, message_type: str, error: str
    ) -> dict[str, Any]: ...


class ResultHandler(Protocol):
    def __call__(
        self, store: OieResultStorePort, payload: str
    ) -> tuple[str, dict[str, Any], int]: ...


def mllp_frame(message: str) -> bytes:
    return b"\x0b" + message.encode("utf-8") + b"\x1c\x0d"


def mllp_unframe(payload: bytes) -> str:
    value = payload
    if value.startswith(b"\x0b"):
        value = value[1:]
    if value.endswith(b"\x1c\x0d"):
        value = value[:-2]
    return value.decode("utf-8", errors="replace")


class OieResultListener:
    def __init__(self, store: OieResultStorePort, result_handler: ResultHandler):
        self.store = store
        self._result_handler = result_handler
        self.host = "0.0.0.0"
        self.port = 6665
        self.framing = True
        self._thread: threading.Thread | None = None
        self._socket: socket.socket | None = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        self._state = "stopped"
        self.last_error = ""
        self.error_category = ""
        self.last_received_at = ""

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": self._state,
                "running": bool(self._thread and self._thread.is_alive()),
                "host": self.host,
                "port": self.port,
                "mllpFraming": self.framing,
                "lastError": self.last_error,
                "errorCategory": self.error_category,
                "lastReceivedAt": self.last_received_at,
            }

    def start(self, *, host: str, port: int, framing: bool = True) -> dict[str, Any]:
        if not host:
            raise ValidationError("Listener host is required.")
        if not 1 <= int(port) <= 65535:
            raise ValidationError("Listener port must be between 1 and 65535.")
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        with self._lock:
            if self._thread and self._thread.is_alive():
                if self.host == host and self.port == int(port) and self.framing == framing:
                    server.close()
                    return self.status()
                server.close()
                raise ValidationError("Stop the current listener before changing configuration.")
            try:
                server.bind((host, int(port)))
                server.listen(5)
                server.settimeout(0.5)
            except OSError as exc:
                server.close()
                self.host = host
                self.port = int(port)
                self.framing = bool(framing)
                self._state = "degraded"
                self.last_error = str(exc)
                self.error_category = "port-conflict"
                raise ValidationError(f"Listener could not start: {exc}") from exc
            self.host = host
            self.port = int(port)
            self.framing = bool(framing)
            self.last_error = ""
            self.error_category = ""
            self._state = "running"
            self._stop_event.clear()
            self._socket = server
            self._thread = threading.Thread(target=self._serve, name="oie-result-listener", daemon=True)
            self._thread.start()
        return self.status()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self._stop_event.set()
            if self._socket:
                try:
                    self._socket.close()
                except OSError:
                    pass
            thread = self._thread
        if thread:
            thread.join(timeout=2)
        with self._lock:
            self._state = "stopped"
            self.last_error = ""
            self.error_category = ""
        return self.status()

    def _serve(self) -> None:
        with self._lock:
            server = self._socket
        if server is None:
            return
        try:
            while not self._stop_event.is_set():
                try:
                    connection, _address = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if not self._stop_event.is_set():
                        with self._lock:
                            self._state = "degraded"
                            self.last_error = "Listener socket closed unexpectedly."
                            self.error_category = "runtime-failure"
                    break
                with connection:
                    self._handle_connection(connection)
        except OSError as exc:
            with self._lock:
                self._state = "degraded"
                self.last_error = str(exc)
                self.error_category = "runtime-failure"
        finally:
            with self._lock:
                self._socket = None
                if self._stop_event.is_set():
                    self._state = "stopped"
            try:
                server.close()
            except OSError:
                pass

    def _handle_connection(self, connection: socket.socket) -> None:
        received = bytearray()
        connection.settimeout(5)
        try:
            while True:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                received.extend(chunk)
                if self.framing and b"\x1c\x0d" in received:
                    break
            payload = mllp_unframe(bytes(received)) if self.framing else bytes(received).decode("utf-8", errors="replace")
            ack, _item, _status = self._result_handler(self.store, payload)
            connection.sendall(mllp_frame(ack) if self.framing else ack.encode("utf-8"))
            with self._lock:
                self.last_received_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
                self.last_error = ""
                self.error_category = ""
        except Exception as exc:  # pragma: no cover - defensive listener boundary
            with self._lock:
                self.last_error = str(exc)
                self.error_category = "message-processing-failure"
