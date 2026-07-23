import json
import unittest
from unittest.mock import patch

from backend.clients.medplum import (
    MedplumAuthManager,
    normalize_fhir_base_url,
    request_fhir_json,
)


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class MedplumClientTest(unittest.TestCase):
    def test_normalize_fhir_base_url(self):
        self.assertEqual("https://example.test/fhir/R4", normalize_fhir_base_url(" https://example.test/fhir/R4/ "))

    def test_auth_status_does_not_expose_secret(self):
        manager = MedplumAuthManager(client_id="client-1234", client_secret="secret")

        status = manager.status("https://example.test/fhir/R4")

        self.assertTrue(status["configured"])
        self.assertEqual("1234", status["clientIdSuffix"])
        self.assertNotIn("secret", str(status))

    @patch("backend.clients.medplum.urllib.request.urlopen")
    def test_request_fhir_json_maps_successful_response(self, urlopen):
        urlopen.return_value = FakeResponse({"resourceType": "Bundle"})

        status, payload = request_fhir_json("https://example.test/fhir/R4/Patient", "token")

        self.assertEqual(200, status)
        self.assertEqual("Bundle", payload["resourceType"])
        request = urlopen.call_args.args[0]
        self.assertEqual("Bearer token", request.headers["Authorization"])

    @patch("backend.clients.medplum.urllib.request.urlopen")
    def test_auth_and_fhir_requests_use_configured_timeout(self, urlopen):
        urlopen.side_effect = [
            FakeResponse({"access_token": "token", "token_type": "Bearer", "expires_in": 60}),
            FakeResponse({"resourceType": "Bundle"}),
        ]
        manager = MedplumAuthManager(
            client_id="client", client_secret="secret", timeout_seconds=7
        )

        request_fhir_json(
            "https://example.test/fhir/R4/Patient",
            "",
            auth_manager=manager,
            base_url="https://example.test/fhir/R4",
        )

        self.assertEqual([7, 7], [call.kwargs["timeout"] for call in urlopen.call_args_list])

    @patch("backend.clients.medplum.urllib.request.urlopen")
    def test_explicit_fhir_timeout_overrides_auth_manager_timeout(self, urlopen):
        urlopen.return_value = FakeResponse({"resourceType": "Bundle"})
        manager = MedplumAuthManager(
            client_id="client", client_secret="secret", timeout_seconds=7
        )

        request_fhir_json(
            "https://example.test/fhir/R4/Patient",
            "token",
            auth_manager=None,
            timeout_seconds=3,
        )

        self.assertEqual(3, urlopen.call_args.kwargs["timeout"])


if __name__ == "__main__":
    unittest.main()
