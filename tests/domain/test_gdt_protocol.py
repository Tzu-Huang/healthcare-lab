import ast
import unittest
from pathlib import Path

from backend import gdt_adapter
from backend.domain import gdt_protocol
from backend.templates import gdt as gdt_template


class GdtProtocolTest(unittest.TestCase):
    def test_6302_and_6310_outputs_match_legacy_adapter(self):
        order = {
            "gdtPatientNumber": "GDT-PAT-000001", "lastName": "Müller", "firstName": "Avery",
            "birthDate": "12041985", "localGdtOrderNumber": "GDT-ORD-000001", "sex": "2",
            "requestedAt": "20260706110000", "orderingProvider": "1001^WANG^AMY",
            "clinicalIndication": "Resting ECG baseline", "patient": {"mrn": "MRN-1"},
            "order": {"localGdtOrderNumber": "GDT-ORD-000001"},
        }
        expected = gdt_adapter.build_gdt_6302_request(order)
        actual = gdt_template.build_gdt_6302_request(order)
        self.assertEqual(actual.as_dict(), expected.as_dict())
        self.assertEqual(actual.raw_gdt_text, expected.raw_gdt_text)
        self.assertEqual({"errors": [], "warnings": []}, actual.validation)

        payload = gdt_protocol.render_gdt_message(
            [("3000", "GDT-PAT-000001"), ("8402", "EKG01"),
             ("6200", "GDT-ORD-000001"), ("8410", "HR"), ("8420", "75"),
             ("8421", "/min"), ("6302", "report"), ("6303", "PDF"),
             ("6304", "ECG report"), ("6305", "reports/report.pdf")],
            set_type="6310",
        )
        self.assertEqual(gdt_protocol.parse_gdt_6310_result(payload).as_dict(),
                         gdt_adapter.parse_gdt_6310_result(payload).as_dict())

    def test_encoding_validation_and_persistence_candidates_are_deterministic(self):
        with self.assertRaisesRegex(gdt_protocol.GdtValidationError, "ANSI"):
            gdt_protocol.render_gdt_message([("3000", "病人")], set_type="6310")
        fields = {"6330": ["older"], "6200": ["newer"], "8410": ["HR", "surprise"]}
        self.assertEqual(gdt_protocol.result_order_identifiers(fields), ["older", "newer"])
        self.assertEqual(
            gdt_protocol.persistence_order_identifiers(fields),
            ["older", "newer", "HR", "surprise"],
        )

    def test_protocol_module_has_no_framework_persistence_or_filesystem_imports(self):
        path = Path(gdt_protocol.__file__)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        self.assertTrue({"flask", "sqlite3", "pathlib", "backend"}.isdisjoint(imports))


if __name__ == "__main__":
    unittest.main()
