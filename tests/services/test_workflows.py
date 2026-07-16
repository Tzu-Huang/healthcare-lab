import json
import unittest
from unittest.mock import Mock, patch

from backend.domain.errors import LabOperationError
from backend.domain.statuses import (
    FHIR_SYNC_STATUS_SYNCED,
    ORDER_STATUS_ACCEPTED,
    ORDER_STATUS_TRANSPORT_ERROR,
)
from backend.services.fhir_workflow import FhirWorkflowService
from backend.services.gdt_workflow import GdtConfigurationConflict, GdtWorkflowService
from backend.services.lab_workflow import (
    DashboardWorkflowService,
    LabHealthService,
    LabOperationService,
    LabRegistryService,
    LabServerWorkflowService,
    LabSmokeService,
)
from backend.services.oie_workflow import OieTransportError, OieWorkflowService
from backend.services.order_workflow import OrderWorkflowService
from backend.services.patient_workflow import PatientWorkflowService


class PatientRepository:
    def __init__(self):
        self.failed = None

    def create_patient_record(self, _payload):
        return {"id": 1, "protocolVersion": "FHIR R4"}

    def create_patient_fhir_workflow_record(self, _patient):
        return {"id": 10}

    def mark_fhir_sync_failure(self, record_id, *, error_text):
        self.failed = (record_id, error_text)
        return {}

    def get_patient_record(self, _record_id):
        return {"id": 1, "protocolVersion": "FHIR R4"}


class OrderRepository:
    def get_order_record(self, _order_id):
        return {"id": 1, "protocolVersion": "HL7 v2.5.1"}


class FhirRepository:
    def get_fhir_workflow_record(self, record_id):
        return {"id": record_id, "resourceType": "Patient"}

    def list_fhir_workflow_records(self, _sync_status=""):
        return []


class Watcher:
    def __init__(self, running=False):
        self.running = running

    def status(self):
        return {"running": self.running}

    def configure(self, **_values):
        return self.status()


class OieRepository:
    def __init__(self):
        self.updated = None

    def get_order_record(self, _order_id):
        return {"payload": "MSH|ORDER"}

    def update_order_send_result(self, order_id, **values):
        self.updated = {"id": order_id, **values}
        return self.updated


class Listener:
    def status(self):
        return {"running": False}

    def start(self, **_values):
        return {"running": True}

    def stop(self):
        return {"running": False}


class LabWorkflowRepository:
    def __init__(self, servers):
        self.servers = servers
        self.operations = []

    def list_lab_servers(self):
        return self.servers

    def get_lab_server(self, server_id):
        return next(item for item in self.servers if item["id"] == server_id)

    def list_lab_operations(self, server_id=None, *, limit=20):
        return self.operations[-limit:]

    def record_lab_operation(self, server_id, **values):
        operation = {"serverId": server_id, **values}
        self.operations.append(operation)
        return operation


