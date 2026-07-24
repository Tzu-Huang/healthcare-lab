import unittest

from flask import Flask

from backend.api.ap_device_profiles import create_ap_device_profiles_blueprint


class _Service:
    def __init__(self):
        self.items = []

    def list(self, environment=None):
        return [item for item in self.items if environment is None or item["environment"] == environment]

    def create(self, payload):
        item = {"id": "ap-1", **payload}
        self.items.append(item)
        return item

    def update(self, profile_id, payload):
        if profile_id != "ap-1":
            raise KeyError(profile_id)
        self.items[0].update(payload)
        return self.items[0]

    def get(self, profile_id):
        if profile_id != "ap-1":
            raise KeyError(profile_id)
        return self.items[0]

    def select_default(self, profile_id):
        if profile_id != "ap-1":
            raise KeyError(profile_id)
        self.items[0]["isDefault"] = True
        return self.items[0]

    def diagnose(self, profile_id):
        if profile_id != "ap-1":
            raise KeyError(profile_id)
        return {"state": "healthy", "checks": []}


class APDeviceProfilesApiTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(create_ap_device_profiles_blueprint(_Service()))
        self.client = app.test_client()

    def test_crud_default_and_diagnostics_contract(self):
        payload = {
            "name": "Main AP", "environment": "lab", "enabled": True,
            "isDefault": False, "metadata": {}, "hl7": {"enabled": False},
            "gdt": {"enabled": False}, "dicom": {"enabled": False},
        }
        self.assertEqual(
            self.client.post("/api/settings/external-devices", json=payload).status_code,
            201,
        )
        self.assertEqual(
            self.client.get("/api/settings/external-devices?environment=lab").get_json()["items"][0]["id"],
            "ap-1",
        )
        self.assertEqual(
            self.client.get("/api/settings/external-devices/ap-1").get_json()["item"]["name"],
            "Main AP",
        )
        self.assertTrue(
            self.client.put("/api/settings/external-devices/ap-1/default", json={}).get_json()["item"]["isDefault"]
        )
        self.assertEqual(
            self.client.post("/api/settings/external-devices/ap-1/diagnostics", json={}).get_json()["state"],
            "healthy",
        )

    def test_unknown_profile_is_value_safe(self):
        response = self.client.put("/api/settings/external-devices/missing", json={})
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("missing", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
