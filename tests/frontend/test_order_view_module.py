from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class OrderViewModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "frontend/static/js/views/order.js").read_text(encoding="utf-8")
        cls.bootstrap = (ROOT / "frontend/static/app.js").read_text(encoding="utf-8")

    def test_order_view_owns_mode_and_patient_selection_behavior(self):
        self.assertIn("export const ORDER_MODE_CONFIG", self.source)
        for owner in (
            "currentOrderMode",
            "orderPatientProtocolForMode",
            "orderPatientModeLabel",
            "orderPatientRecordsForMode",
            "selectedOrderPatient",
            "selectedOrderPatientReference",
            "renderOrderPatientOptions",
            "updateOrderModeFields",
        ):
            self.assertIn(f"export function {owner}", self.source)
            self.assertNotIn(f"function {owner}", self.bootstrap)

    def test_order_patient_selection_uses_shared_state(self):
        self.assertIn('../state/patient.js', self.source)
        self.assertIn('../state/selection.js', self.source)
        self.assertIn("getPatientRecords()", self.source)
        self.assertIn("setSelectedPatientId", self.source)

    def test_order_view_owns_form_and_validation_behavior(self):
        for owner in (
            "fhirOrderPayload",
            "orderFormPayload",
            "setFhirOrderForm",
            "setOrderForm",
            "validateOrderPayload",
            "renderOrderValidation",
        ):
            self.assertIn(f"export function {owner}", self.source)
            self.assertNotIn(f"function {owner}", self.bootstrap)

    def test_order_view_owns_protocol_preview_builders(self):
        for owner in (
            "buildGdtOrderPreviewPayload",
            "buildFhirOrderPreviewPayload",
            "buildOrderPreviewPayload",
        ):
            self.assertIn(f"export function {owner}", self.source)
            self.assertNotIn(f"function {owner}", self.bootstrap)
        for contract in ("ORM^O01^ORM_O01", 'resourceType: "ServiceRequest"', '"00400100"', '["8402", "EKG01"]'):
            self.assertIn(contract, self.source)

    def test_order_view_owns_preview_lifecycle(self):
        for owner in ("configureOrderCoordinator", "refreshOrderPreview", "initializeOrderView"):
            self.assertIn(f"export function {owner}", self.source)
            self.assertNotIn(f"function {owner}", self.bootstrap)
        self.assertIn("initializeOrderView({", self.bootstrap)

    def test_order_view_owns_record_table(self):
        for owner in (
            "renderOrderRecordList",
            "orderVisitNumber",
            "orderRecordMode",
            "orderListKey",
            "orderModeLabel",
            "orderStateLabel",
        ):
            self.assertIn(f"export function {owner}", self.source)
            self.assertNotIn(f"function {owner}", self.bootstrap)

    def test_order_view_owns_async_order_and_dcm4chee_actions(self):
        for owner in (
            "refreshOrders",
            "retryDcm4cheeOrder",
            "sendDcm4cheeOrder",
            "verifyDcm4cheeOrder",
            "simulateDcm4cheeApReturn",
            "refreshOrderWorkspace",
            "createOrderRecord",
        ):
            self.assertIn(f"export async function {owner}", self.source)
            self.assertNotIn(f"function {owner}", self.bootstrap)
        self.assertIn('../api/order.js', self.source)


if __name__ == "__main__":
    unittest.main()
