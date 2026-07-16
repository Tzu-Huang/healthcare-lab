import tempfile
import unittest
from pathlib import Path

from backend.domain.errors import SimulatorValidationError
from backend.domain.gdt_protocol import parse_gdt_6310_result, render_gdt_message
from backend.services.gdt_coordination import GdtWorkflowCoordinator, artifact_status


class RepositoryDouble:
    def __init__(self):
        self.created = []
        self.results = []
        self.order = {
            "id": 7,
            "localGdtOrderNumber": "GDT-ORD-000007",
            "gdtPatientNumber": "GDT-PAT-000003",
            "patientSnapshot": {"lastName": "Morgan", "firstName": "Avery"},
        }

    def create_gdt_order_record(self, values):
        self.created.append(values)
        return {"id": 1, **values}

    def record_gdt_result(self, values):
        self.results.append(values)
        return values

    def list_gdt_order_records(self):
        return [self.order]

    def get_gdt_order_record(self, record_id):
        if record_id != self.order["id"]:
            raise KeyError(record_id)
        return self.order

    def list_gdt_messages(self, order_record_id=None):
        return [{"orderRecordId": order_record_id}]

    def list_gdt_events(self, order_record_id=None):
        return [{"orderRecordId": order_record_id}]

    def list_gdt_attachments(self, order_record_id=None):
        return [{"orderRecordId": order_record_id}]

    def list_gdt_workbench(self, *, bridge_inbox=None):
        return {"bridgeInbox": bridge_inbox or []}

    def record_gdt_order_export(self, order_record_id, *, export_path, status, error_text=""):
        return {"id": order_record_id, "exportPath": export_path, "status": status, "error": error_text}

    def list_gdt_orders(self):
        return [{"id": self.order["id"]}]


class GdtWorkflowCoordinatorTest(unittest.TestCase):
    def setUp(self):
        self.repository = RepositoryDouble()
        self.coordinator = GdtWorkflowCoordinator(
            self.repository, requested_at_factory=lambda: "20260716123456"
        )

    def test_order_payload_is_validated_and_normalized_before_persistence(self):
        result = self.coordinator.create_gdt_order_record(
            {
                "patientRecordId": "12",
                "orderingProvider": " 1001^WANG^AMY ",
                "clinicalIndication": " baseline ",
                "gdtPatientNumberOverride": " MANUAL-01 ",
            }
        )
        self.assertEqual(
            self.repository.created[0],
            {
                "patient_record_id": 12,
                "requested_at": "20260716123456",
                "ordering_provider": "1001^WANG^AMY",
                "clinical_indication": "baseline",
                "attachment_url": "",
                "gdt_patient_number_override": "MANUAL-01",
                "gdt_test_code": "EKG01",
            },
        )
        self.assertEqual(result["patient_record_id"], 12)

        for payload in ({}, {"patientRecordId": 1, "gdtTestCode": "EKG04"},
                        {"patientRecordId": 1, "gdtPatientNumberOverride": "bad\nnumber"}):
            with self.assertRaises(SimulatorValidationError):
                self.coordinator.create_gdt_order_record(payload)
        self.assertEqual(len(self.repository.created), 1)

    def test_result_is_parsed_and_artifact_status_is_resolved_before_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reports"
            reports.mkdir()
            (reports / "available.pdf").write_bytes(b"pdf")
            raw = render_gdt_message(
                [
                    ("3000", "GDT-PAT-000003"), ("8402", "EKG01"),
                    ("6330", "GDT-ORD-000007"),
                    ("6302", "report"), ("6303", "PDF"), ("6304", "ECG report"),
                    ("6305", "available.pdf"),
                ],
                set_type="6310",
            )
            result = self.coordinator.record_gdt_result(
                {
                    "rawGdtText": raw,
                    "bridgeRoot": str(root),
                    "sourceFile": "device.gdt",
                    "attachments": [
                        {"role": "external", "url": "https://example.test/report.pdf"},
                        {"role": "missing", "reference": "absent.dcm", "status": "manual",
                         "details": {"reviewed": True}},
                    ],
                }
            )
        persisted = self.repository.results[0]
        self.assertEqual(result, persisted)
        self.assertEqual(persisted["parsedFields"]["8000"], ["6310"])
        protocol_attachment = persisted["canonical"]["attachments"][0]
        self.assertEqual(protocol_attachment["status"], "available")
        self.assertEqual(protocol_attachment["details"], {"kind": "path"})
        self.assertEqual(protocol_attachment["sourceFile"], "device.gdt")
        external, missing = persisted["attachments"]
        self.assertEqual(external["status"], "reference-only")
        self.assertEqual(missing["status"], "manual")
        self.assertTrue(missing["details"]["reviewed"])
        self.assertIn("warning", missing["details"])

    def test_invalid_raw_result_never_reaches_repository(self):
        with self.assertRaises(SimulatorValidationError):
            self.coordinator.record_gdt_result({"rawGdtText": "not-gdt"})
        self.assertEqual(self.repository.results, [])
        with self.assertRaises(SimulatorValidationError):
            self.coordinator.record_gdt_result([])

    def test_demo_result_is_deterministic_and_uses_normal_result_path(self):
        first = self.coordinator.create_gdt_demo_result(7)
        second = self.coordinator.create_gdt_demo_result(7)
        self.assertEqual(first["rawGdtText"], second["rawGdtText"])
        parsed = parse_gdt_6310_result(first["rawGdtText"])
        self.assertEqual(parsed.canonical["result"]["measurements"]["QTC"]["value"], 427)
        self.assertEqual(first["sourceFile"], "demo-result")
        self.assertEqual(
            [item["path"] for item in first["canonical"]["attachments"]],
            ["reports/gdt-ord-000007-report.pdf", "reports/gdt-ord-000007.dcm"],
        )

    def test_reads_export_and_workbench_are_narrow_delegates(self):
        self.assertEqual(self.coordinator.list_gdt_order_records(), [self.repository.order])
        self.assertEqual(self.coordinator.get_gdt_order_record(7), self.repository.order)
        self.assertEqual(self.coordinator.list_gdt_messages(7), [{"orderRecordId": 7}])
        self.assertEqual(self.coordinator.list_gdt_events(7), [{"orderRecordId": 7}])
        self.assertEqual(self.coordinator.list_gdt_attachments(7), [{"orderRecordId": 7}])
        self.assertEqual(self.coordinator.list_gdt_workbench(bridge_inbox=[{"name": "one.gdt"}]),
                         {"bridgeInbox": [{"name": "one.gdt"}]})
        self.assertEqual(self.coordinator.record_gdt_order_export(
            7, export_path="out.gdt", status="exported"
        )["exportPath"], "out.gdt")
        self.assertEqual(self.coordinator.list_gdt_orders(), [{"id": 7}])

    def test_artifact_status_has_no_mutation_and_preserves_legacy_resolution_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reports").mkdir()
            (root / "reports" / "item.pdf").write_bytes(b"pdf")
            self.assertEqual(artifact_status("item.pdf", str(root)), ("available", {"kind": "path"}))
            self.assertEqual(artifact_status("https://example.test/a.pdf"),
                             ("reference-only", {"kind": "url"}))
            self.assertEqual(artifact_status(""),
                             ("missing-reference", {"warning": "Artifact reference is empty."}))


if __name__ == "__main__":
    unittest.main()
