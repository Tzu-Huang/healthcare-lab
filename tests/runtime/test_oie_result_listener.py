import unittest

from backend.runtime.oie_result_listener import OieResultListener, mllp_frame


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


if __name__ == "__main__":
    unittest.main()
