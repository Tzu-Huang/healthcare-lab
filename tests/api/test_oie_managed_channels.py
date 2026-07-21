import unittest
from flask import Flask

from backend.api.oie import create_oie_blueprint
from backend.services.oie_channel_lifecycle import LifecycleGuardError


class Lifecycle:
    def __init__(self): self.calls = []
    def inspect(self): self.calls.append(("inspect",)); return [{"logicalType": "hlab-orm-to-ap", "classification": "missing"}]
    def preview(self, logical_type, operation): self.calls.append(("preview", logical_type, operation)); return {"permitted": True, "previewToken": "opaque"}
    def execute(self, logical_type, operation, token, *, confirmation=""):
        self.calls.append(("execute", logical_type, operation, token, confirmation))
        return {"outcome": "success", "steps": [], "operationId": "op-1"}


class Settings:
    def get_profile(self): return {}
class Workflow: pass


class ManagedChannelApiTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__); self.lifecycle = Lifecycle()
        app.register_blueprint(create_oie_blueprint(Settings(), Workflow(), self.lifecycle)); self.client = app.test_client()

    def test_inspection_preview_and_single_target_mutation(self):
        self.assertEqual(200, self.client.get("/api/oie/managed-channels").status_code)
        preview = self.client.post("/api/oie/managed-channels/hlab-orm-to-ap/previews/create", json={})
        self.assertEqual("opaque", preview.get_json()["item"]["previewToken"])
        mutation = self.client.post("/api/oie/managed-channels/hlab-orm-to-ap/create", json={"previewToken": "opaque"})
        self.assertEqual(200, mutation.status_code)
        self.assertEqual(("execute", "hlab-orm-to-ap", "create", "opaque", ""), self.lifecycle.calls[-1])

    def test_yolo_options_are_rejected_before_service(self):
        for body in ({"previewToken": "x", "force": True}, {"previewToken": "x", "override": True}, {"previewToken": "x", "targets": ["*"]}):
            with self.subTest(body=body): self.assertEqual(400, self.client.post("/api/oie/managed-channels/hlab-orm-to-ap/update", json=body).status_code)
        self.assertFalse(any(call[0] == "execute" for call in self.lifecycle.calls))

    def test_delete_requires_service_confirmation_contract(self):
        self.lifecycle.execute = lambda *args, **kwargs: (_ for _ in ()).throw(LifecycleGuardError("confirmation-mismatch", "match logical type"))
        response = self.client.post("/api/oie/managed-channels/hlab-orm-to-ap/delete", json={"previewToken": "x", "confirmation": "yes"})
        self.assertEqual(400, response.status_code)

    def test_stale_preview_maps_to_conflict_without_leaking_payload(self):
        self.lifecycle.execute = lambda *args, **kwargs: (_ for _ in ()).throw(LifecycleGuardError("stale-preview", "refresh", fresh=True))
        response = self.client.post("/api/oie/managed-channels/hlab-orm-to-ap/update", json={"previewToken": "x"})
        self.assertEqual(409, response.status_code); self.assertTrue(response.get_json()["requiresFreshPreview"])

    def test_route_map_has_no_bulk_force_adopt_or_redeploy(self):
        routes = " ".join(str(rule) for rule in self.client.application.url_map.iter_rules())
        for forbidden in ("bulk", "force", "adopt", "redeploy"): self.assertNotIn(forbidden, routes.lower())


if __name__ == "__main__": unittest.main()
