from __future__ import annotations

import base64
import unittest
from unittest.mock import Mock, patch

from backend.clients.dcm4chee import request_dcm4chee_qido
from backend.domain.errors import UpstreamDcm4cheeError
from backend.services.dcm4chee_diagnostics import diagnose_dcm4chee
from backend.services.integration_settings import Dcm4cheeRuntimeProfile


class _Response:
    status = 200

    def __init__(self, body=b"[]"):
        self._body = body

    def read(self, *_args):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


def _profile(mode, secrets, *, tls_enabled=False):
    return Dcm4cheeRuntimeProfile(
        {
            "dicomweb": {"baseUrl": "https://archive.example/rs", "qidoRsUrl": "https://archive.example/rs"},
            "security": {
                "authMode": mode,
                "username": "client",
                "tokenUrl": "https://identity.example/token",
                "tlsEnabled": tls_enabled,
                "tlsVerify": True,
                "certificatePath": "C:/mounted/certificate-canary.pem" if tls_enabled else "",
                "privateKeyPath": "C:/mounted/private-key-canary.pem" if tls_enabled else "",
            },
            "webUiUrl": "https://archive.example/ui",
            "hl7": {"host": "archive.example", "port": 2575},
            "dimse": {"host": "archive.example", "port": 11112},
        },
        secrets,
    )


class Dcm4cheeSecurityTests(unittest.TestCase):
    @patch("backend.clients.dcm4chee.urllib.request.urlopen")
    def test_basic_and_bearer_are_applied_to_real_qido_requests(self, urlopen):
        urlopen.return_value = _Response()
        for mode, secrets, expected in (
            ("basic", {"password": "secret"}, "Basic " + base64.b64encode(b"client:secret").decode()),
            ("bearer", {"token": "token-canary"}, "Bearer token-canary"),
        ):
            with self.subTest(mode=mode):
                request_dcm4chee_qido(_profile(mode, secrets), "studies")
                self.assertEqual(expected, urlopen.call_args.args[0].get_header("Authorization"))

    @patch("backend.clients.dcm4chee.urllib.request.urlopen")
    def test_oauth_client_credentials_are_exchanged_then_applied(self, urlopen):
        urlopen.side_effect = [_Response(b'{"access_token":"access-token"}'), _Response()]
        profile = _profile("oauth2", {"clientSecret": "client-secret-canary"})
        request_dcm4chee_qido(profile, "studies")
        token_request = urlopen.call_args_list[0].args[0]
        qido_request = urlopen.call_args_list[1].args[0]
        self.assertEqual("Basic " + base64.b64encode(b"client:client-secret-canary").decode(), token_request.get_header("Authorization"))
        self.assertEqual("Bearer access-token", qido_request.get_header("Authorization"))
        self.assertNotIn("client-secret-canary", repr(profile))
        self.assertNotIn("client-secret-canary", repr(dict(profile)))

    @patch("backend.clients.dcm4chee.urllib.request.urlopen")
    @patch("backend.clients.dcm4chee.ssl.create_default_context")
    def test_mtls_loads_certificate_chain_and_passes_context(self, create_context, urlopen):
        context = Mock()
        create_context.return_value = context
        urlopen.return_value = _Response()
        profile = _profile("mtls", {}, tls_enabled=True)

        request_dcm4chee_qido(profile, "studies")

        context.load_cert_chain.assert_called_once_with(
            "C:/mounted/certificate-canary.pem",
            "C:/mounted/private-key-canary.pem",
        )
        self.assertIs(context, urlopen.call_args.kwargs["context"])

    @patch("backend.clients.dcm4chee.ssl.create_default_context")
    def test_tls_setup_failure_is_bounded_and_path_free(self, create_context):
        context = Mock()
        context.load_cert_chain.side_effect = OSError(
            "cannot read C:/mounted/private-key-canary.pem"
        )
        create_context.return_value = context

        with self.assertRaises(UpstreamDcm4cheeError) as raised:
            request_dcm4chee_qido(_profile("mtls", {}, tls_enabled=True), "studies")

        rendered = str(raised.exception)
        self.assertIn("TLS configuration is invalid", rendered)
        self.assertNotIn("private-key-canary", rendered)
        self.assertNotIn("cannot read", rendered)

    @patch("backend.clients.dcm4chee.urllib.request.urlopen")
    def test_default_diagnostics_http_transport_uses_runtime_auth(self, urlopen):
        urlopen.side_effect = [_Response(b""), _Response(b"[]")]
        profile = _profile("basic", {"password": "diagnostic-secret"})

        report = diagnose_dcm4chee(
            profile,
            tcp_probe=lambda *_args: _Response(),
        )

        self.assertEqual("healthy", report["state"])
        expected = "Basic " + base64.b64encode(b"client:diagnostic-secret").decode()
        self.assertEqual(
            [expected, expected],
            [
                call.args[0].get_header("Authorization")
                for call in urlopen.call_args_list
            ],
        )
        self.assertNotIn("diagnostic-secret", repr(report))


if __name__ == "__main__":
    unittest.main()
