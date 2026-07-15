"""Explicit typed workflow adapters for protocol coordination retained by DemoStore."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.services.order_workflow import OrderCoordinationPort
from backend.services.patient_workflow import PatientCoordinationPort


class PatientProtocolCoordinator:
    def __init__(
        self, *,
        begin_dcm4chee_result_refresh: Callable[..., Any], build_dcm4chee_patient_adt_payload: Callable[..., Any], complete_dcm4chee_result_refresh: Callable[..., Any], create_dcm4chee_e2e_demo_fixture: Callable[..., Any],
        create_dcm4chee_patient_sync_attempt: Callable[..., Any], create_patient_fhir_workflow_record: Callable[..., Any], dcm4chee_datasets_from_response_body: Callable[..., Any], dcm4chee_result_metadata_from_dataset: Callable[..., Any],
        get_dcm4chee_patient_sync_for_patient: Callable[..., Any], get_patient_record: Callable[..., Any], get_fhir_workflow_record: Callable[..., Any], list_dcm4chee_mwl_mappings_for_patient: Callable[..., Any],
        mark_fhir_sync_failure: Callable[..., Any], mark_fhir_sync_success: Callable[..., Any], mark_fhir_syncing: Callable[..., Any], record_fhir_sync_attempt: Callable[..., Any],
        record_dcm4chee_result_refresh_diagnostic: Callable[..., Any], update_dcm4chee_patient_sync_attempt_result: Callable[..., Any], update_dcm4chee_patient_sync_from_attempt: Callable[..., Any], upsert_dcm4chee_patient_sync: Callable[..., Any],
        upsert_dcm4chee_result_record: Callable[..., Any],
    ) -> None:
        self._begin_dcm4chee_result_refresh = begin_dcm4chee_result_refresh
        self._build_dcm4chee_patient_adt_payload = build_dcm4chee_patient_adt_payload
        self._complete_dcm4chee_result_refresh = complete_dcm4chee_result_refresh
        self._create_dcm4chee_e2e_demo_fixture = create_dcm4chee_e2e_demo_fixture
        self._create_dcm4chee_patient_sync_attempt = create_dcm4chee_patient_sync_attempt
        self._create_patient_fhir_workflow_record = create_patient_fhir_workflow_record
        self._dcm4chee_datasets_from_response_body = dcm4chee_datasets_from_response_body
        self._dcm4chee_result_metadata_from_dataset = dcm4chee_result_metadata_from_dataset
        self._get_dcm4chee_patient_sync_for_patient = get_dcm4chee_patient_sync_for_patient
        self._get_patient_record = get_patient_record
        self._get_fhir_workflow_record = get_fhir_workflow_record
        self._list_dcm4chee_mwl_mappings_for_patient = list_dcm4chee_mwl_mappings_for_patient
        self._mark_fhir_sync_failure = mark_fhir_sync_failure
        self._mark_fhir_sync_success = mark_fhir_sync_success
        self._mark_fhir_syncing = mark_fhir_syncing
        self._record_fhir_sync_attempt = record_fhir_sync_attempt
        self._record_dcm4chee_result_refresh_diagnostic = record_dcm4chee_result_refresh_diagnostic
        self._update_dcm4chee_patient_sync_attempt_result = update_dcm4chee_patient_sync_attempt_result
        self._update_dcm4chee_patient_sync_from_attempt = update_dcm4chee_patient_sync_from_attempt
        self._upsert_dcm4chee_patient_sync = upsert_dcm4chee_patient_sync
        self._upsert_dcm4chee_result_record = upsert_dcm4chee_result_record

    def begin_dcm4chee_result_refresh(self, patient_record_id: int, refresh_generation: str, *, promote_existing: bool=False) -> None:
        return self._begin_dcm4chee_result_refresh(patient_record_id, refresh_generation, promote_existing=promote_existing)

    def build_dcm4chee_patient_adt_payload(self, patient: dict[str, Any], profile: dict[str, Any], *, event_type: str='A04', timestamp: str='') -> str:
        return self._build_dcm4chee_patient_adt_payload(patient, profile, event_type=event_type, timestamp=timestamp)

    def complete_dcm4chee_result_refresh(self, patient_record_id: int, refresh_generation: str) -> list[dict[str, Any]]:
        return self._complete_dcm4chee_result_refresh(patient_record_id, refresh_generation)

    def create_dcm4chee_e2e_demo_fixture(self, profile: dict[str, Any], *, uid_root: str='1.2.826.0.1.3680043.10.543') -> dict[str, Any]:
        return self._create_dcm4chee_e2e_demo_fixture(profile, uid_root=uid_root)

    def create_dcm4chee_patient_sync_attempt(self, patient_record_id: int, profile: dict[str, Any], *, operation_type: str='adt-create', request_url: str='', request_payload: str='', attempt_status: str='Pending sync', error_type: str='', error_text: str='', response_payload: str='', ack: dict[str, str] | None=None, patient_sync_id: int | None=None) -> dict[str, Any]:
        return self._create_dcm4chee_patient_sync_attempt(patient_record_id, profile, operation_type=operation_type, request_url=request_url, request_payload=request_payload, attempt_status=attempt_status, error_type=error_type, error_text=error_text, response_payload=response_payload, ack=ack, patient_sync_id=patient_sync_id)

    def create_patient_fhir_workflow_record(self, patient_record: dict[str, Any]) -> dict[str, Any]:
        return self._create_patient_fhir_workflow_record(patient_record)

    def dcm4chee_datasets_from_response_body(self, response_body: str) -> list[dict[str, Any]]:
        return self._dcm4chee_datasets_from_response_body(response_body)

    def dcm4chee_result_metadata_from_dataset(self, dataset: dict[str, Any]) -> dict[str, str]:
        return self._dcm4chee_result_metadata_from_dataset(dataset)

    def get_dcm4chee_patient_sync_for_patient(self, patient_record_id: int, profile: dict[str, Any] | None=None) -> dict[str, Any] | None:
        return self._get_dcm4chee_patient_sync_for_patient(patient_record_id, profile)

    def get_patient_record(self, record_id: int) -> dict[str, Any]:
        return self._get_patient_record(record_id)

    def get_fhir_workflow_record(self, record_id: int) -> dict[str, Any]:
        return self._get_fhir_workflow_record(record_id)

    def list_dcm4chee_mwl_mappings_for_patient(self, patient_record_id: int) -> list[dict[str, Any]]:
        return self._list_dcm4chee_mwl_mappings_for_patient(patient_record_id)

    def mark_fhir_sync_failure(self, record_id: int, *, error_text: str, operation_outcome: dict[str, Any] | None=None) -> dict[str, Any]:
        return self._mark_fhir_sync_failure(record_id, error_text=error_text, operation_outcome=operation_outcome)

    def mark_fhir_sync_success(self, record_id: int, *, medplum_resource_id: str, medplum_resource_reference: str='') -> dict[str, Any]:
        return self._mark_fhir_sync_success(record_id, medplum_resource_id=medplum_resource_id, medplum_resource_reference=medplum_resource_reference)

    def mark_fhir_syncing(self, record_id: int) -> dict[str, Any]:
        return self._mark_fhir_syncing(record_id)

    def record_fhir_sync_attempt(self, record_id: int, *, method: str, request_url: str, request_payload: dict[str, Any] | None=None, http_status: int | None=None, response_payload: dict[str, Any] | None=None, operation_outcome: dict[str, Any] | None=None, error_text: str='') -> dict[str, Any]:
        return self._record_fhir_sync_attempt(record_id, method=method, request_url=request_url, request_payload=request_payload, http_status=http_status, response_payload=response_payload, operation_outcome=operation_outcome, error_text=error_text)

    def record_dcm4chee_result_refresh_diagnostic(self, *, patient_record_id: int, profile: dict[str, Any], status: str, query_url: str='', query_payload: dict[str, Any] | None=None, diagnostic_payload: dict[str, Any] | None=None, refresh_generation: str='') -> dict[str, Any]:
        return self._record_dcm4chee_result_refresh_diagnostic(patient_record_id=patient_record_id, profile=profile, status=status, query_url=query_url, query_payload=query_payload, diagnostic_payload=diagnostic_payload, refresh_generation=refresh_generation)

    def update_dcm4chee_patient_sync_attempt_result(self, attempt_id: int, *, attempt_status: str, response_payload: str='', ack: dict[str, str] | None=None, error_type: str='', error_text: str='') -> dict[str, Any]:
        return self._update_dcm4chee_patient_sync_attempt_result(attempt_id, attempt_status=attempt_status, response_payload=response_payload, ack=ack, error_type=error_type, error_text=error_text)

    def update_dcm4chee_patient_sync_from_attempt(self, patient_sync_id: int, attempt: dict[str, Any], *, sync_status: str) -> dict[str, Any]:
        return self._update_dcm4chee_patient_sync_from_attempt(patient_sync_id, attempt, sync_status=sync_status)

    def upsert_dcm4chee_patient_sync(self, patient_record_id: int, profile: dict[str, Any], *, sync_status: str='Pending sync', increment_retry: bool=False) -> dict[str, Any]:
        return self._upsert_dcm4chee_patient_sync(patient_record_id, profile, sync_status=sync_status, increment_retry=increment_retry)

    def upsert_dcm4chee_result_record(self, metadata: dict[str, str], profile: dict[str, Any], *, patient_record_id: int | None=None, query_url: str='', query_payload: dict[str, Any] | None=None, raw_metadata: dict[str, Any] | None=None, refresh_generation: str='') -> dict[str, Any]:
        return self._upsert_dcm4chee_result_record(metadata, profile, patient_record_id=patient_record_id, query_url=query_url, query_payload=query_payload, raw_metadata=raw_metadata, refresh_generation=refresh_generation)


class OrderProtocolCoordinator:
    def __init__(
        self, *,
        build_dcm4chee_mwl_payload: Callable[..., Any], create_dcm4chee_mwl_attempt: Callable[..., Any], create_dcm4chee_mwl_profile_failure_attempt: Callable[..., Any], create_dcm4chee_mwl_verification_attempt: Callable[..., Any],
        create_dcm4chee_order_record: Callable[..., Any], create_fhir_order_record: Callable[..., Any], create_order_service_request_fhir_workflow_record: Callable[..., Any], create_simulated_dcm4chee_ap_return: Callable[..., Any],
        dcm4chee_datasets_from_response_body: Callable[..., Any], dcm4chee_e2e_evidence_for_order: Callable[..., Any], dcm4chee_identifiers_from_dataset: Callable[..., Any], dcm4chee_identifiers_from_payload: Callable[..., Any],
        dcm4chee_identifiers_from_response_body: Callable[..., Any], dcm4chee_mwl_verification_query_from_mapping: Callable[..., Any], get_dcm4chee_mwl_mapping_for_order: Callable[..., Any], get_dcm4chee_patient_sync_for_patient: Callable[..., Any],
        get_fhir_workflow_record: Callable[..., Any], get_order_record: Callable[..., Any], get_patient_record: Callable[..., Any], list_dcm4chee_mwl_attempts: Callable[..., Any],
        mark_fhir_sync_failure: Callable[..., Any], mark_fhir_sync_success: Callable[..., Any], mark_fhir_syncing: Callable[..., Any], record_fhir_sync_attempt: Callable[..., Any],
        update_dcm4chee_mwl_attempt_result: Callable[..., Any], update_dcm4chee_mwl_mapping_from_attempt: Callable[..., Any], update_dcm4chee_mwl_verification_result: Callable[..., Any], upsert_dcm4chee_mwl_mapping: Callable[..., Any],
    ) -> None:
        self._build_dcm4chee_mwl_payload = build_dcm4chee_mwl_payload
        self._create_dcm4chee_mwl_attempt = create_dcm4chee_mwl_attempt
        self._create_dcm4chee_mwl_profile_failure_attempt = create_dcm4chee_mwl_profile_failure_attempt
        self._create_dcm4chee_mwl_verification_attempt = create_dcm4chee_mwl_verification_attempt
        self._create_dcm4chee_order_record = create_dcm4chee_order_record
        self._create_fhir_order_record = create_fhir_order_record
        self._create_order_service_request_fhir_workflow_record = create_order_service_request_fhir_workflow_record
        self._create_simulated_dcm4chee_ap_return = create_simulated_dcm4chee_ap_return
        self._dcm4chee_datasets_from_response_body = dcm4chee_datasets_from_response_body
        self._dcm4chee_e2e_evidence_for_order = dcm4chee_e2e_evidence_for_order
        self._dcm4chee_identifiers_from_dataset = dcm4chee_identifiers_from_dataset
        self._dcm4chee_identifiers_from_payload = dcm4chee_identifiers_from_payload
        self._dcm4chee_identifiers_from_response_body = dcm4chee_identifiers_from_response_body
        self._dcm4chee_mwl_verification_query_from_mapping = dcm4chee_mwl_verification_query_from_mapping
        self._get_dcm4chee_mwl_mapping_for_order = get_dcm4chee_mwl_mapping_for_order
        self._get_dcm4chee_patient_sync_for_patient = get_dcm4chee_patient_sync_for_patient
        self._get_fhir_workflow_record = get_fhir_workflow_record
        self._get_order_record = get_order_record
        self._get_patient_record = get_patient_record
        self._list_dcm4chee_mwl_attempts = list_dcm4chee_mwl_attempts
        self._mark_fhir_sync_failure = mark_fhir_sync_failure
        self._mark_fhir_sync_success = mark_fhir_sync_success
        self._mark_fhir_syncing = mark_fhir_syncing
        self._record_fhir_sync_attempt = record_fhir_sync_attempt
        self._update_dcm4chee_mwl_attempt_result = update_dcm4chee_mwl_attempt_result
        self._update_dcm4chee_mwl_mapping_from_attempt = update_dcm4chee_mwl_mapping_from_attempt
        self._update_dcm4chee_mwl_verification_result = update_dcm4chee_mwl_verification_result
        self._upsert_dcm4chee_mwl_mapping = upsert_dcm4chee_mwl_mapping

    def build_dcm4chee_mwl_payload(self, order: dict[str, Any], profile: dict[str, Any], *, uid_root: str='1.2.826.0.1.3680043.10.543') -> dict[str, Any]:
        return self._build_dcm4chee_mwl_payload(order, profile, uid_root=uid_root)

    def create_dcm4chee_mwl_attempt(self, order_record_id: int, profile: dict[str, Any], *, uid_root: str='1.2.826.0.1.3680043.10.543', request_url: str='', request_payload: dict[str, Any] | None=None, attempt_status: str='Pending sync', error_type: str='', error_text: str='', http_status: int | None=None, response_body: str='', operation_type: str='create', mapping_id: int | None=None) -> dict[str, Any]:
        return self._create_dcm4chee_mwl_attempt(order_record_id, profile, uid_root=uid_root, request_url=request_url, request_payload=request_payload, attempt_status=attempt_status, error_type=error_type, error_text=error_text, http_status=http_status, response_body=response_body, operation_type=operation_type, mapping_id=mapping_id)

    def create_dcm4chee_mwl_profile_failure_attempt(self, order_record_id: int, profile: dict[str, Any], *, uid_root: str='1.2.826.0.1.3680043.10.543', request_url: str='', diagnostics: dict[str, Any] | None=None) -> dict[str, Any]:
        return self._create_dcm4chee_mwl_profile_failure_attempt(order_record_id, profile, uid_root=uid_root, request_url=request_url, diagnostics=diagnostics)

    def create_dcm4chee_mwl_verification_attempt(self, order_record_id: int, mapping: dict[str, Any], *, request_url: str, query_criteria: dict[str, str], attempt_status: str='Pending sync', error_type: str='', error_text: str='', http_status: int | None=None, response_body: str='') -> dict[str, Any]:
        return self._create_dcm4chee_mwl_verification_attempt(order_record_id, mapping, request_url=request_url, query_criteria=query_criteria, attempt_status=attempt_status, error_type=error_type, error_text=error_text, http_status=http_status, response_body=response_body)

    def create_dcm4chee_order_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._create_dcm4chee_order_record(payload)

    def create_fhir_order_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._create_fhir_order_record(payload)

    def create_order_service_request_fhir_workflow_record(self, order: dict[str, Any]) -> dict[str, Any]:
        return self._create_order_service_request_fhir_workflow_record(order)

    def create_simulated_dcm4chee_ap_return(self, order_record_id: int, profile: dict[str, Any], *, result_type: str='both', artifact_url: str='', artifact_path: str='') -> dict[str, Any]:
        return self._create_simulated_dcm4chee_ap_return(order_record_id, profile, result_type=result_type, artifact_url=artifact_url, artifact_path=artifact_path)

    def dcm4chee_datasets_from_response_body(self, response_body: str) -> list[dict[str, Any]]:
        return self._dcm4chee_datasets_from_response_body(response_body)

    def dcm4chee_e2e_evidence_for_order(self, order_record_id: int, profile: dict[str, Any]) -> dict[str, Any]:
        return self._dcm4chee_e2e_evidence_for_order(order_record_id, profile)

    def dcm4chee_identifiers_from_dataset(self, dataset: dict[str, Any]) -> dict[str, str]:
        return self._dcm4chee_identifiers_from_dataset(dataset)

    def dcm4chee_identifiers_from_payload(self, order: dict[str, Any], profile: dict[str, Any], *, uid_root: str='1.2.826.0.1.3680043.10.543', payload: dict[str, Any] | None=None) -> dict[str, str]:
        return self._dcm4chee_identifiers_from_payload(order, profile, uid_root=uid_root, payload=payload)

    def dcm4chee_identifiers_from_response_body(self, response_body: str) -> dict[str, str]:
        return self._dcm4chee_identifiers_from_response_body(response_body)

    def dcm4chee_mwl_verification_query_from_mapping(self, mapping: dict[str, Any]) -> dict[str, str]:
        return self._dcm4chee_mwl_verification_query_from_mapping(mapping)

    def get_dcm4chee_mwl_mapping_for_order(self, order_record_id: int) -> dict[str, Any] | None:
        return self._get_dcm4chee_mwl_mapping_for_order(order_record_id)

    def get_dcm4chee_patient_sync_for_patient(self, patient_record_id: int, profile: dict[str, Any] | None=None) -> dict[str, Any] | None:
        return self._get_dcm4chee_patient_sync_for_patient(patient_record_id, profile)

    def get_fhir_workflow_record(self, record_id: int) -> dict[str, Any]:
        return self._get_fhir_workflow_record(record_id)

    def get_order_record(self, record_id: int) -> dict[str, Any]:
        return self._get_order_record(record_id)

    def get_patient_record(self, record_id: int) -> dict[str, Any]:
        return self._get_patient_record(record_id)

    def list_dcm4chee_mwl_attempts(self, order_record_id: int | None=None) -> list[dict[str, Any]]:
        return self._list_dcm4chee_mwl_attempts(order_record_id)

    def mark_fhir_sync_failure(self, record_id: int, *, error_text: str, operation_outcome: dict[str, Any] | None=None) -> dict[str, Any]:
        return self._mark_fhir_sync_failure(record_id, error_text=error_text, operation_outcome=operation_outcome)

    def mark_fhir_sync_success(self, record_id: int, *, medplum_resource_id: str, medplum_resource_reference: str='') -> dict[str, Any]:
        return self._mark_fhir_sync_success(record_id, medplum_resource_id=medplum_resource_id, medplum_resource_reference=medplum_resource_reference)

    def mark_fhir_syncing(self, record_id: int) -> dict[str, Any]:
        return self._mark_fhir_syncing(record_id)

    def record_fhir_sync_attempt(self, record_id: int, *, method: str, request_url: str, request_payload: dict[str, Any] | None=None, http_status: int | None=None, response_payload: dict[str, Any] | None=None, operation_outcome: dict[str, Any] | None=None, error_text: str='') -> dict[str, Any]:
        return self._record_fhir_sync_attempt(record_id, method=method, request_url=request_url, request_payload=request_payload, http_status=http_status, response_payload=response_payload, operation_outcome=operation_outcome, error_text=error_text)

    def update_dcm4chee_mwl_attempt_result(self, attempt_id: int, *, attempt_status: str, http_status: int | None=None, response_body: str='', error_type: str='', error_text: str='') -> dict[str, Any]:
        return self._update_dcm4chee_mwl_attempt_result(attempt_id, attempt_status=attempt_status, http_status=http_status, response_body=response_body, error_type=error_type, error_text=error_text)

    def update_dcm4chee_mwl_mapping_from_attempt(self, order_record_id: int, *, attempt_id: int | None, sync_status: str, http_status: int | None=None, response_body: str='', error_type: str='', error_text: str='', error_payload: dict[str, Any] | None=None, readback_payload: dict[str, Any] | list[Any] | None=None, identifiers: dict[str, str] | None=None) -> dict[str, Any]:
        return self._update_dcm4chee_mwl_mapping_from_attempt(order_record_id, attempt_id=attempt_id, sync_status=sync_status, http_status=http_status, response_body=response_body, error_type=error_type, error_text=error_text, error_payload=error_payload, readback_payload=readback_payload, identifiers=identifiers)

    def update_dcm4chee_mwl_verification_result(self, order_record_id: int, *, attempt_id: int, verification_status: str, method: str, query_criteria: dict[str, Any], match_payload: dict[str, Any] | None=None, error_type: str='', error_text: str='', error_payload: dict[str, Any] | None=None) -> dict[str, Any]:
        return self._update_dcm4chee_mwl_verification_result(order_record_id, attempt_id=attempt_id, verification_status=verification_status, method=method, query_criteria=query_criteria, match_payload=match_payload, error_type=error_type, error_text=error_text, error_payload=error_payload)

    def upsert_dcm4chee_mwl_mapping(self, order_record_id: int, profile: dict[str, Any], *, uid_root: str='1.2.826.0.1.3680043.10.543', request_payload: dict[str, Any] | None=None, sync_status: str='Pending sync', increment_retry: bool=False) -> dict[str, Any]:
        return self._upsert_dcm4chee_mwl_mapping(order_record_id, profile, uid_root=uid_root, request_payload=request_payload, sync_status=sync_status, increment_retry=increment_retry)