class WorkflowServiceTest(unittest.TestCase):
    def test_lab_compatibility_service_composes_focused_use_case_owners(self):
        service = self._lab_service(LabWorkflowRepository([]))

        self.assertIsInstance(service.registry, LabRegistryService)
        self.assertIsInstance(service.health, LabHealthService)
        self.assertIsInstance(service.operations, LabOperationService)
        self.assertIsInstance(service.smoke, LabSmokeService)

    def test_patient_missing_medplum_records_sync_failure(self):
        repository = PatientRepository()
        service = PatientWorkflowService(
            repository,
            {"DCM4CHEE_UID_ROOT": "1.2.3"},
            medplum_base_url=lambda: "",
            auth_manager=lambda: object(),
            fhir_sync=lambda *_args, **_kwargs: self.fail("sync must not run"),
            dicom_patient_sync=lambda *_args, **_kwargs: None,
            dcm_result_refresh=lambda *_args, **_kwargs: {},
            dcm_profile=lambda _config: {},
        )

        item = service.create({})

        self.assertEqual(1, item["id"])
        self.assertEqual((10, "Medplum FHIR base URL is required."), repository.failed)

    def test_order_rejects_non_dicom_workflow(self):
        service = OrderWorkflowService(
            OrderRepository(),
            {},
            medplum_base_url=lambda: "",
            auth_manager=lambda: object(),
            fhir_sync=lambda *_args, **_kwargs: None,
            dcm_sync=lambda *_args, **_kwargs: None,
            dcm_verify=lambda *_args, **_kwargs: {},
            dcm_profile=lambda _config: {},
        )

        with self.assertRaisesRegex(ValueError, "not DICOM MWL mode"):
            service.get_dicom(1)

    def test_fhir_sync_delegates_to_injected_client(self):
        calls = []

        def sync(_repository, record_id, **values):
            calls.append((record_id, values["base_url"]))
            return {"id": record_id, "sync": {"status": FHIR_SYNC_STATUS_SYNCED}}

        service = FhirWorkflowService(
            FhirRepository(),
            inventory_types=("Patient",),
            medplum_base_url=lambda: "http://medplum/fhir/R4",
            auth_manager=lambda: object(),
            inventory_mapper=lambda item: item,
            diagnostic_fetcher=lambda *_args, **_kwargs: {},
            base_url_normalizer=lambda value: value,
            reference_url_builder=lambda base, reference: f"{base}/{reference}",
            json_request=lambda *_args, **_kwargs: (200, {}),
            operation_outcome=lambda payload: payload,
            upstream_status=lambda _message: None,
            record_sync=sync,
        )

        success, item = service.sync_record(7)

        self.assertTrue(success)
        self.assertEqual(7, item["id"])
        self.assertEqual([(7, "http://medplum/fhir/R4")], calls)

    def test_gdt_config_change_rejects_running_watcher(self):
        service = GdtWorkflowService(
            object(),
            {
                "GDT_BRIDGE_PATH": "bridge",
                "GDT_BRIDGE_FILENAME_PROFILE": "permissive",
            },
            Watcher(running=True),
            is_internal_file=lambda _path: False,
            has_supported_extension=lambda *_args, **_kwargs: True,
            filename_binding_matches=lambda *_args, **_kwargs: True,
            bridge_importer=lambda *_args, **_kwargs: {},
        )

        with self.assertRaises(GdtConfigurationConflict):
            service.update_bridge_config({"bridgePath": "new-bridge"})

    def test_oie_ack_updates_order_status(self):
        repository = OieRepository()
        service = self._oie_service(repository, lambda *_args, **_kwargs: "ACK")

        item = service.send_order(4, {})

        self.assertEqual(ORDER_STATUS_ACCEPTED, item["order_status"])
        self.assertEqual("AA", item["ack_code"])

    def test_oie_transport_failure_is_persisted(self):
        repository = OieRepository()

        def fail(*_args, **_kwargs):
            raise OSError("connection refused")

        service = self._oie_service(repository, fail)

        with self.assertRaises(OieTransportError) as raised:
            service.send_order(4, {})

        self.assertEqual(ORDER_STATUS_TRANSPORT_ERROR, raised.exception.item["order_status"])
        self.assertEqual("connection refused", raised.exception.item["transport_error"])

    def test_lab_check_all_skips_disabled_servers_and_decorates_results(self):
        repository = LabWorkflowRepository(
            [
                {"id": 1, "name": "disabled", "enabled": False},
                {"id": 2, "name": "enabled", "enabled": True},
            ]
        )
        health_checker = Mock(
            return_value={"id": 2, "name": "enabled", "enabled": True, "checked": True}
        )
        service = self._lab_service(repository, health_checker=health_checker)

        items = service.check_all_servers()

        health_checker.assert_called_once_with(repository, 2)
        self.assertEqual(
            [
                {"id": 1, "name": "disabled", "enabled": False, "available": True},
                {
                    "id": 2,
                    "name": "enabled",
                    "enabled": True,
                    "checked": True,
                    "available": True,
                },
            ],
            items,
        )

    def test_lab_smoke_all_records_disabled_and_keeps_partial_failures(self):
        servers = [
            {"id": 1, "name": "disabled", "enabled": False},
            {"id": 2, "name": "healthy", "enabled": True},
            {"id": 3, "name": "failed", "enabled": True},
        ]
        repository = LabWorkflowRepository(servers)

        def run_operation(**values):
            if values["server_id"] == 3:
                raise LabOperationError(
                    json.dumps(
                        {
                            "server": servers[2],
                            "operation": {"result": "failed"},
                            "error": "smoke failed",
                        }
                    )
                )
            return {"server": servers[1], "operation": {"result": "success"}}

        service = self._lab_service(repository, operation_runner=run_operation)

        results = service.smoke_all_servers()

        self.assertEqual(["skipped"], [item["result"] for item in repository.operations])
        self.assertEqual("Server is disabled.", repository.operations[0]["error_text"])
        self.assertEqual("success", results[1]["operation"]["result"])
        self.assertEqual("failed", results[2]["operation"]["result"])
        self.assertEqual("smoke failed", results[2]["error"])

    def test_lab_execute_operation_passes_repository_and_requested_target(self):
        repository = LabWorkflowRepository([])
        operation_runner = Mock(return_value={"operation": {"result": "success"}})
        service = self._lab_service(repository, operation_runner=operation_runner)

        result = service.execute_operation(9, "logs", lines=75)

        self.assertEqual("success", result["operation"]["result"])
        operation_runner.assert_called_once_with(
            app=service.app,
            store=repository,
            server_id=9,
            action="logs",
            lines=75,
        )

    def test_lab_operation_history_validates_server_and_preserves_repository_order(self):
        repository = LabWorkflowRepository([{"id": 9, "name": "target", "enabled": True}])
        repository.operations = [
            {"id": 1, "result": "failed"},
            {"id": 2, "result": "success"},
        ]
        service = self._lab_service(repository)

        self.assertEqual(
            [{"id": 2, "result": "success"}],
            service.operation_history(9, limit=1),
        )

        with self.assertRaises(StopIteration):
            service.operation_history(404)

    def test_dashboard_snapshot_preserves_resource_summary_and_event_assembly(self):
        repository = LabWorkflowRepository([])
        service = DashboardWorkflowService(
            object(), repository, health_check=Mock(), operation_runner=Mock()
        )
        items = [{"id": "fhir", "status": "healthy"}]
        resources = {"cpu": {"percent": 12}}
        summary = {"healthy": 1, "total": 1}
        events = [{"type": "status", "serviceId": "fhir"}]

        with (
            patch(
                "backend.services.lab_workflow.collect_dashboard_resource_snapshot",
                return_value=resources,
            ),
            patch(
                "backend.services.lab_workflow.dashboard_all_group_items",
                return_value=items,
            ),
            patch(
                "backend.services.lab_workflow.dashboard_summary",
                return_value=summary,
            ) as summarize,
            patch(
                "backend.services.lab_workflow.dashboard_events",
                return_value=events,
            ) as assemble_events,
        ):
            payload = service.snapshot()

        self.assertEqual(
            {"items": items, "summary": summary, "resources": resources, "events": events},
            payload,
        )
        summarize.assert_called_once_with(items, resources)
        assemble_events.assert_called_once_with(repository, items, resources)

    def test_dashboard_check_all_keeps_results_when_one_service_fails(self):
        repository = LabWorkflowRepository([])

        def check(_repository, service_id):
            if service_id == "broken":
                raise LabOperationError("unavailable")
            return [{"id": 1, "overallStatus": "Healthy"}]

        service = DashboardWorkflowService(object(), repository, health_check=check, operation_runner=Mock())
        service.snapshot = Mock(
            return_value={"items": [], "summary": {}, "resources": {}, "events": []}
        )

        with patch.dict(
            "backend.services.lab_workflow.LAB_DASHBOARD_SERVICE_GROUPS",
            {"healthy": {}, "broken": {}},
            clear=True,
        ):
            payload = service.check_all()

        self.assertEqual(
            [
                {
                    "serviceId": "healthy",
                    "servers": [{"id": 1, "overallStatus": "Healthy"}],
                },
                {"serviceId": "broken", "error": "unavailable"},
            ],
            payload["results"],
        )
        self.assertEqual([], payload["items"])

    def test_dashboard_action_targets_primary_and_ordered_backing_services(self):
        repository = LabWorkflowRepository([])
        runner = Mock(
            return_value={"operation": {"result": "success"}, "output": "restarted"}
        )
        service = DashboardWorkflowService(
            object(), repository, health_check=Mock(), operation_runner=runner
        )
        group = {
            "primary": "primary",
            "backingService": "primary-svc",
            "children": (
                {"service": "database"},
                {"service": "cache"},
            ),
        }
        servers = [
            {"id": 11, "name": "secondary"},
            {"id": 22, "name": "primary"},
        ]

        with (
            patch(
                "backend.services.lab_workflow.dashboard_servers_for_group",
                return_value=(group, servers),
            ),
            patch(
                "backend.services.lab_workflow.dashboard_group_item",
                return_value={"id": "group"},
            ),
        ):
            result = service.run_action("group", "restart", lines=40)

        runner.assert_called_once_with(
            app=service.app,
            store=repository,
            server_id=22,
            action="restart",
            lines=40,
            backing_services=["database", "cache", "primary-svc"],
        )
        self.assertEqual("restarted", result["output"])

    @staticmethod
    def _lab_service(repository, *, health_checker=None, operation_runner=None):
        return LabServerWorkflowService(
            object(),
            repository,
            health_checker=health_checker or Mock(),
            availability_decorator=lambda _app, item: {**item, "available": True},
            operation_runner=operation_runner or Mock(),
            operator_resolver=lambda: "tester",
        )

    @staticmethod
    def _oie_service(repository, sender):
        return OieWorkflowService(
            repository,
            repository,
            {
                "OIE_MLLP_ORDER_HOST": "oie",
                "OIE_MLLP_ORDER_PORT": 6600,
                "OIE_MLLP_RESULT_HOST": "0.0.0.0",
                "OIE_MLLP_RESULT_PORT": 6665,
            },
            Listener(),
            result_handler=lambda *_args: ("ACK", {}, 200),
            ack_parser=lambda _payload: {"code": "AA", "controlId": "1", "text": "ok"},
            order_sender_provider=lambda: sender,
        )


if __name__ == "__main__":
    unittest.main()
