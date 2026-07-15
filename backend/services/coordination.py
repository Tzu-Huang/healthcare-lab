"""Explicit workflow adapters for protocol coordination retained by DemoStore."""

from __future__ import annotations

from typing import Any

from backend.services.order_workflow import OrderCoordinationPort
from backend.services.patient_workflow import PatientCoordinationPort


class PatientProtocolCoordinator:
    """Expose only the coordination operations owned by this workflow."""

    def __init__(self, facade: PatientCoordinationPort) -> None:
        self._facade = facade

    def begin_dcm4chee_result_refresh(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.begin_dcm4chee_result_refresh(*args, **kwargs)

    def build_dcm4chee_patient_adt_payload(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.build_dcm4chee_patient_adt_payload(*args, **kwargs)

    def complete_dcm4chee_result_refresh(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.complete_dcm4chee_result_refresh(*args, **kwargs)

    def create_dcm4chee_e2e_demo_fixture(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.create_dcm4chee_e2e_demo_fixture(*args, **kwargs)

    def create_dcm4chee_patient_sync_attempt(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.create_dcm4chee_patient_sync_attempt(*args, **kwargs)

    def create_patient_fhir_workflow_record(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.create_patient_fhir_workflow_record(*args, **kwargs)

    def dcm4chee_datasets_from_response_body(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.dcm4chee_datasets_from_response_body(*args, **kwargs)

    def dcm4chee_result_metadata_from_dataset(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.dcm4chee_result_metadata_from_dataset(*args, **kwargs)

    def get_dcm4chee_patient_sync_for_patient(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.get_dcm4chee_patient_sync_for_patient(*args, **kwargs)

    def get_patient_record(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.get_patient_record(*args, **kwargs)

    def get_fhir_workflow_record(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.get_fhir_workflow_record(*args, **kwargs)

    def list_dcm4chee_mwl_mappings_for_patient(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.list_dcm4chee_mwl_mappings_for_patient(*args, **kwargs)

    def mark_fhir_sync_failure(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.mark_fhir_sync_failure(*args, **kwargs)

    def mark_fhir_sync_success(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.mark_fhir_sync_success(*args, **kwargs)

    def mark_fhir_syncing(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.mark_fhir_syncing(*args, **kwargs)

    def record_fhir_sync_attempt(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.record_fhir_sync_attempt(*args, **kwargs)

    def record_dcm4chee_result_refresh_diagnostic(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.record_dcm4chee_result_refresh_diagnostic(*args, **kwargs)

    def update_dcm4chee_patient_sync_attempt_result(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.update_dcm4chee_patient_sync_attempt_result(*args, **kwargs)

    def update_dcm4chee_patient_sync_from_attempt(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.update_dcm4chee_patient_sync_from_attempt(*args, **kwargs)

    def upsert_dcm4chee_patient_sync(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.upsert_dcm4chee_patient_sync(*args, **kwargs)

    def upsert_dcm4chee_result_record(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.upsert_dcm4chee_result_record(*args, **kwargs)


class OrderProtocolCoordinator:
    """Expose only the coordination operations owned by this workflow."""

    def __init__(self, facade: OrderCoordinationPort) -> None:
        self._facade = facade

    def build_dcm4chee_mwl_payload(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.build_dcm4chee_mwl_payload(*args, **kwargs)

    def create_dcm4chee_mwl_attempt(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.create_dcm4chee_mwl_attempt(*args, **kwargs)

    def create_dcm4chee_mwl_profile_failure_attempt(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.create_dcm4chee_mwl_profile_failure_attempt(*args, **kwargs)

    def create_dcm4chee_mwl_verification_attempt(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.create_dcm4chee_mwl_verification_attempt(*args, **kwargs)

    def create_dcm4chee_order_record(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.create_dcm4chee_order_record(*args, **kwargs)

    def create_fhir_order_record(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.create_fhir_order_record(*args, **kwargs)

    def create_order_service_request_fhir_workflow_record(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.create_order_service_request_fhir_workflow_record(*args, **kwargs)

    def create_simulated_dcm4chee_ap_return(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.create_simulated_dcm4chee_ap_return(*args, **kwargs)

    def dcm4chee_datasets_from_response_body(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.dcm4chee_datasets_from_response_body(*args, **kwargs)

    def dcm4chee_e2e_evidence_for_order(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.dcm4chee_e2e_evidence_for_order(*args, **kwargs)

    def dcm4chee_identifiers_from_dataset(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.dcm4chee_identifiers_from_dataset(*args, **kwargs)

    def dcm4chee_identifiers_from_payload(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.dcm4chee_identifiers_from_payload(*args, **kwargs)

    def dcm4chee_identifiers_from_response_body(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.dcm4chee_identifiers_from_response_body(*args, **kwargs)

    def dcm4chee_mwl_verification_query_from_mapping(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.dcm4chee_mwl_verification_query_from_mapping(*args, **kwargs)

    def get_dcm4chee_mwl_mapping_for_order(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.get_dcm4chee_mwl_mapping_for_order(*args, **kwargs)

    def get_dcm4chee_patient_sync_for_patient(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.get_dcm4chee_patient_sync_for_patient(*args, **kwargs)

    def get_fhir_workflow_record(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.get_fhir_workflow_record(*args, **kwargs)

    def get_order_record(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.get_order_record(*args, **kwargs)

    def get_patient_record(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.get_patient_record(*args, **kwargs)

    def list_dcm4chee_mwl_attempts(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.list_dcm4chee_mwl_attempts(*args, **kwargs)

    def mark_fhir_sync_failure(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.mark_fhir_sync_failure(*args, **kwargs)

    def mark_fhir_sync_success(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.mark_fhir_sync_success(*args, **kwargs)

    def mark_fhir_syncing(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.mark_fhir_syncing(*args, **kwargs)

    def record_fhir_sync_attempt(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.record_fhir_sync_attempt(*args, **kwargs)

    def update_dcm4chee_mwl_attempt_result(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.update_dcm4chee_mwl_attempt_result(*args, **kwargs)

    def update_dcm4chee_mwl_mapping_from_attempt(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.update_dcm4chee_mwl_mapping_from_attempt(*args, **kwargs)

    def update_dcm4chee_mwl_verification_result(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.update_dcm4chee_mwl_verification_result(*args, **kwargs)

    def upsert_dcm4chee_mwl_mapping(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade.upsert_dcm4chee_mwl_mapping(*args, **kwargs)
