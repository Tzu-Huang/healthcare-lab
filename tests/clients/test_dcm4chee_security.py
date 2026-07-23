from __future__ import annotations

import base64
import unittest
from unittest.mock import patch

from backend.clients.dcm4chee import request_dcm4chee_qido
from backend.services.integration_settings import Dcm4cheeRuntimeProfile


class _Response:
    status = 200

    def __init__(self, body=b"[]"):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


def _profile(mode, secrets):
    return Dcm4cheeRuntimeProfile(
        {
            "dicomweb": {"baseUrl": "https://archive.example/rs", "qidoRsUrl": "https://archive.example/rs"},
            "security": {
                "authMode": mode,
                "username": "client",
                "tokenUrl": "https://identity.example/token",
                "tlsEnabled": False,
                "tlsVerify": True,
                "certificatePath": "",
                "privateKeyPath": "",
            },
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


if __name__ == "__main__":
    unittest.main()
