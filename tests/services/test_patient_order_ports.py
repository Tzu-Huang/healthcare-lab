import unittest

from backend.services.coordination import OrderProtocolCoordinator, PatientProtocolCoordinator
from backend.services.order_workflow import OrderWorkflowService
from backend.services.patient_workflow import PatientWorkflowService


class PatientOrderPortCompositionTests(unittest.TestCase):
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

    def test_coordination_adapters_reject_unrelated_facade_methods(self):
        facade = type("Facade", (), {"get_patient_record": lambda self, record_id: record_id,
                                      "list_lab_servers": lambda self: []})()
        patient = PatientProtocolCoordinator(facade)
        order = OrderProtocolCoordinator(facade)
        self.assertEqual(patient.get_patient_record(7), 7)
        with self.assertRaises(AttributeError):
            patient.list_lab_servers()
        with self.assertRaises(AttributeError):
            order.list_lab_servers()


if __name__ == "__main__":
    unittest.main()
