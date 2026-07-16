import json
import socket
import ssl
import unittest
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass
from unittest.mock import patch

from backend.clients.oie_management import HttpResponse, OieManagementClient, UrllibOieTransport
from backend.domain.oie_management import (
    OieErrorCategory,
    OieManagementConfig,
    OieManagementError,
    OieTlsMode,
)


@dataclass
class Step:
    status: int = 200
    body: object = None
    error: Exception | None = None


class ScriptedTransport:
    def __init__(self, *steps: Step):
        self.steps = deque(steps)
        self.requests = []
        self.clear_count = 0
        self.closed = False

    def request(self, **request):
        self.requests.append(request)
        step = self.steps.popleft()
        if step.error:
            raise step.error
        if isinstance(step.body, bytes):
            body = step.body
        elif isinstance(step.body, str):
            body = step.body.encode()
        elif step.body is None:
            body = b""
        else:
            body = json.dumps(step.body).encode()
        return HttpResponse(step.status, body)

    def clear(self):
        self.clear_count += 1

    def close(self):
        self.closed = True
        self.clear()


def client_with(*steps: Step):
    transport = ScriptedTransport(*steps)
    client = OieManagementClient(
        OieManagementConfig("https://oie.test", "admin", "password-canary", connect_timeout=2, read_timeout=9),
        transport,
    )
    return client, transport


