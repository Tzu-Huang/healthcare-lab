import unittest

from backend.domain.statuses import (
    FHIR_SYNC_STATUS_SYNCED,
    ORDER_STATUS_ACCEPTED,
    ORDER_STATUS_TRANSPORT_ERROR,
)
from backend.services.fhir_workflow import FhirWorkflowService
from backend.services.gdt_workflow import GdtConfigurationConflict, GdtWorkflowService
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


class WorkflowServiceTest(unittest.TestCase):
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

    @staticmethod
    def _oie_service(repository, sender):
        return OieWorkflowService(
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
