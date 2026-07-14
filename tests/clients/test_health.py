import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from backend.clients.health import run_http_smoke, run_lab_application_check, run_tcp_smoke


class HealthClientTest(unittest.TestCase):
    @patch("backend.clients.health.urllib.request.urlopen")
    def test_http_smoke_treats_client_response_as_reachable(self, urlopen):
        urlopen.side_effect = urllib.error.HTTPError(
            "http://service.test", 404, "missing", {}, None
        )

        result = run_http_smoke("http://service.test", "service", required=False)

        self.assertEqual("Healthy", result["status"])
        self.assertEqual("HTTP 404", result["message"])
        self.assertFalse(result["required"])

    @patch("backend.clients.health.urllib.request.urlopen")
    def test_application_check_falls_back_to_tcp(self, urlopen):
        urlopen.side_effect = urllib.error.URLError("offline")
        connection = MagicMock()
        connection.__enter__.return_value = connection
        with patch("backend.clients.health.socket.create_connection", return_value=connection) as connect:
            status, message = run_lab_application_check(
                {
                    "baseUrl": "http://lab.test",
                    "host": "lab.test",
                    "port": "2575",
                    "operation": {},
                }
            )

        self.assertEqual(("Healthy", ""), (status, message))
        connect.assert_called_once_with(("lab.test", 2575), 2.0)

    def test_tcp_smoke_rejects_invalid_port_and_preserves_required_flag(self):
        result = run_tcp_smoke("lab.test", "not-a-port", "mllp", required=False)

        self.assertEqual("Down", result["status"])
        self.assertIn("integer", result["message"])
        self.assertFalse(result["required"])


if __name__ == "__main__":
    unittest.main()
