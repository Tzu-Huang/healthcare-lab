import unittest
from flask import Flask

from backend.api.oie import create_oie_blueprint


class Diagnostics:
    def diagnose(self):
        return {"state": "degraded", "observedAt": "2026-07-21T04:05:06Z", "probes": []}


class OieDiagnosticsApiTests(unittest.TestCase):
    def test_endpoint_exposes_only_diagnostic_projection(self):
        app = Flask(__name__)
        app.register_blueprint(create_oie_blueprint(object(), object(), diagnostics=Diagnostics()))
        response = app.test_client().get("/api/oie/settings/diagnostics")
        self.assertEqual(200, response.status_code)
        self.assertEqual("degraded", response.get_json()["item"]["state"])


if __name__ == "__main__":
    unittest.main()
