from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class OrderStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = ROOT / "frontend/static/js/state/order.js"
        cls.source = cls.path.read_text(encoding="utf-8")
        cls.bootstrap = (ROOT / "frontend/static/app.js").read_text(encoding="utf-8")
        cls.view = (ROOT / "frontend/static/js/views/order.js").read_text(encoding="utf-8")

    def test_order_collections_and_record_selection_have_explicit_apis(self):
        for operation in (
            "getOrderRecords",
            "setOrderRecords",
            "getGdtOrderRecords",
            "setGdtOrderRecords",
            "getSelectedOrderRecordKey",
            "setSelectedOrderRecordKey",
        ):
            self.assertIn(f"export function {operation}", self.source)
            self.assertIn(operation, self.bootstrap + self.view)
        for legacy_global in ("let orderRecords", "let gdtOrderRecords", "let selectedOrderRecordKey"):
            self.assertNotIn(legacy_global, self.bootstrap)

    def test_order_state_round_trips_and_normalizes_invalid_values(self):
        module_uri = self.path.as_uri()
        script = f"""
            import {{
              getGdtOrderRecords, getOrderRecords, getSelectedOrderRecordKey,
              setGdtOrderRecords, setOrderRecords, setSelectedOrderRecordKey,
            }} from {module_uri!r};
            setOrderRecords([{{ id: 1 }}]);
            setGdtOrderRecords([{{ id: 2 }}]);
            setSelectedOrderRecordKey("gdt:2");
            if (getOrderRecords()[0].id !== 1 || getGdtOrderRecords()[0].id !== 2) process.exit(1);
            if (getSelectedOrderRecordKey() !== "gdt:2") process.exit(2);
            setOrderRecords(null);
            setGdtOrderRecords(null);
            setSelectedOrderRecordKey(null);
            if (getOrderRecords().length || getGdtOrderRecords().length || getSelectedOrderRecordKey()) process.exit(3);
        """
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
