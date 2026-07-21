import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.application_composition import assemble_application_dependencies
from backend.domain.gdt_protocol import render_gdt_message
from backend.repositories.gdt_workflow import GdtWorkflowRepository
from backend.services.gdt_coordination import GdtWorkflowCoordinator


class GdtWorkflowCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        temporary_root = Path(self.directory.name).resolve()
        self.path = (temporary_root / "gdt-workflow-characterization.db").resolve()
        self.assertTrue(self.path.is_relative_to(temporary_root))
        self.dependencies = assemble_application_dependencies(self.path)
        self.assertEqual(Path(self.dependencies.database.path).resolve(), self.path)

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
        with self.dependencies.database.connect() as connection:
            return {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in tables
            }

    def workflow(self, *, order_builder=render_gdt_message):
        repository = GdtWorkflowRepository(
            self.dependencies.database.connect,
            self.dependencies.database.lock,
            timestamp_factory=lambda: "2026-07-16T09:00:00+00:00",
            patient_loader=self.dependencies.patient_repository.get_patient_record,
            patient_list_loader=self.dependencies.patient_repository.list_patient_records,
            order_builder=order_builder,
        )
        return GdtWorkflowCoordinator(repository), repository

    def test_conflicting_exact_identifiers_choose_newest_matching_order_id(self):
        patient = self.dependencies.patient_repository.create_patient_record(self.patient("MRN-000611"))
        first = self.dependencies.gdt_workflow.create_gdt_order_record({"patientRecordId": patient["id"]})
        second = self.dependencies.gdt_workflow.create_gdt_order_record({"patientRecordId": patient["id"]})
        newest = self.dependencies.gdt_workflow.create_gdt_order_record({"patientRecordId": patient["id"]})

        result = self.dependencies.gdt_workflow.record_gdt_result(
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
        self.assertEqual(self.dependencies.gdt_workflow.get_gdt_order_record(newest["id"])["status"], "Result received")
        self.assertEqual(self.dependencies.gdt_workflow.get_gdt_order_record(first["id"])["status"], "Created")
        self.assertEqual(self.dependencies.gdt_workflow.get_gdt_order_record(second["id"])["status"], "Created")

    def test_exact_order_match_overrides_contradictory_patient_number(self):
        matched_patient = self.dependencies.patient_repository.create_patient_record(self.patient("MRN-000612"))
        contradictory_patient = self.dependencies.patient_repository.create_patient_record(self.patient("MRN-000613"))
        matched_order = self.dependencies.gdt_workflow.create_gdt_order_record({"patientRecordId": matched_patient["id"]})
        contradictory_order = self.dependencies.gdt_workflow.create_gdt_order_record(
            {"patientRecordId": contradictory_patient["id"]}
        )

        result = self.dependencies.gdt_workflow.record_gdt_result(
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
            patient["id"]: patient for patient in self.dependencies.gdt_workflow.list_gdt_workbench()["patients"]
        }
        self.assertEqual(
            [item["id"] for item in workbench_by_patient[matched_patient["id"]]["results"]],
            [result["id"]],
        )
        self.assertEqual(workbench_by_patient[contradictory_patient["id"]]["results"], [])

    def test_context_only_and_fully_unbound_results_use_current_workbench_buckets(self):
        patient = self.dependencies.patient_repository.create_patient_record(self.patient("MRN-000614"))
        order = self.dependencies.gdt_workflow.create_gdt_order_record({"patientRecordId": patient["id"]})
        context_only = self.dependencies.gdt_workflow.record_gdt_result(
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
        fully_unbound = self.dependencies.gdt_workflow.record_gdt_result(
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

        self.assertEqual(context_only["matchStatus"], "unmatched")
        self.assertIsNone(context_only["orderRecordId"])
        self.assertEqual(context_only["patientContextId"], order["gdtPatientContextId"])
        legacy_context_only = self.dependencies.gdt_workflow.record_gdt_result(
            {
                "rawGdtText": self.result_message(
                    [
                        ("3000", order["patientSnapshot"]["gdtWorkflowPatientId"]),
                        ("8402", "EKG01"),
                        ("6220", "Known legacy context only"),
                    ]
                )
            }
        )
        self.assertEqual(legacy_context_only["patientContextId"], order["gdtPatientContextId"])
        workbench = self.dependencies.gdt_workflow.list_gdt_workbench()
        patient_bucket = next(item for item in workbench["patients"] if item["id"] == patient["id"])
        self.assertEqual(
            [item["id"] for item in patient_bucket["results"]],
            [legacy_context_only["id"], context_only["id"]],
        )
        self.assertEqual([item["id"] for item in workbench["unmatchedResults"]], [fully_unbound["id"]])
        self.assertEqual(
            {item["id"] for item in workbench["results"]},
            {context_only["id"], legacy_context_only["id"], fully_unbound["id"]},
        )
        self.assertEqual(workbench["resultsByOrder"], {})

    def test_canonical_mrn_precedes_legacy_alias_and_ambiguous_alias_is_unmatched(self):
        canonical_patient = self.dependencies.patient_repository.create_patient_record(
            self.patient("MRN-000617")
        )
        canonical_order = self.dependencies.gdt_workflow.create_gdt_order_record(
            {
                "patientRecordId": canonical_patient["id"],
                "gdtPatientNumberOverride": "LEGACY-CANONICAL-PATIENT",
            }
        )
        alias_patient = self.dependencies.patient_repository.create_patient_record(
            self.patient("MRN-000618")
        )
        self.dependencies.gdt_workflow.create_gdt_order_record(
            {
                "patientRecordId": alias_patient["id"],
                "gdtPatientNumberOverride": canonical_patient["summary"]["mrn"],
            }
        )

        canonical_result = self.dependencies.gdt_workflow.record_gdt_result(
            {
                "rawGdtText": self.result_message(
                    [
                        ("3000", canonical_patient["summary"]["mrn"]),
                        ("8402", "EKG01"),
                        ("6220", "Canonical MRN wins over legacy alias"),
                    ]
                )
            }
        )

        self.assertEqual(
            canonical_result["patientContextId"],
            canonical_order["gdtPatientContextId"],
        )

        ambiguous_patient = self.dependencies.patient_repository.create_patient_record(
            self.patient("MRN-000619")
        )
        self.dependencies.gdt_workflow.create_gdt_order_record(
            {
                "patientRecordId": ambiguous_patient["id"],
                "gdtPatientNumberOverride": f"GDT-PAT-{canonical_patient['id']:06d}",
            }
        )
        ambiguous_result = self.dependencies.gdt_workflow.record_gdt_result(
            {
                "rawGdtText": self.result_message(
                    [
                        ("3000", f"GDT-PAT-{canonical_patient['id']:06d}"),
                        ("8402", "EKG01"),
                        ("6220", "Ambiguous legacy alias"),
                    ]
                )
            }
        )

        self.assertIsNone(ambiguous_result["patientContextId"])

    def test_6302_builder_failure_rolls_back_all_gdt_workflow_rows(self):
        patient = self.dependencies.patient_repository.create_patient_record(self.patient("MRN-000615"))

        workflow, _ = self.workflow(
            order_builder=lambda _payload: (_ for _ in ()).throw(RuntimeError("6302 failed"))
        )
        with self.assertRaisesRegex(RuntimeError, "6302 failed"):
            workflow.create_gdt_order_record(
                {
                    "patientRecordId": patient["id"],
                    "attachmentUrl": "https://example.test/order.pdf",
                }
            )

        self.assertEqual(self.table_counts(), {table: 0 for table in self.table_counts()})

    def test_result_side_failure_rolls_back_message_attachments_events_and_status(self):
        patient = self.dependencies.patient_repository.create_patient_record(self.patient("MRN-000616"))
        order = self.dependencies.gdt_workflow.create_gdt_order_record({"patientRecordId": patient["id"]})
        before = self.table_counts()
        workflow, repository = self.workflow()
        original_record_event = repository._event
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
        with patch.object(repository, "_event", side_effect=fail_after_first_event):
            with self.assertRaisesRegex(RuntimeError, "result event failed"):
                workflow.record_gdt_result(
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
        self.assertEqual(self.dependencies.gdt_workflow.get_gdt_order_record(order["id"])["status"], "Created")
        self.assertFalse(
            any(
                message["direction"] == "inbound"
                for message in self.dependencies.gdt_workflow.list_gdt_messages(order["id"])
            )
        )


if __name__ == "__main__":
    unittest.main()
