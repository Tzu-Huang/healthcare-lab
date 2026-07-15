import inspect
import unittest

from backend.services.coordination import OrderProtocolCoordinator, PatientProtocolCoordinator
from backend.services.order_workflow import OrderCoordinationPort, OrderWorkflowService
from backend.services.patient_workflow import PatientCoordinationPort, PatientWorkflowService


class PatientOrderPortCompositionTests(unittest.TestCase):
    @staticmethod
    def coordinator(adapter, **overrides):
        operations = {
            name: (lambda *args, **kwargs: None)
            for name in inspect.signature(adapter.__init__).parameters
            if name != "self"
        }
        operations.update(overrides)
        return adapter(**operations)

    def test_patient_service_keeps_ledger_and_protocol_coordination_separate(self):
        ledger = object()
        coordination = object()
        service = PatientWorkflowService(
            ledger, {}, coordination=coordination, medplum_base_url=lambda: "",
            auth_manager=lambda: None, fhir_sync=lambda *args, **kwargs: None,
            dicom_patient_sync=lambda *args, **kwargs: None,
            dcm_result_refresh=lambda *args, **kwargs: {}, dcm_profile=lambda config: {},
        )
        self.assertIs(service._repository, ledger)
        self.assertIs(service._coordination, coordination)

    def test_order_service_keeps_ledger_and_protocol_coordination_separate(self):
        ledger = object()
        coordination = object()
        service = OrderWorkflowService(
            ledger, {}, coordination=coordination, medplum_base_url=lambda: "",
            auth_manager=lambda: None, fhir_sync=lambda *args, **kwargs: None,
            dcm_sync=lambda *args, **kwargs: None, dcm_verify=lambda *args, **kwargs: {},
            dcm_profile=lambda config: {},
        )
        self.assertIs(service._repository, ledger)
        self.assertIs(service._coordination, coordination)

    def test_services_route_named_capabilities_without_a_general_facade(self):
        patient_parts = [object() for _ in range(4)]
        patient = PatientWorkflowService(
            object(), {}, fhir_capability=patient_parts[0], patient_sync_capability=patient_parts[1],
            result_refresh_capability=patient_parts[2], fixture_capability=patient_parts[3],
            medplum_base_url=lambda: "", auth_manager=lambda: None,
            fhir_sync=lambda *args, **kwargs: None, dicom_patient_sync=lambda *args, **kwargs: None,
            dcm_result_refresh=lambda *args, **kwargs: {}, dcm_profile=lambda config: {},
        )
        order_parts = [object() for _ in range(3)]
        order = OrderWorkflowService(
            object(), {}, fhir_capability=order_parts[0], dcm_order_capability=order_parts[1],
            evidence_capability=order_parts[2], medplum_base_url=lambda: "", auth_manager=lambda: None,
            fhir_sync=lambda *args, **kwargs: None, dcm_sync=lambda *args, **kwargs: None,
            dcm_verify=lambda *args, **kwargs: {}, dcm_profile=lambda config: {},
        )
        self.assertEqual([patient._fhir, patient._patient_sync, patient._results, patient._fixture], patient_parts)
        self.assertEqual([order._fhir, order._dcm_order, order._evidence], order_parts)

    def test_coordination_adapters_reject_unrelated_facade_methods(self):
        patient = self.coordinator(PatientProtocolCoordinator, get_patient_record=lambda record_id: record_id)
        order = self.coordinator(OrderProtocolCoordinator)
        self.assertEqual(patient.get_patient_record(7), 7)
        with self.assertRaises(AttributeError):
            patient.list_lab_servers()
        with self.assertRaises(AttributeError):
            order.list_lab_servers()

    def test_coordination_adapters_explicitly_satisfy_workflow_ports(self):
        patient = PatientProtocolCoordinator.__new__(PatientProtocolCoordinator)
        order = OrderProtocolCoordinator.__new__(OrderProtocolCoordinator)

        self.assertIsInstance(patient, PatientCoordinationPort)
        self.assertIsInstance(order, OrderCoordinationPort)
        self.assertNotIn("__getattr__", PatientProtocolCoordinator.__dict__)
        self.assertNotIn("__getattr__", OrderProtocolCoordinator.__dict__)
        self.assertNotIn("_facade", PatientProtocolCoordinator.__dict__)
        self.assertNotIn("_facade", OrderProtocolCoordinator.__dict__)

        for protocol, adapter in (
            (PatientCoordinationPort, PatientProtocolCoordinator),
            (OrderCoordinationPort, OrderProtocolCoordinator),
        ):
            declared = {
                name
                for name, value in protocol.__dict__.items()
                if not name.startswith("_") and callable(value)
            }
            implemented = {
                name
                for name, value in adapter.__dict__.items()
                if not name.startswith("_") and callable(value)
            }
            self.assertEqual(declared, implemented)
            for method_name in declared:
                protocol_signature = inspect.signature(getattr(protocol, method_name))
                adapter_signature = inspect.signature(getattr(adapter, method_name))
                self.assertEqual(protocol_signature, adapter_signature)
                self.assertNotEqual("Any", protocol_signature.return_annotation)
                self.assertNotIn(
                    inspect.Parameter.VAR_POSITIONAL,
                    {parameter.kind for parameter in protocol_signature.parameters.values()},
                )
                self.assertNotIn(
                    inspect.Parameter.VAR_KEYWORD,
                    {parameter.kind for parameter in protocol_signature.parameters.values()},
                )


if __name__ == "__main__":
    unittest.main()
