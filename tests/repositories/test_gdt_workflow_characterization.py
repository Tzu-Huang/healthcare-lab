import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.lab_store import DemoStore, render_gdt_message


class GdtWorkflowCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        temporary_root = Path(self.directory.name).resolve()
        self.path = (temporary_root / "gdt-workflow-characterization.db").resolve()
        self.assertTrue(self.path.is_relative_to(temporary_root))
        self.store = DemoStore(self.path)
        self.assertEqual(Path(self.store.path).resolve(), self.path)

    def tearDown(self):
        self.directory.cleanup()

    @staticmethod
    def patient(mrn, **overrides):
        payload = {
            "mode": "gdt",
            "mrn": mrn,
            "firstName": "Avery",
            "lastName": "Morgan",
            "dob": "19850412",
            "sex": "F",
        }
        payload.update(overrides)
        return payload

    @staticmethod
    def result_message(fields):
        return render_gdt_message(fields, set_type="6310")

    def table_counts(self):
        tables = (
            "local_gdt_patient_contexts",
            "local_gdt_order_records",
            "local_gdt_message_records",
            "local_gdt_workflow_events",
            "local_gdt_attachment_records",
        )
        with self.store.connect() as connection:
            return {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in tables
            }

    def test_conflicting_exact_identifiers_choose_newest_matching_order_id(self):
        patient = self.store.create_patient_record(self.patient("MRN-GDT-CONFLICT"))
        first = self.store.create_gdt_order_record({"patientRecordId": patient["id"]})
        second = self.store.create_gdt_order_record({"patientRecordId": patient["id"]})
        newest = self.store.create_gdt_order_record({"patientRecordId": patient["id"]})

        result = self.store.record_gdt_result(
            {
                "rawGdtText": self.result_message(
                    [
                        ("3000", first["gdtPatientNumber"]),
                        ("6330", first["localGdtOrderNumber"]),
                        ("6200", second["localGdtOrderNumber"]),
                        ("8402", "EKG01"),
                        ("8410", newest["localGdtOrderNumber"]),
                        ("6220", "Conflicting exact identifiers"),
                    ]
                )
            }
        )

        self.assertEqual(result["matchStatus"], "order-matched")
        self.assertEqual(result["orderRecordId"], newest["id"])
        self.assertEqual(
            result["canonical"]["order"]["localGdtOrderNumber"],
            newest["localGdtOrderNumber"],
        )
        self.assertEqual(self.store.get_gdt_order_record(newest["id"])["status"], "Result received")
        self.assertEqual(self.store.get_gdt_order_record(first["id"])["status"], "Created")
        self.assertEqual(self.store.get_gdt_order_record(second["id"])["status"], "Created")

    def test_exact_order_match_overrides_contradictory_patient_number(self):
        matched_patient = self.store.create_patient_record(self.patient("MRN-GDT-MATCHED"))
        contradictory_patient = self.store.create_patient_record(self.patient("MRN-GDT-CONTRADICT"))
        matched_order = self.store.create_gdt_order_record({"patientRecordId": matched_patient["id"]})
        contradictory_order = self.store.create_gdt_order_record(
            {"patientRecordId": contradictory_patient["id"]}
        )

        result = self.store.record_gdt_result(
            {
                "rawGdtText": self.result_message(
                    [
                        ("3000", contradictory_order["gdtPatientNumber"]),
                        ("6330", matched_order["localGdtOrderNumber"]),
                        ("8402", "EKG01"),
                        ("6220", "Order identifier wins"),
                    ]
                )
            }
        )

        self.assertEqual(result["orderRecordId"], matched_order["id"])
        self.assertEqual(result["patientContextId"], matched_order["gdtPatientContextId"])
        workbench_by_patient = {
            patient["id"]: patient for patient in self.store.list_gdt_workbench()["patients"]
        }
        self.assertEqual(
            [item["id"] for item in workbench_by_patient[matched_patient["id"]]["results"]],
            [result["id"]],
        )
        self.assertEqual(workbench_by_patient[contradictory_patient["id"]]["results"], [])

    def test_context_only_and_fully_unbound_results_use_current_workbench_buckets(self):
        patient = self.store.create_patient_record(self.patient("MRN-GDT-BUCKETS"))
        order = self.store.create_gdt_order_record({"patientRecordId": patient["id"]})
        context_only = self.store.record_gdt_result(
            {
                "rawGdtText": self.result_message(
                    [
                        ("3000", order["gdtPatientNumber"]),
                        ("8402", "EKG01"),
                        ("6220", "Known context only"),
                    ]
                )
            }
        )
        fully_unbound = self.store.record_gdt_result(
            {
                "rawGdtText": self.result_message(
                    [
                        ("3000", "UNKNOWN-GDT-PATIENT"),
                        ("8402", "EKG01"),
                        ("6220", "No context or order"),
                    ]
                )
            }
        )

        workbench = self.store.list_gdt_workbench()
        patient_bucket = next(item for item in workbench["patients"] if item["id"] == patient["id"])
        self.assertEqual(context_only["matchStatus"], "unmatched")
        self.assertIsNone(context_only["orderRecordId"])
        self.assertEqual(context_only["patientContextId"], order["gdtPatientContextId"])
        self.assertEqual([item["id"] for item in patient_bucket["results"]], [context_only["id"]])
        self.assertEqual([item["id"] for item in workbench["unmatchedResults"]], [fully_unbound["id"]])
        self.assertEqual({item["id"] for item in workbench["results"]}, {context_only["id"], fully_unbound["id"]})
        self.assertEqual(workbench["resultsByOrder"], {})

    def test_6302_builder_failure_rolls_back_all_gdt_workflow_rows(self):
        patient = self.store.create_patient_record(self.patient("MRN-GDT-ORDER-ROLLBACK"))

        with patch("backend.lab_store.build_gdt_6302_request", side_effect=RuntimeError("6302 failed")):
            with self.assertRaisesRegex(RuntimeError, "6302 failed"):
                self.store.create_gdt_order_record(
                    {
                        "patientRecordId": patient["id"],
                        "attachmentUrl": "https://example.test/order.pdf",
                    }
                )

        self.assertEqual(self.table_counts(), {table: 0 for table in self.table_counts()})

    def test_result_side_failure_rolls_back_message_attachments_events_and_status(self):
        patient = self.store.create_patient_record(self.patient("MRN-GDT-RESULT-ROLLBACK"))
        order = self.store.create_gdt_order_record({"patientRecordId": patient["id"]})
        before = self.table_counts()
        original_record_event = self.store._record_gdt_event
        event_calls = 0

        def fail_after_first_event(*args, **kwargs):
            nonlocal event_calls
            event_calls += 1
            if event_calls == 2:
                raise RuntimeError("result event failed")
            return original_record_event(*args, **kwargs)

        raw_result = self.result_message(
            [
                ("3000", order["gdtPatientNumber"]),
                ("6330", order["localGdtOrderNumber"]),
                ("8402", "EKG01"),
                ("6220", "Rollback this result"),
            ]
        )
        with patch.object(self.store, "_record_gdt_event", side_effect=fail_after_first_event):
            with self.assertRaisesRegex(RuntimeError, "result event failed"):
                self.store.record_gdt_result(
                    {
                        "rawGdtText": raw_result,
                        "attachments": [
                            {
                                "role": "report",
                                "reference": "reports/rollback.pdf",
                                "contentType": "application/pdf",
                            }
                        ],
                    }
                )

        self.assertEqual(event_calls, 2)
        self.assertEqual(self.table_counts(), before)
        self.assertEqual(self.store.get_gdt_order_record(order["id"])["status"], "Created")
        self.assertFalse(
            any(
                message["direction"] == "inbound"
                for message in self.store.list_gdt_messages(order["id"])
            )
        )


if __name__ == "__main__":
    unittest.main()
