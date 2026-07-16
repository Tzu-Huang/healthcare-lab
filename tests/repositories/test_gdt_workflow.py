import tempfile
import unittest
from pathlib import Path

from backend.domain.gdt_protocol import build_gdt_6302_request, parse_gdt_6310_result, render_gdt_message
from backend.lab_store import DemoStore
from backend.repositories.gdt_workflow import GdtWorkflowRepository


class GdtWorkflowRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = DemoStore(Path(self.directory.name) / "gdt-repository.db")
        self.clock = iter(f"2026-07-16T00:00:{index:02d}+00:00" for index in range(60))
        self.repository = self.make_repository()

    def tearDown(self):
        self.directory.cleanup()

    def make_repository(self, repository_type=GdtWorkflowRepository, *, builder=build_gdt_6302_request):
        return repository_type(
            self.store.database.connect,
            self.store.database.lock,
            timestamp_factory=lambda: next(self.clock),
            patient_loader=self.store.patient_repository.get_patient_record,
            patient_list_loader=self.store.patient_repository.list_patient_records,
            order_builder=builder,
        )

    def patient(self, mrn="MRN-GDT-REPO"):
        return self.store.patient_repository.create_patient_record({
            "mode": "gdt", "mrn": mrn, "firstName": "Avery", "lastName": "Morgan",
            "dob": "19850412", "sex": "F",
        })

    @staticmethod
    def normalized_result(records, **extras):
        parsed = parse_gdt_6310_result(render_gdt_message(records, set_type="6310")).as_dict()
        parsed.update(extras)
        return parsed

    def table_counts(self):
        names = (
            "local_gdt_patient_contexts", "local_gdt_order_records", "local_gdt_message_records",
            "local_gdt_attachment_records", "local_gdt_workflow_events",
        )
        with self.store.database.connect() as connection:
            return {name: connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in names}

    def test_order_projection_snapshots_message_attachment_and_scoped_events(self):
        patient = self.patient()
        order = self.repository.create_gdt_order_record({
            "patientRecordId": patient["id"], "requestedAt": "20260716120000",
            "orderingProvider": "1001^WANG^AMY", "clinicalIndication": "Baseline",
            "attachmentUrl": "https://example.test/report.pdf",
            "gdtPatientNumberOverride": "MANUAL-3000-01", "gdtTestCode": "EKG01",
        })
        self.assertEqual(order["localGdtOrderNumber"], "GDT-ORD-000001")
        self.assertEqual(order["patientSnapshot"]["gdtPatientNumber"], "MANUAL-3000-01")
        self.assertEqual(order["messages"][0]["parsedFields"]["6330"], ["GDT-ORD-000001"])
        self.assertEqual(order["attachments"][0]["role"], "order-attachment")
        self.assertEqual(
            [event["eventType"] for event in order["events"]],
            ["patient-number-generated", "patient-number-overridden", "order-created",
             "message-generated", "attachment-registered"],
        )

    def test_matching_uses_newest_exact_candidate_and_preserves_context_only_unmatched(self):
        patient = self.patient()
        older = self.repository.create_gdt_order_record({"patientRecordId": patient["id"]})
        newer = self.repository.create_gdt_order_record({"patientRecordId": patient["id"]})
        matched = self.repository.record_gdt_result(self.normalized_result([
            ("3000", "WRONG-PATIENT"), ("8402", "EKG01"),
            ("6330", older["localGdtOrderNumber"]), ("6200", newer["localGdtOrderNumber"]),
        ]))
        self.assertEqual(matched["orderRecordId"], newer["id"])
        self.assertEqual(matched["patientContextId"], newer["gdtPatientContextId"])
        self.assertEqual(matched["matchStatus"], "order-matched")

        context_only = self.repository.record_gdt_result(self.normalized_result([
            ("3000", older["gdtPatientNumber"]), ("8402", "EKG01"), ("8410", "HR"),
        ]))
        fully_unmatched = self.repository.record_gdt_result(self.normalized_result([
            ("3000", "UNKNOWN-PATIENT"), ("8402", "EKG01"), ("8410", "HR"),
        ]))
        self.assertIsNone(context_only["orderRecordId"])
        self.assertEqual(context_only["patientContextId"], older["gdtPatientContextId"])
        self.assertEqual(context_only["matchStatus"], "unmatched")
        workbench = self.repository.list_gdt_workbench(bridge_inbox=[{"name": "pending.gdt"}])
        self.assertIn(context_only["id"], {item["id"] for item in workbench["patients"][0]["results"]})
        self.assertEqual([item["id"] for item in workbench["unmatchedResults"]], [fully_unmatched["id"]])
        self.assertEqual(workbench["bridgeInbox"], [{"name": "pending.gdt"}])

    def test_normalized_result_persists_attachment_details_and_updates_order_atomically(self):
        patient = self.patient()
        order = self.repository.create_gdt_order_record({"patientRecordId": patient["id"]})
        result = self.repository.record_gdt_result(self.normalized_result(
            [("3000", order["gdtPatientNumber"]), ("8402", "EKG01"),
             ("6330", order["localGdtOrderNumber"]), ("6302", "reports/result.pdf"),
             ("6303", "application/pdf")],
            sourceFile="device.gdt",
            attachments=[{"role": "extra", "reference": "reports/missing.dcm", "status": "warning",
                          "details": {"warning": "not found"}}],
        ))
        self.assertEqual(result["matchStatus"], "order-matched")
        updated = self.repository.get_gdt_order_record(order["id"])
        self.assertEqual(updated["status"], "Result received")
        by_role = {item["role"]: item for item in updated["attachments"]}
        self.assertEqual(by_role["report"]["sourceFile"], "device.gdt")
        self.assertEqual(by_role["extra"]["details"], {"warning": "not found"})

    def test_order_builder_failure_rolls_back_context_order_message_and_events(self):
        patient = self.patient()

        def fail_builder(_values):
            raise RuntimeError("builder failed")

        repository = self.make_repository(builder=fail_builder)
        before = self.table_counts()
        with self.assertRaisesRegex(RuntimeError, "builder failed"):
            repository.create_gdt_order_record({"patientRecordId": patient["id"]})
        self.assertEqual(self.table_counts(), before)

    def test_result_attachment_failure_rolls_back_all_result_rows_and_order_status(self):
        class FailingAttachmentRepository(GdtWorkflowRepository):
            def _attachment(self, *args, **kwargs):
                if kwargs.get("role") == "result-artifact":
                    raise RuntimeError("attachment failed")
                return super()._attachment(*args, **kwargs)

        patient = self.patient()
        order = self.repository.create_gdt_order_record({"patientRecordId": patient["id"]})
        repository = self.make_repository(FailingAttachmentRepository)
        before = self.table_counts()
        result = self.normalized_result(
            [("3000", order["gdtPatientNumber"]), ("8402", "EKG01"),
             ("6330", order["localGdtOrderNumber"])],
            attachments=[{"role": "result-artifact", "reference": "artifact.pdf"}],
        )
        with self.assertRaisesRegex(RuntimeError, "attachment failed"):
            repository.record_gdt_result(result)
        self.assertEqual(self.table_counts(), before)
        self.assertEqual(self.repository.get_gdt_order_record(order["id"])["status"], "Created")


if __name__ == "__main__":
    unittest.main()
