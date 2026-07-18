import unittest
from pathlib import Path

from backend.services.coordination import ConfiguredWorkflowOperations
from backend.services.fhir_workflow import FhirRepositoryPort


ROOT = Path(__file__).resolve().parents[2]


class _FhirCapability:
    def create_patient_fhir_workflow_record(self, item):
        return item

    def create_fhir_order_record(self, item):
        return item

    def create_order_service_request_fhir_workflow_record(self, item):
        return item


class _Ledger:
    def mark_fhir_sync_failure(self, record_id, **_values):
        return {"id": record_id}


class ProtocolRepositoryWiringTests(unittest.TestCase):
    def test_configured_fhir_operations_sync_through_the_ledger(self):
        ledger = _Ledger()
        calls = []
        capability = _FhirCapability()
        broad = type("Broad", (), {
            "create_dcm4chee_e2e_demo_fixture": lambda *_args: {},
            "create_dcm4chee_order_record": lambda *_args: {},
            "list_dcm4chee_mwl_attempts": lambda *_args: [],
            "dcm4chee_e2e_evidence_for_order": lambda *_args: {},
            "create_simulated_dcm4chee_ap_return": lambda *_args: {},
            "get_patient_record": lambda *_args: {},
        })()
        operations = ConfiguredWorkflowOperations(
            patient=broad, order=broad, patient_fhir=capability,
            order_fhir=capability, fhir_ledger=ledger,
            fhir_sync=lambda repository, record_id, **_values: calls.append(
                (repository, record_id)
            ) or {"id": record_id},
            patient_sync=lambda *_args, **_values: {},
            result_refresh=lambda *_args, **_values: {},
            order_sync=lambda *_args, **_values: {},
            order_verify=lambda *_args, **_values: {},
            patient_sender=lambda *_args, **_values: None,
        )

        operations.sync_patient_fhir(7, base_url="https://fhir.test", auth_manager=object())
        operations.sync_order_fhir(8, base_url="https://fhir.test", auth_manager=object())

        self.assertEqual(calls, [(ledger, 7), (ledger, 8)])
        marker = {"protocolVersion": "FHIR R4"}
        self.assertIs(
            operations.patient_fhir.create_patient_fhir_workflow_record(marker), marker
        )

    def test_fhir_port_declares_the_complete_sync_surface(self):
        declared = {
            name for name, value in FhirRepositoryPort.__dict__.items()
            if not name.startswith("_") and callable(value)
        }
        self.assertEqual(
            declared,
            {
                "list_fhir_resource_mappings", "list_fhir_workflow_records",
                "create_fhir_workflow_record", "get_fhir_workflow_record",
                "list_fhir_sync_attempts", "ordered_fhir_workflow_records",
                "mark_fhir_syncing", "mark_fhir_sync_success",
                "mark_fhir_sync_failure", "record_fhir_sync_attempt",
            },
        )

    def test_composition_root_routes_protocols_to_named_owners(self):
        source = (ROOT / "backend" / "app_factory.py").read_text(encoding="utf-8")
        self.assertIn("FhirWorkflowService(\n                fhir_ledger,", source)
        self.assertIn("GdtWorkflowService(\n        gdt_workflow, app.config,", source)
        self.assertIn(
            "gdt_workflow, gdt_service.bridge_service, gdt_service.result_service,",
            source,
        )
        self.assertIn("GdtBridgeInboundWatcher(\n        gdt_workflow,", source)
        self.assertLessEqual(len(source.splitlines()), 500)


if __name__ == "__main__":
    unittest.main()
