from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class OrderApiModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "frontend/static/js/api/order.js").read_text(encoding="utf-8")
        cls.bootstrap = (ROOT / "frontend/static/app.js").read_text(encoding="utf-8")
        cls.view = (ROOT / "frontend/static/js/views/order.js").read_text(encoding="utf-8")

    def test_order_adapter_owns_order_workflow_transport(self):
        for operation in (
            "fetchOrders",
            "fetchGdtOrders",
            "createOrder",
            "syncDcm4cheeOrder",
            "verifyDcm4cheeMwl",
            "simulateDcm4cheeApReturn",
        ):
            self.assertIn(f"export function {operation}", self.source)
            self.assertIn(operation, self.bootstrap + self.view)

    def test_bootstrap_has_no_direct_order_transport(self):
        self.assertNotIn('requestJson("/api/orders', self.bootstrap)
        self.assertNotIn('requestJson(`/api/orders', self.bootstrap)
        self.assertNotIn('requestJsonAllowBusinessFailure(`/api/orders', self.bootstrap)
        for endpoint in (
            "/api/orders",
            "/api/gdt/orders",
            "/dcm4chee-sync",
            "/dcm4chee-mwl-verify",
            "/dcm4chee-simulated-ap-return",
        ):
            self.assertIn(endpoint, self.source)


if __name__ == "__main__":
    unittest.main()
