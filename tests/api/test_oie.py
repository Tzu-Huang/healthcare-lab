import unittest

from flask import Flask

from backend.api.oie import create_oie_blueprint
from backend.domain.errors import SimulatorValidationError
from backend.domain.oie_management import OieErrorCategory, OieManagementError
from backend.services.oie_settings import OieSettingsUpdateResult


class FakeService:
    def get_profile(self):
        return {"profileName": "local-oie"}

    def update_profile(self, payload):
        if not isinstance(payload, dict):
            raise SimulatorValidationError("OIE settings payload must be a JSON object.")
        return OieSettingsUpdateResult(
            profile={"profileName": "local-oie", "updated": True},
            runtime_reload_required=True,
        )

    def test_connection(self):
        return {
            "status": "connected",
            "version": "4.5.2",
            "currentUser": "admin",
            "tlsMode": "verified",
            "testedAt": "2026-07-21T02:00:00Z",
        }


class FakeWorkflow:
    pass


class OieSettingsBlueprintTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(create_oie_blueprint(FakeService(), FakeWorkflow()))
        self.client = app.test_client()

    def test_get_preserves_response_shape(self):
        response = self.client.get("/api/oie/settings")

        self.assertEqual(200, response.status_code)
        self.assertEqual("local-oie", response.get_json()["item"]["profileName"])

    def test_invalid_update_maps_validation_error_to_400(self):
        response = self.client.put("/api/oie/settings", data="null", content_type="application/json")

        self.assertEqual(400, response.status_code)
        self.assertFalse(response.get_json()["success"])

    def test_update_exposes_runtime_reload_requirement_outside_profile(self):
        response = self.client.put("/api/oie/settings", json={"managementApi": {}})

        self.assertEqual(200, response.status_code)
        self.assertTrue(response.get_json()["runtimeReloadRequired"])
        self.assertNotIn("runtimeReloadRequired", response.get_json()["item"])

    def test_connection_uses_saved_settings_and_returns_bounded_projection(self):
        response = self.client.post("/api/oie/settings/test-connection", json={})

        self.assertEqual(200, response.status_code)
        self.assertEqual("connected", response.get_json()["item"]["status"])
        self.assertEqual("4.5.2", response.get_json()["item"]["version"])
        self.assertNotIn("password", response.get_data(as_text=True).lower())

    def test_connection_rejects_request_overrides(self):
        response = self.client.post(
            "/api/oie/settings/test-connection", json={"password": "do-not-use"}
        )

        self.assertEqual(400, response.status_code)
        self.assertNotIn("do-not-use", response.get_data(as_text=True))

    def test_connection_maps_safe_oie_failure_category(self):
        class FailingService(FakeService):
            def test_connection(self):
                raise OieManagementError(
                    OieErrorCategory.AUTHENTICATION,
                    "OIE rejected the configured credentials.",
                )

        app = Flask(__name__)
        app.register_blueprint(create_oie_blueprint(FailingService(), FakeWorkflow()))
        response = app.test_client().post("/api/oie/settings/test-connection", json={})

        self.assertEqual(502, response.status_code)
        self.assertEqual("authentication", response.get_json()["errorCategory"])
        self.assertNotIn("password", response.get_data(as_text=True).lower())


if __name__ == "__main__":
    unittest.main()
