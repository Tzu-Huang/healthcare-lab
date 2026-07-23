from __future__ import annotations

import unittest

from flask import Flask

from backend.api.settings_readiness import create_settings_readiness_blueprint


class _Service:
    def get_readiness(self):
        return {"complete": True, "nextAction": None, "sections": []}

    def run_checks(self):
        return {"summary": "Checks completed.", "results": []}


class _FailingService:
    def get_readiness(self):
        raise RuntimeError("secret-canary patient-canary")

    def run_checks(self):
        raise RuntimeError("secret-canary patient-canary")


class SettingsReadinessApiTests(unittest.TestCase):
    def _client(self, service):
        app = Flask(__name__)
        app.register_blueprint(create_settings_readiness_blueprint(service))
        return app.test_client()

    def test_returns_stable_success_envelope(self):
        response = self._client(_Service()).get("/api/settings/readiness")
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "success": True,
                "item": {"complete": True, "nextAction": None, "sections": []},
            },
            response.get_json(),
        )

    def test_failure_is_value_free(self):
        response = self._client(_FailingService()).get("/api/settings/readiness")
        self.assertEqual(503, response.status_code)
        self.assertEqual(
            "settings_readiness_unavailable", response.get_json()["error"]["code"]
        )
        body = response.get_data(as_text=True)
        self.assertNotIn("secret-canary", body)
        self.assertNotIn("patient-canary", body)

    def test_checks_use_stable_secret_safe_envelope(self):
        response = self._client(_Service()).post("/api/settings/readiness/checks")
        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.get_json()["item"]["results"])

        failed = self._client(_FailingService()).post(
            "/api/settings/readiness/checks"
        )
        self.assertEqual(503, failed.status_code)
        body = failed.get_data(as_text=True)
        self.assertNotIn("secret-canary", body)
        self.assertNotIn("patient-canary", body)
