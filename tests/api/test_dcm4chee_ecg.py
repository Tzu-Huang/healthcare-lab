from __future__ import annotations

import unittest

from flask import Flask

from backend.api.dcm4chee_ecg import create_dcm4chee_ecg_blueprint
from backend.services.dcm4chee_ecg import (
    Dcm4cheeEcgConflictError,
    Dcm4cheeEcgInvalidError,
    Dcm4cheeEcgNotFoundError,
    Dcm4cheeEcgUnsupportedError,
    Dcm4cheeEcgUpstreamError,
)


class _Service:
    def __init__(self, error=None):
        self.error = error

    def metadata(self, result_id):
        if self.error:
            raise self.error
        return {"result": {"id": result_id}}

    def render(self, _result_id):
        if self.error:
            raise self.error
        return type(
            "Rendered", (), {"svg_bytes": b"<svg/>", "media_type": "image/svg+xml"}
        )()


class Dcm4cheeEcgApiTests(unittest.TestCase):
    @staticmethod
    def client(service):
        app = Flask(__name__)
        app.register_blueprint(create_dcm4chee_ecg_blueprint(service))
        return app.test_client()

    def test_metadata_and_svg_routes_have_stable_success_shapes(self):
        client = self.client(_Service())

        metadata = client.get("/api/dcm4chee/results/7/ecg")
        graph = client.get("/api/dcm4chee/results/7/ecg/render.svg")

        self.assertEqual(200, metadata.status_code)
        self.assertEqual(7, metadata.get_json()["item"]["result"]["id"])
        self.assertEqual(200, graph.status_code)
        self.assertEqual("image/svg+xml", graph.mimetype)
        self.assertEqual(b"<svg/>", graph.data)

    def test_typed_errors_are_safe_and_stable(self):
        cases = (
            (Dcm4cheeEcgNotFoundError(), 404),
            (Dcm4cheeEcgConflictError(), 409),
            (Dcm4cheeEcgUnsupportedError(), 415),
            (Dcm4cheeEcgInvalidError(), 422),
            (Dcm4cheeEcgUpstreamError(), 502),
        )
        for error, status in cases:
            with self.subTest(status=status):
                response = self.client(_Service(error)).get(
                    "/api/dcm4chee/results/7/ecg"
                )
                body = response.get_data(as_text=True)
                self.assertEqual(status, response.status_code)
                self.assertFalse(response.get_json()["success"])
                self.assertEqual(error.code, response.get_json()["error"]["code"])
                for forbidden in ("http://", "PatientName", "password", "token"):
                    self.assertNotIn(forbidden, body)

    def test_public_routes_do_not_accept_url_or_path_selectors(self):
        client = self.client(_Service())

        self.assertEqual(
            404,
            client.get("/api/dcm4chee/results/https://attacker/ecg").status_code,
        )
        response = client.get(
            "/api/dcm4chee/results/7/ecg",
            query_string={"url": "http://attacker", "path": "../../secret"},
        )
        self.assertEqual(200, response.status_code)
        self.assertNotIn("attacker", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
