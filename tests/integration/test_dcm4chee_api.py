from ._owners import register_cases
from ._api_case_library import HealthcareLabApiTests as _ApiCaseLibrary


class Dcm4cheeApiTests(_ApiCaseLibrary):
    """Own dcm4chee profile, MWL, sync, and result lifecycle contracts."""


register_cases(
    Dcm4cheeApiTests,
    (
        "test_dcm4chee_mwl_payload_uses_profile_and_generated_identifiers",
        "test_order_api_creates_dcm4chee_mwl_attempt",
        "test_order_api_blocks_dcm4chee_mwl_when_dicom_patient_sync_fails",
        "test_dcm4chee_sync_reuses_successful_mapping_without_duplicate_post",
        "test_dcm4chee_sync_endpoint_retries_failed_order_and_reuses_successful_mapping",
        "test_dcm4chee_sync_endpoint_preserves_order_when_retry_fails",
        "test_dcm4chee_sync_endpoint_rejects_unknown_and_non_dicom_orders",
        "test_dcm4chee_attempt_history_endpoint_lists_newest_first",
        "test_dcm4chee_mapping_retry_reuses_stable_identifiers",
        "test_dcm4chee_mapping_lookup_uses_reconciliation_identifiers",
        "test_dcm4chee_failed_retry_reads_back_before_duplicate_post",
        "test_dcm4chee_create_with_readback_failure_retries_readback_without_post",
        "test_dcm4chee_create_with_empty_readback_retries_readback_without_post",
        "test_order_api_records_dcm4chee_patient_missing_without_deleting_order",
        "test_order_api_records_dcm4chee_profile_validation_failure",
        "test_order_api_records_dcm4chee_missing_station_profile_failure",
        "test_dcm4chee_mwl_verify_endpoint_records_matching_order",
        "test_dcm4chee_mwl_verify_endpoint_records_empty_response",
        "test_dcm4chee_mwl_verify_keeps_patient_missing_precondition",
        "test_dcm4chee_mwl_verify_endpoint_records_mismatch_and_ambiguity",
        "test_dcm4chee_mwl_verify_endpoint_records_patient_missing_and_profile_failure",
        "test_patient_dcm4chee_result_ui_hooks_are_present",
        "test_dcm4chee_e2e_fixture_api_creates_demo_patient_order_and_evidence",
        "test_dcm4chee_simulated_ap_return_records_pdf_and_dicom_results",
        "test_dcm4chee_simulated_ap_return_sequence_keeps_pdf_and_dicom_visible",
        "test_patient_dcm4chee_result_refresh_reconciles_study_series_and_instance",
        "test_patient_dcm4chee_result_refresh_records_diagnostics",
        "test_dcm4chee_result_refresh_generation_is_unique_when_clock_does_not_advance",
        "test_dcm4chee_result_refresh_run_order_supersedes_updated_lower_id_row",
        "test_dcm4chee_result_refresh_publishes_only_completed_snapshots",
        "test_patient_dcm4chee_result_refresh_supersedes_stale_diagnostics",
        "test_patient_dcm4chee_result_refresh_records_duplicate_study_candidates",
    ),
)
del _ApiCaseLibrary
