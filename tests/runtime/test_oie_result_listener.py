import unittest
import socket

from backend.runtime.oie_result_listener import OieResultListener, mllp_frame
from backend.domain.errors import ValidationError


class FakeConnection:
    def __init__(self, payload):
        self._chunks = [payload, b""]
        self.sent = b""

    def settimeout(self, _timeout):
        return None

    def recv(self, _size):
        return self._chunks.pop(0)

    def sendall(self, payload):
        self.sent = payload


class OieResultListenerTest(unittest.TestCase):
    def test_status_defaults_are_stable(self):
        listener = OieResultListener(object(), lambda _store, _payload: ("ACK", {}, 200))

        self.assertEqual(
            {
                "state": "stopped",
                "running": False,
                "host": "0.0.0.0",
                "port": 6665,
                "mllpFraming": True,
                "lastError": "",
                "lastReceivedAt": "",
            },
            listener.status(),
        )

    def test_connection_payload_is_delegated_to_injected_handler(self):
        received = []

        def handler(_store, payload):
            received.append(payload)
            return "MSH|ACK", {}, 200

        listener = OieResultListener(object(), handler)
        connection = FakeConnection(mllp_frame("MSH|RESULT"))

        listener._handle_connection(connection)

        self.assertEqual(["MSH|RESULT"], received)
        self.assertEqual(mllp_frame("MSH|ACK"), connection.sent)

    def test_repeated_start_reuses_one_socket_and_thread(self):
        listener = OieResultListener(object(), lambda *_args: ("ACK", {}, 200))
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        try:
            first = listener.start(host="127.0.0.1", port=port, framing=True)
            thread = listener._thread
            server = listener._socket

            second = listener.start(host="127.0.0.1", port=port, framing=True)

            self.assertEqual("running", first["state"])
            self.assertEqual("running", second["state"])
            self.assertIs(thread, listener._thread)
            self.assertIs(server, listener._socket)
            with self.assertRaisesRegex(ValidationError, "Stop the current listener"):
                listener.start(host="127.0.0.1", port=port + 1, framing=True)
        finally:
            listener.stop()

    def test_bind_failure_degrades_and_stop_clears_error(self):
        occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        occupied.bind(("127.0.0.1", 0))
        occupied.listen(1)
        port = occupied.getsockname()[1]
        listener = OieResultListener(object(), lambda *_args: ("ACK", {}, 200))
        try:
            with self.assertRaisesRegex(ValidationError, "Listener could not start"):
                listener.start(host="127.0.0.1", port=port, framing=False)
        finally:
            occupied.close()

        degraded = listener.status()
        self.assertEqual("degraded", degraded["state"])
        self.assertEqual(port, degraded["port"])
        self.assertFalse(degraded["mllpFraming"])
        self.assertTrue(degraded["lastError"])
        stopped = listener.stop()
        self.assertEqual("stopped", stopped["state"])
        self.assertEqual("", stopped["lastError"])


if __name__ == "__main__":
    unittest.main()
