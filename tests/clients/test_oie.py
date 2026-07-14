import unittest
from unittest.mock import patch

from backend.clients.oie import send_hl7_mllp_message


class FakeConnection:
    def __init__(self, response: bytes) -> None:
        self._chunks = [response, b""]
        self.sent = b""
        self.timeout = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def settimeout(self, timeout):
        self.timeout = timeout

    def sendall(self, payload):
        self.sent = payload

    def recv(self, _size):
        return self._chunks.pop(0)


class OieClientTest(unittest.TestCase):
    @patch("backend.clients.oie.socket.create_connection")
    def test_framed_message_round_trip(self, create_connection):
        connection = FakeConnection(b"\x0bMSH|ACK\x1c\x0d")
        create_connection.return_value = connection

        response = send_hl7_mllp_message(
            "MSH|ORDER", host="oie", port=6600, timeout_seconds=3
        )

        self.assertEqual("MSH|ACK", response)
        self.assertEqual(b"\x0bMSH|ORDER\x1c\x0d", connection.sent)
        self.assertEqual(3, connection.timeout)


if __name__ == "__main__":
    unittest.main()
