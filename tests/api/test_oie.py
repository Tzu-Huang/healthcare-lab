import unittest

from flask import Flask

from backend.api.oie import create_oie_blueprint
from backend.domain.errors import SimulatorValidationError
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


if __name__ == "__main__":
    unittest.main()
