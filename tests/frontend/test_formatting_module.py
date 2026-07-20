from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class FormattingModuleTests(unittest.TestCase):
    def test_shared_formatters_are_exported_from_core(self):
        source = (ROOT / "frontend/static/js/core/formatting.js").read_text(encoding="utf-8")
        for name in (
            "hl7Escape", "hl7EscapeComposite", "pad", "hl7Timestamp",
            "localDatetimeValue", "taipeiTimestamp", "gdtTaipeiTimestamp",
            "fhirBirthDate", "fhirGender",
        ):
            with self.subTest(name=name):
                self.assertIn(f"export function {name}(", source)

    def test_core_formatter_has_no_dom_or_transport_dependency(self):
        source = (ROOT / "frontend/static/js/core/formatting.js").read_text(encoding="utf-8")
        self.assertNotIn("document.", source)
        self.assertNotIn("fetch(", source)
        self.assertNotIn("/api/", source)


if __name__ == "__main__":
    unittest.main()
