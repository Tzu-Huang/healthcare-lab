import unittest

from flask import Flask

from backend.api.oie import create_oie_blueprint
from backend.lab_store import SimulatorValidationError


class FakeService:
    def get_profile(self):
        return {"profileName": "local-oie"}

    def update_profile(self, payload):
        if not isinstance(payload, dict):
            raise SimulatorValidationError("OIE settings payload must be a JSON object.")
        return {"profileName": "local-oie", "updated": True}


class OieSettingsBlueprintTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(OIE_MLLP_RESULT_HOST="0.0.0.0", OIE_MLLP_RESULT_PORT=6665, OIE_MLLP_ORDER_HOST="localhost", OIE_MLLP_ORDER_PORT=6600)
        app.extensions["oie_result_listener"] = type("Listener", (), {"status": lambda self: {}, "stop": lambda self: {}})()
        store = type("Store", (), {})()
        app.register_blueprint(create_oie_blueprint(
            app, store, FakeService(), result_handler=lambda _store, _payload: ("ACK", {}, 200),
            ack_parser=lambda _payload: {}, order_sender_provider=lambda: lambda *_args, **_kwargs: "",
        ))
        self.client = app.test_client()

    def test_get_preserves_response_shape(self):
        response = self.client.get("/api/oie/settings")

        self.assertEqual(200, response.status_code)
        self.assertEqual("local-oie", response.get_json()["item"]["profileName"])

    def test_invalid_update_maps_validation_error_to_400(self):
        response = self.client.put("/api/oie/settings", data="null", content_type="application/json")

        self.assertEqual(400, response.status_code)
        self.assertFalse(response.get_json()["success"])


if __name__ == "__main__":
    unittest.main()
