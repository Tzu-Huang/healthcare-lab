import socket
import unittest
from types import SimpleNamespace

from backend.services.dcm4chee_diagnostics import (
    Dcm4cheeDiagnostics,
    diagnose_dcm4chee,
)


def profile():
    return {
        "webUiUrl": "http://browser.example/archive",
        "dicomweb": {"qidoRsUrl": "http://archive.internal/rs"},
        "hl7": {"host": "archive.internal", "port": 2575},
        "dimse": {"host": "archive.internal", "port": 11112},
        "security": {
            "password": "PASSWORD-CANARY",
            "token": "TOKEN-CANARY",
            "privateKeyPath": "PRIVATE-KEY-PATH-CANARY",
        },
    }


class Connection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class Dcm4cheeDiagnosticsTest(unittest.TestCase):
    def test_all_checks_are_independent_bounded_and_healthy(self):
        http_calls = []
        tcp_calls = []
        connections = []

        def http_probe(url, timeout):
            http_calls.append((url, timeout))
            return {"status": 200, "body": b"[]"}

        def tcp_probe(host, port, timeout):
            tcp_calls.append((host, port, timeout))
            connection = Connection()
            connections.append(connection)
            return connection

        report = diagnose_dcm4chee(
            profile(), timeout_seconds=0.25, http_probe=http_probe, tcp_probe=tcp_probe
        )

        self.assertEqual("healthy", report["state"])
        self.assertEqual(
            [
                ("web-ui-http", "http-reachable"),
                ("qido-rs", "metadata-reachable"),
                ("hl7-tcp", "transport-reachable"),
                ("dimse-tcp", "transport-reachable"),
            ],
            [(item["role"], item["code"]) for item in report["checks"]],
        )
        self.assertTrue(all(call[1] == 0.25 for call in http_calls))
        self.assertTrue(all(call[2] == 0.25 for call in tcp_calls))
        self.assertIn("/studies?limit=1", http_calls[1][0])
        self.assertTrue(all(connection.closed for connection in connections))

    def test_partial_failures_and_timeouts_preserve_every_result(self):
        http_call = 0
        tcp_call = 0

        def http_probe(_url, _timeout):
            nonlocal http_call
            http_call += 1
            if http_call == 1:
                return {"status": 503, "body": b"upstream secret"}
            raise TimeoutError("TOKEN-CANARY")

        def tcp_probe(_host, _port, _timeout):
            nonlocal tcp_call
            tcp_call += 1
            if tcp_call == 1:
                raise socket.timeout("PATIENT-CANARY")
            return Connection()

        report = Dcm4cheeDiagnostics(
            profile(), http_probe=http_probe, tcp_probe=tcp_probe
        ).run()

        self.assertEqual("degraded", report["state"])
        self.assertEqual(4, len(report["checks"]))
        self.assertEqual(
            ["http-error", "timed-out", "timed-out", "transport-reachable"],
            [item["code"] for item in report["checks"]],
        )
        rendered = str(report)
        for canary in ("upstream secret", "TOKEN-CANARY", "PATIENT-CANARY"):
            self.assertNotIn(canary, rendered)

    def test_qido_requires_json_list_metadata_and_does_not_return_payload(self):
        def http_probe(url, _timeout):
            if "/studies" not in url:
                return {"status": 200, "body": b""}
            return {"status": 200, "body": b'{"PatientName":"PHI-CANARY"}'}

        report = diagnose_dcm4chee(
            profile(), http_probe=http_probe, tcp_probe=lambda *_args: Connection()
        )

        qido = report["checks"][1]
        self.assertEqual(
            {"role": "qido-rs", "state": "failed", "code": "invalid-response"},
            qido,
        )
        self.assertNotIn("PHI-CANARY", str(report))

    def test_missing_or_invalid_endpoints_are_value_free(self):
        report = diagnose_dcm4chee(
            {
                "webUiUrl": "",
                "dicomweb": {},
                "hl7": {"host": "SECRET-HOST", "port": "bad"},
                "dimse": {"host": "", "port": 70000},
            },
            http_probe=lambda *_args: self.fail("HTTP probe must not run"),
            tcp_probe=lambda *_args: self.fail("TCP probe must not run"),
        )

        self.assertEqual("degraded", report["state"])
        self.assertTrue(
            all(item["code"] == "not-configured" for item in report["checks"])
        )
        self.assertNotIn("SECRET-HOST", str(report))

    def test_object_profile_and_call_time_profile_are_supported(self):
        object_profile = SimpleNamespace(
            webUiUrl="http://browser.example",
            dicomweb=SimpleNamespace(qidoRsUrl="http://archive.example/rs/studies"),
            hl7=SimpleNamespace(host="hl7.example", port=2575),
            dimse=SimpleNamespace(host="dimse.example", port=11112),
        )
        seen_urls = []

        service = Dcm4cheeDiagnostics(
            http_probe=lambda url, _timeout: (
                seen_urls.append(url) or {"status": 200, "body": b"[]"}
            ),
            tcp_probe=lambda *_args: Connection(),
        )
        report = service.run(object_profile)

        self.assertEqual("healthy", report["state"])
        self.assertEqual(1, seen_urls[1].count("/studies"))

    def test_tcp_success_only_claims_transport_reachability(self):
        report = diagnose_dcm4chee(
            profile(),
            http_probe=lambda *_args: {"status": 200, "body": b"[]"},
            tcp_probe=lambda *_args: Connection(),
        )

        tcp_results = report["checks"][2:]
        self.assertEqual(
            ["transport-reachable", "transport-reachable"],
            [item["code"] for item in tcp_results],
        )
        rendered = str(tcp_results).lower()
        self.assertNotIn("protocol", rendered)
        self.assertNotIn("hl7-success", rendered)
        self.assertNotIn("dicom-success", rendered)

    def test_results_do_not_expose_profile_or_exception_canaries(self):
        def explode(*_args):
            raise OSError("PASSWORD-CANARY TOKEN-CANARY PRIVATE-KEY-PATH-CANARY")

        report = diagnose_dcm4chee(
            profile(), http_probe=explode, tcp_probe=explode
        )

        self.assertEqual("degraded", report["state"])
        rendered = str(report)
        for canary in (
            "PASSWORD-CANARY",
            "TOKEN-CANARY",
            "PRIVATE-KEY-PATH-CANARY",
            "browser.example",
            "archive.internal",
        ):
            self.assertNotIn(canary, rendered)


if __name__ == "__main__":
    unittest.main()
