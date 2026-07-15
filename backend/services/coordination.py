"""Explicit allowlisted adapters for protocol coordination retained by DemoStore."""

from __future__ import annotations

from typing import Any


class _NarrowCoordinationAdapter:
    allowed_methods: frozenset[str] = frozenset()

    def __init__(self, facade: Any) -> None:
        self._facade = facade

    def __getattr__(self, name: str) -> Any:
        if name not in self.allowed_methods:
            raise AttributeError(name)
        return getattr(self._facade, name)


class PatientProtocolCoordinator(_NarrowCoordinationAdapter):
    allowed_methods = frozenset({
        "begin_dcm4chee_result_refresh", "build_dcm4chee_patient_adt_payload",
        "complete_dcm4chee_result_refresh", "create_dcm4chee_e2e_demo_fixture",
        "create_dcm4chee_patient_sync_attempt", "create_patient_fhir_workflow_record",
        "dcm4chee_datasets_from_response_body", "dcm4chee_result_metadata_from_dataset",
        "get_dcm4chee_patient_sync_for_patient", "get_patient_record",
        "get_fhir_workflow_record",
        "list_dcm4chee_mwl_mappings_for_patient", "mark_fhir_sync_failure",
        "mark_fhir_sync_success", "mark_fhir_syncing", "record_fhir_sync_attempt",
        "record_dcm4chee_result_refresh_diagnostic", "update_dcm4chee_patient_sync_attempt_result",
        "update_dcm4chee_patient_sync_from_attempt", "upsert_dcm4chee_patient_sync",
        "upsert_dcm4chee_result_record",
    })


class OrderProtocolCoordinator(_NarrowCoordinationAdapter):
    allowed_methods = frozenset({
        "build_dcm4chee_mwl_payload", "create_dcm4chee_mwl_attempt",
        "create_dcm4chee_mwl_profile_failure_attempt", "create_dcm4chee_mwl_verification_attempt",
        "create_dcm4chee_order_record", "create_fhir_order_record",
        "create_order_service_request_fhir_workflow_record", "create_simulated_dcm4chee_ap_return",
        "dcm4chee_datasets_from_response_body", "dcm4chee_e2e_evidence_for_order",
        "dcm4chee_identifiers_from_dataset", "dcm4chee_identifiers_from_payload",
        "dcm4chee_identifiers_from_response_body", "dcm4chee_mwl_verification_query_from_mapping",
        "get_dcm4chee_mwl_mapping_for_order", "get_dcm4chee_patient_sync_for_patient",
        "get_fhir_workflow_record", "get_order_record", "get_patient_record",
        "list_dcm4chee_mwl_attempts", "mark_fhir_sync_failure", "mark_fhir_sync_success",
        "mark_fhir_syncing", "record_fhir_sync_attempt", "update_dcm4chee_mwl_attempt_result",
        "update_dcm4chee_mwl_mapping_from_attempt", "update_dcm4chee_mwl_verification_result",
        "upsert_dcm4chee_mwl_mapping",
    })
