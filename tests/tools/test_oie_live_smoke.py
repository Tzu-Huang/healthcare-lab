import socket
import unittest
from unittest.mock import patch

from tools.oie_live_smoke import main, parse_ack, poll_diagnostics, safe_error, tcp_probe


class OieLiveSmokeTests(unittest.TestCase):
    def test_parse_ack_reports_code_and_hash_without_raw_hl7(self):
        result = parse_ack(b"\x0bMSH|^~\\&|OIE\rMSA|AA|sensitive-control-id\x1c\x0d")
        self.assertEqual("pass", result["classification"])
        self.assertEqual("AA", result["ackCode"])
        self.assertNotIn("sensitive-control-id", str(result))
        self.assertEqual(12, len(result["controlIdHash"]))

    def test_parse_ack_classifies_negative_and_malformed_responses(self):
        self.assertEqual("fail", parse_ack(b"MSA|AE|id")["classification"])
        self.assertEqual("fail", parse_ack(b"not an ack")["classification"])

    def test_safe_error_redacts_socket_details(self):
        result = safe_error(OSError("failed for admin:secret@private-host/path"))
        self.assertNotIn("secret", result)
        self.assertEqual("OSError", result)

    @patch("tools.oie_live_smoke.socket.create_connection")
    def test_tcp_probe_classifies_timeout_as_blocked(self, connect):
        connect.side_effect = socket.timeout("private endpoint")
        result = tcp_probe("private-host", 6600, 0.01)
        self.assertEqual("blocked", result["classification"])
        self.assertNotIn("private-host", str(result))

    def test_poll_diagnostics_returns_degraded_as_failure(self):
        result = poll_diagnostics(
            "http://unused",
            0.1,
            0,
            fetch=lambda _url, _timeout: {"item": {"state": "degraded", "probes": [{"secret": "ignored"}]}},
        )
        self.assertEqual({"classification": "fail", "detail": "diagnostics available", "state": "degraded"}, result)

    def test_poll_diagnostics_uses_explicit_deadline(self):
        result = poll_diagnostics("http://unused", 0.002, 0, fetch=lambda *_args: {})
        self.assertEqual("blocked", result["classification"])
        self.assertEqual("diagnostics polling timed out", result["detail"])

    @patch("tools.oie_live_smoke.tcp_probe")
    def test_optional_probes_do_not_fail_preflight_when_omitted(self, probe):
        probe.return_value = {"classification": "pass", "detail": "TCP reachable", "elapsedMs": 1}

        self.assertEqual(0, main(["--host", "oie", "--hlab-host", "lab-app"]))
        self.assertIn(("lab-app", 6665, 3.0), [call.args for call in probe.call_args_list])


if __name__ == "__main__":
    unittest.main()
