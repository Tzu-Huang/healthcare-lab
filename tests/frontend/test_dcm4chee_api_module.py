from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Dcm4cheeApiModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "frontend/static/js/api/dcm4chee.js").read_text(encoding="utf-8")
        cls.bootstrap = (ROOT / "frontend/static/app.js").read_text(encoding="utf-8")
        cls.view = (ROOT / "frontend/static/js/views/dcm4chee.js").read_text(encoding="utf-8")
        cls.order_api = (ROOT / "frontend/static/js/api/order.js").read_text(encoding="utf-8")

    def test_dcm4chee_transport_has_a_named_api_owner(self):
        self.assertIn('from "./client.js"', self.source)
        self.assertIn("export function fetchDcm4cheeProfileDiagnostics", self.source)
        self.assertIn("export function fetchDcm4cheeAttempts", self.source)
        self.assertIn('from "../api/dcm4chee.js"', self.view)

    def test_dcm4chee_transport_is_not_owned_by_order_or_bootstrap(self):
        self.assertNotIn("fetchDcm4cheeAttempts", self.order_api)
        self.assertNotIn('requestJson("/api/dcm4chee', self.bootstrap)
        self.assertNotIn('requestJson("/api/dcm4chee', self.view)
        self.assertNotIn('requestJson(`/api/orders/${orderId}/dcm4chee-attempts`)', self.bootstrap)


if __name__ == "__main__":
    unittest.main()