class OieManagementClientTests(unittest.TestCase):
    def test_login_uses_form_header_and_bounded_transport_without_live_socket(self):
        client, transport = client_with(Step(body={"status": "SUCCESS"}))
        with (
            patch.object(urllib.request, "urlopen", side_effect=AssertionError("live network")),
            patch.object(socket, "create_connection", side_effect=AssertionError("live network")),
        ):
            result = client.login()

        request = transport.requests[0]
        self.assertEqual("POST", request["method"])
        self.assertEqual("https://oie.test/api/users/_login", request["url"])
        self.assertEqual("XMLHttpRequest", request["headers"]["X-Requested-With"])
        self.assertEqual("application/x-www-form-urlencoded", request["headers"]["Content-Type"])
        self.assertEqual(
            {"username": ["admin"], "password": ["password-canary"]},
            urllib.parse.parse_qs(request["body"].decode()),
        )
        self.assertEqual((2, 9), (request["connect_timeout"], request["read_timeout"]))
        self.assertNotIn("password-canary", repr(client))
        self.assertNotIn("password-canary", repr(result))

    def test_operations_require_login_and_logout_always_clears_session(self):
        client, transport = client_with()
        with self.assertRaises(OieManagementError) as raised:
            client.current_user()
        self.assertEqual(OieErrorCategory.UNAUTHENTICATED, raised.exception.category)
        self.assertEqual([], transport.requests)

        client, transport = client_with(
            Step(body={"status": "SUCCESS"}),
            Step(error=urllib.error.URLError("cookie-canary")),
        )
        client.login()
        with self.assertRaises(OieManagementError):
            client.logout()
        self.assertEqual(1, transport.clear_count)
        with self.assertRaises(OieManagementError) as raised:
            client.current_user()
        self.assertEqual(OieErrorCategory.UNAUTHENTICATED, raised.exception.category)

    def test_concrete_transport_selects_tls_policy_without_fallback(self):
        with (
            patch("backend.clients.oie_management.ssl.create_default_context", return_value="verified") as verified,
            patch("backend.clients.oie_management.ssl._create_unverified_context", return_value="local") as local,
            patch("backend.clients.oie_management.urllib.request.HTTPSHandler") as handler,
            patch("backend.clients.oie_management.urllib.request.build_opener"),
        ):
            UrllibOieTransport(OieTlsMode.VERIFIED)
            verified.assert_called_once_with()
            local.assert_not_called()
            self.assertEqual("verified", handler.call_args.kwargs["context"])

        with (
            patch("backend.clients.oie_management.ssl.create_default_context") as verified,
            patch("backend.clients.oie_management.ssl._create_unverified_context", return_value="local") as local,
            patch("backend.clients.oie_management.urllib.request.HTTPSHandler") as handler,
            patch("backend.clients.oie_management.urllib.request.build_opener"),
        ):
            UrllibOieTransport(OieTlsMode.LOCAL_SELF_SIGNED)
            local.assert_called_once_with()
            verified.assert_not_called()
            self.assertEqual("local", handler.call_args.kwargs["context"])

        with self.assertRaises(OieManagementError) as raised:
            UrllibOieTransport("verified")
        self.assertEqual(OieErrorCategory.VALIDATION, raised.exception.category)

    def test_login_status_controls_local_authentication(self):
        for status, category in (
            ("FAIL", OieErrorCategory.AUTHENTICATION),
            ("FAIL_EXPIRED", OieErrorCategory.AUTHENTICATION),
            ("FAIL_LOCKED_OUT", OieErrorCategory.AUTHENTICATION),
            ("FAIL_VERSION_MISMATCH", OieErrorCategory.UNSUPPORTED_VERSION),
            ("UNKNOWN", OieErrorCategory.UNEXPECTED_RESPONSE),
        ):
            with self.subTest(status=status):
                client, transport = client_with(Step(body={"status": status, "message": "secret-body"}))
                with self.assertRaises(OieManagementError) as raised:
                    client.login()
                self.assertEqual(category, raised.exception.category)
                self.assertEqual(1, transport.clear_count)
                with self.assertRaises(OieManagementError) as unauthenticated:
                    client.current_user()
                self.assertEqual(OieErrorCategory.UNAUTHENTICATED, unauthenticated.exception.category)

        client, _ = client_with(Step(body={"status": "SUCCESS_GRACE_PERIOD"}))
        client.login()
        self.assertIn("authenticated=True", repr(client))

    def test_read_operations_use_verified_paths_and_normalized_results(self):
        client, transport = client_with(
            Step(body={"status": "SUCCESS"}), Step(body={"id": "u1", "username": "admin"}),
            Step(body={"jvmVersion": "17", "osName": "Linux", "dbName": "PostgreSQL"}),
            Step(body="4.5.2"),
            Step(body=[{"id": "c1", "revision": 3}]),
            Step(body={"id": "c/1", "revision": 3}),
            Step(body={"channelId": "c/1", "state": "STARTED"}),
            Step(body=[{"id": "c1", "name": "Source", "port": "6661"}]),
        )
        client.login()
        self.assertEqual("u1", client.current_user().identifier)
        self.assertEqual("17", client.system_info().values["jvmVersion"])
        self.assertTrue(client.require_supported_version().supported)
        self.assertEqual("c1", client.list_channels().values["items"][0]["id"])
        self.assertEqual(3, client.get_channel("c/1").revision)
        self.assertEqual("STARTED", client.channel_status("c/1").status)
        self.assertEqual("6661", client.ports_in_use().values["items"][0]["port"])
        paths = [item["url"].removeprefix("https://oie.test/api") for item in transport.requests]
        self.assertEqual(
            ["/users/_login", "/users/current", "/system/info", "/server/version", "/channels",
             "/channels/c%2F1", "/channels/c%2F1/status", "/channels/portsInUse"], paths,
        )

    def test_mutation_shapes_preserve_safe_update_default_and_exact_primitives(self):
        client, transport = client_with(
            Step(body={"status": "SUCCESS"}), Step(body="4.5.2"),
            Step(body="true"), Step(body="true"), Step(body="true"),
            Step(), Step(), Step(), Step(),
        )
        client.login()
        client.create_channel({"id": "c1", "revision": 1})
        client.update_channel("c1", {"id": "c1", "revision": 2})
        client.update_channel("c1", {"id": "c1", "revision": 3}, override=True)
        client.delete_channel("c1")
        client.deploy("c1")
        client.redeploy("c1")
        client.undeploy("c1")
        self.assertTrue(transport.requests[1]["url"].endswith("/server/version"))
        requests = transport.requests[2:]
        self.assertEqual(["POST", "PUT", "PUT", "DELETE", "POST", "POST", "POST"], [r["method"] for r in requests])
        self.assertTrue(requests[1]["url"].endswith("/channels/c1?override=false"))
        self.assertTrue(requests[2]["url"].endswith("/channels/c1?override=true"))
        self.assertEqual("application/json", requests[0]["headers"]["Content-Type"])
        self.assertEqual(requests[4]["url"], requests[5]["url"])
        self.assertTrue(requests[6]["url"].endswith("/channels/c1/_undeploy"))

    def test_failure_categories_are_stable_and_raw_secrets_are_discarded(self):
        cases = (
            (Step(status=401), OieErrorCategory.AUTHENTICATION),
            (Step(status=403), OieErrorCategory.PERMISSION),
            (Step(status=500), OieErrorCategory.SERVER),
            (Step(error=ssl.SSLError("password-canary")), OieErrorCategory.TLS),
            (Step(error=TimeoutError("password-canary")), OieErrorCategory.TIMEOUT),
            (Step(error=urllib.error.URLError("password-canary")), OieErrorCategory.CONNECTION),
            (Step(error=urllib.error.URLError(ssl.SSLError("password-canary"))), OieErrorCategory.TLS),
            (Step(error=urllib.error.URLError(socket.timeout("password-canary"))), OieErrorCategory.TIMEOUT),
        )
        for step, category in cases:
            with self.subTest(category=category):
                client, _ = client_with(step)
                with self.assertRaises(OieManagementError) as raised:
                    client.login()
                self.assertEqual(category, raised.exception.category)
                self.assertNotIn("password-canary", str(raised.exception))
                self.assertNotIn("password-canary", repr(raised.exception))

    def test_revision_conflict_is_not_retried_or_overridden(self):
        client, transport = client_with(
            Step(body={"status": "SUCCESS"}), Step(body="4.5.2"),
            Step(status=409, body="secret-body"),
        )
        client.login()
        with self.assertRaises(OieManagementError) as raised:
            client.update_channel("c1", {"id": "c1"})
        self.assertEqual(OieErrorCategory.REVISION_CONFLICT, raised.exception.category)
        self.assertEqual(3, len(transport.requests))
        self.assertIn("override=false", transport.requests[-1]["url"])
        self.assertNotIn("secret-body", str(raised.exception))

    def test_invalid_channel_payload_maps_to_validation_without_transport_call(self):
        client, transport = client_with(Step(body={"status": "SUCCESS"}))
        client.login()
        with self.assertRaises(OieManagementError) as raised:
            client.create_channel({"bad": object()})
        self.assertEqual(OieErrorCategory.VALIDATION, raised.exception.category)
        self.assertEqual(1, len(transport.requests))

    def test_malformed_and_unsupported_responses_are_explicit(self):
        malformed_login, malformed_transport = client_with(Step(body=b"not-json"))
        with self.assertRaises(OieManagementError) as raised:
            malformed_login.login()
        self.assertEqual(OieErrorCategory.UNEXPECTED_RESPONSE, raised.exception.category)
        self.assertEqual(1, malformed_transport.clear_count)

        client, _ = client_with(Step(body={"status": "SUCCESS"}), Step(body=b"not-json"))
        client.login()
        with self.assertRaises(OieManagementError) as raised:
            client.current_user()
        self.assertEqual(OieErrorCategory.UNEXPECTED_RESPONSE, raised.exception.category)

        client, _ = client_with(Step(body={"status": "SUCCESS"}), Step(body="4.6.0"))
        client.login()
        with self.assertRaises(OieManagementError) as raised:
            client.require_supported_version()
        self.assertEqual(OieErrorCategory.UNSUPPORTED_VERSION, raised.exception.category)

    def test_unsupported_version_blocks_mutation_request(self):
        client, transport = client_with(
            Step(body={"status": "SUCCESS"}), Step(body="4.6.0"),
        )
        client.login()
        with self.assertRaises(OieManagementError) as raised:
            client.create_channel({"id": "c1", "revision": 1})
        self.assertEqual(OieErrorCategory.UNSUPPORTED_VERSION, raised.exception.category)
        self.assertEqual(2, len(transport.requests))

    def test_semantically_incomplete_success_responses_are_rejected(self):
        cases = (
            (lambda client: client.current_user(), {}),
            (lambda client: client.system_info(), {"jvmVersion": "17"}),
            (lambda client: client.get_channel("c1"), {"id": "c1"}),
            (lambda client: client.channel_status("c1"), {"channelId": "c1"}),
            (lambda client: client.list_channels(), [{"id": "c1"}]),
            (lambda client: client.ports_in_use(), [{"id": "c1", "port": "6661"}]),
        )
        for operation, body in cases:
            with self.subTest(operation=operation):
                client, _ = client_with(Step(body={"status": "SUCCESS"}), Step(body=body))
                client.login()
                with self.assertRaises(OieManagementError) as raised:
                    operation(client)
                self.assertEqual(OieErrorCategory.UNEXPECTED_RESPONSE, raised.exception.category)

    def test_public_results_recursively_redact_and_bound_unknown_payloads(self):
        client, _ = client_with(
            Step(body={"status": "SUCCESS", "sessionToken": "login-token-canary"}),
            Step(body={
                "id": "u1",
                "username": "admin",
                "password": "password-canary",
                "nested": {"authorizationValue": "authorization-canary"},
                "description": "x" * 700,
            }),
        )
        login = client.login()
        result = client.current_user()
        public = repr((login, result))
        for secret in ("login-token-canary", "password-canary", "authorization-canary"):
            self.assertNotIn(secret, public)
        self.assertIn("[REDACTED]", public)
        self.assertIn("[TRUNCATED]", public)

    def test_clients_are_isolated_and_close_is_idempotent(self):
        first, first_transport = client_with(Step(body={"status": "SUCCESS"}), Step())
        second, second_transport = client_with(Step(body={"status": "SUCCESS"}), Step())
        first.login()
        second.login()
        first.close()
        first.close()
        second.close()
        self.assertIsNot(first_transport, second_transport)
        self.assertTrue(first_transport.closed)
        self.assertEqual(2, first_transport.clear_count)
        self.assertEqual(2, second_transport.clear_count)

    def test_cleanup_log_does_not_expose_remote_exception(self):
        client, _ = client_with(
            Step(body={"status": "SUCCESS"}),
            Step(error=urllib.error.URLError("cookie-and-password-canary")),
        )
        client.login()
        with self.assertLogs("backend.clients.oie_management", level="DEBUG") as captured:
            client.close()
        self.assertNotIn("cookie-and-password-canary", " ".join(captured.output))


if __name__ == "__main__":
    unittest.main()
