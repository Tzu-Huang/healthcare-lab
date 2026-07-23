import ast
from pathlib import Path
import unittest


INTEGRATION_OWNER_INVENTORY = {
    "integration/test_application_shell.py": (
        "test_index_serves_dashboard_only_ui",
        "test_native_module_assets_use_conditional_revalidation",
        "test_frontend_exposes_dashboard_children_and_gdt_workspace_order_action",
        "test_sidebar_views_hide_inactive_pages",
        "test_only_healthcare_lab_routes_are_registered",
        "test_settings_readiness_is_composed_without_openemr",
        "test_fresh_settings_readiness_requires_operator_setup",
    ),
    "integration/test_cross_feature_workflows.py": (
        "test_patient_api_creates_dicom_patient_and_syncs_dcm4chee",
        "test_patient_api_preserves_dicom_patient_when_dcm4chee_sync_fails",
        "test_patient_api_creates_fhir_patient_and_syncs_medplum",
        "test_patient_api_preserves_fhir_patient_when_sync_fails_and_retry_succeeds",
        "test_order_api_creates_dcm4chee_mwl_after_dicom_patient_sync",
        "test_gdt_result_api_imports_and_matches_local_order",
        "test_oie_result_api_persists_and_matches_order_result",
    ),
    "integration/test_dashboard_lab_api.py": (
        "test_dashboard_summary_counts_running_primary_and_child_services",
        "test_dashboard_services_exposes_three_allowlisted_groups_with_children",
        "test_dashboard_rejects_unsupported_service_ids",
        "test_dashboard_action_mapping_and_restart_preview",
        "test_dashboard_action_mapping_helper",
        "test_dashboard_check_runs_health_check_for_primary_service",
        "test_dashboard_child_action_targets_only_allowlisted_child",
        "test_dashboard_resource_snapshot_falls_back_when_docker_stats_unavailable",
        "test_dashboard_resource_snapshot_prefers_docker_socket",
        "test_lab_server_registry_seeds_default_services",
        "test_dcm4chee_profile_api_returns_local_defaults",
        "test_dcm4chee_profile_archive_defaults_preserve_configured_host",
        "test_dcm4chee_profile_diagnostics_report_missing_values",
        "test_dcm4chee_profile_named_route_rejects_unknown_profile",
        "test_dcm4chee_profile_diagnostics_handles_malformed_env_values",
        "test_dcm4chee_smoke_reports_out_of_range_dimse_port",
        "test_lab_server_create_update_and_detail_api",
        "test_lab_server_validation_rejects_invalid_payload",
        "test_lab_operation_history_exposes_internal_logs_operation",
        "test_lab_application_check_uses_tcp_when_host_and_port_are_configured",
        "test_internal_lab_tool_application_check_ignores_host_mapped_port",
        "test_oie_smoke_uses_compose_network_endpoints",
        "test_medplum_smoke_distinguishes_service_request_unauthorized",
        "test_medplum_smoke_treats_empty_diagnostic_report_bundle_as_healthy",
        "test_openemr_gdt_backend_verify_reports_healthy_steps",
        "test_openemr_gdt_backend_verify_reports_mariadb_connection_failure",
        "test_openemr_gdt_backend_verify_reports_missing_order_schema_failure",
        "test_openemr_gdt_backend_verify_degrades_when_no_ecg_orders_exist",
        "test_lab_compose_operation_adapter_builds_allowlisted_command",
        "test_lab_compose_operation_adapter_parses_array_and_line_json_status",
        "test_default_compose_omits_openemr_and_keeps_gdt_in_lab_app",
        "test_docker_socket_stop_uses_short_grace_period",
        "test_lab_health_status_derivation",
    ),
    "integration/test_dcm4chee_api.py": (
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
        "test_patient_dcm4chee_result_refresh_ignores_empty_results_and_records_failures",
        "test_dcm4chee_result_refresh_generation_is_unique_when_clock_does_not_advance",
        "test_dcm4chee_result_refresh_run_order_supersedes_updated_lower_id_row",
        "test_dcm4chee_result_refresh_publishes_only_completed_snapshots",
        "test_patient_dcm4chee_result_refresh_replaces_empty_snapshot_with_results",
        "test_patient_dcm4chee_result_refresh_records_duplicate_study_candidates",
    ),
    "integration/test_fhir_api.py": (
        "test_fhir_mapping_and_record_apis_expose_local_sync_status",
        "test_fhir_inventory_exposes_patient_relations_and_local_preview",
        "test_fhir_record_preview_uses_medplum_live_json_for_synced_resource",
        "test_fhir_record_preview_falls_back_to_local_json_when_live_fetch_fails",
        "test_fhir_diagnostic_reports_fetches_patient_bundle_and_summaries",
        "test_fhir_diagnostic_reports_empty_bundle_is_successful",
        "test_fhir_diagnostic_reports_falls_back_when_based_on_search_is_unsupported",
        "test_fhir_diagnostic_reports_prefers_based_on_when_subject_search_fails",
        "test_fhir_diagnostic_reports_surfaces_unauthorized_fetch",
        "test_fhir_diagnostic_reports_rejects_malformed_bundle",
        "test_fhir_resource_preview_fetches_live_binary_reference",
        "test_fhir_sync_reuses_existing_medplum_resource_by_identifier",
        "test_fhir_sync_creates_once_when_identifier_is_missing",
        "test_fhir_sync_updates_existing_medplum_resource_after_local_change",
        "test_fhir_sync_failure_preserves_operation_outcome",
        "test_fhir_sync_validation_failure_marks_record_failed",
    ),
    "integration/test_gdt_api.py": (
        "test_gdt_bridge_config_api_updates_shared_folder_path",
        "test_gdt_bridge_config_rejects_missing_folders_without_creating_them",
        "test_gdt_order_api_creates_and_lists_local_ecg_order_without_openemr",
        "test_gdt_bridge_write_import_demo_and_workbench",
        "test_gdt_bridge_batch_import_delete_mode_removes_successful_exchange_file",
        "test_gdt_bridge_batch_import_reports_disposition_warning_after_successful_persistence",
        "test_gdt_bridge_batch_import_skips_temp_files_and_moves_parse_failures_to_error",
        "test_gdt_bridge_batch_import_applies_gdt35_filename_binding",
        "test_gdt_bridge_inbox_lists_gdt21_sequence_extension_files",
        "test_gdt_bridge_batch_import_requires_stable_observation_before_processing",
        "test_gdt_bridge_batch_import_uses_fifo_candidate_order",
        "test_gdt_bridge_watcher_api_lifecycle_and_path_change_guard",
        "test_gdt_order_api_rejects_non_mvp_test_codes",
        "test_parse_hl7_ack_extracts_msa_fields",
        "test_parse_oru_summary_extracts_matching_fields",
    ),
    "integration/test_oie_api.py": (
        "test_oie_settings_api_returns_secret_safe_local_defaults",
        "test_oie_settings_api_updates_profile_without_changing_listener_runtime",
        "test_oie_settings_api_validates_fields_and_rejects_atomically",
        "test_oie_settings_api_preserves_replaces_and_never_exposes_password",
        "test_oie_result_api_keeps_unknown_patient_unmatched",
        "test_oie_result_api_rejects_unsupported_message_with_failure_ack",
        "test_oie_result_api_requires_msh_10_without_accepting_a_result",
        "test_oie_result_redelivery_is_acknowledged_without_duplicate_insert",
        "test_oie_result_listener_status_defaults_to_port_6665",
        "test_oie_result_listener_start_reports_bind_failure",
        "test_oie_send_order_records_ack_acceptance",
        "test_oie_send_order_uses_configured_default_endpoint",
        "test_oie_send_order_records_transport_error",
    ),
    "integration/test_order_api.py": (
        "test_order_api_creates_and_lists_local_orm_order",
        "test_order_api_creates_only_fhir_service_request",
        "test_order_api_preserves_fhir_service_request_sync_failure",
        "test_historical_fhir_task_is_excluded_from_active_api_contracts",
        "test_order_api_rejects_missing_patient",
    ),
    "integration/test_patient_api.py": (
        "test_patient_api_allocates_blank_mrn_and_rejects_duplicate",
        "test_integration_patient_lists_filter_to_their_own_protocol",
        "test_patient_api_creates_fhir_local_patient_without_medplum_base",
    ),
}

REPOSITORY_OWNER_INVENTORY = {
    "repositories/test_dcm4chee_store.py": (
        "test_dcm4chee_mapping_backfills_from_existing_attempts",
        "test_dcm4chee_patient_sync_mapping_attempt_and_patient_view",
        "test_dcm4chee_patient_sync_failure_is_retryable",
    ),
    "repositories/test_fhir_store.py": (
        "test_fhir_patient_common_fields_and_paired_ledger_metadata",
        "test_fhir_workflow_record_persists_status_identifier_and_resource",
        "test_fhir_workflow_mapping_metadata_covers_supported_resources",
        "test_fhir_order_builds_service_request_and_requires_synced_patient",
        "test_fhir_sync_attempts_and_failure_details_are_preserved",
        "test_fhir_sync_success_preserves_medplum_reference_and_ordering",
        "test_fhir_synced_record_update_marks_changed_payload_pending",
    ),
    "repositories/test_gdt_store.py": (
        "test_gdt_order_creation_persists_fixed_ekg01_order",
        "test_gdt_patient_number_override_is_snapshotted",
        "test_gdt_result_import_persists_canonical_message_attachments_and_events",
        "test_gdt_unmatched_result_is_persisted",
        "test_gdt_result_without_order_identifier_does_not_guess_latest_patient_order",
        "test_gdt_order_events_do_not_include_other_order_lifecycle_events",
        "test_gdt_order_creation_rejects_non_mvp_8402_codes",
    ),
    "repositories/test_oie_store.py": (
        "test_order_send_result_persists_ack_and_transport_error",
    ),
    "repositories/test_patient_order_store.py": (
        "test_patient_mrn_sequence_allocates_persists_and_does_not_reuse_deleted_values",
        "test_patient_mrn_sequence_skips_explicit_collision",
        "test_duplicate_explicit_mrn_is_rejected_without_patient_side_effects",
        "test_noncanonical_explicit_mrn_is_rejected_without_side_effects",
        "test_database_enforces_normalized_mrn_uniqueness",
        "test_patient_protocol_filter_and_workbenches_keep_protocol_boundaries",
        "test_local_order_record_persists_orm_payload",
        "test_local_patient_modes_generate_protocol_specific_payloads",
        "test_generated_mrn_propagates_across_patient_modes_and_into_order_snapshot",
    ),
    "repositories/test_template_compatibility.py": (
        "test_healthcare_lab_template_excludes_ap_simulator_views",
    ),
}


def _test_method_names(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            names.extend(
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and child.name.startswith("test_")
            )
    return tuple(names)


class Zac64OwnershipContractTests(unittest.TestCase):
    def test_owner_inventory_is_complete_and_aggregate_libraries_are_removed(self):
        tests_root = Path(__file__).resolve().parent
        legacy_paths = (
            "integration/_api_case_library.py",
            "integration/_owners.py",
            "integration/test_app.py",
            "repositories/_store_case_library.py",
            "repositories/_owners.py",
            "repositories/test_lab_store.py",
        )
        for relative in legacy_paths:
            self.assertFalse((tests_root / relative).exists(), relative)

        integration_names = []
        for relative, expected in INTEGRATION_OWNER_INVENTORY.items():
            actual = _test_method_names(tests_root / relative)
            self.assertEqual(actual, expected, relative)
            integration_names.extend(actual)
        self.assertEqual(len(integration_names), 131)
        self.assertEqual(len(set(integration_names)), 131)

        repository_names = []
        for relative, expected in REPOSITORY_OWNER_INVENTORY.items():
            actual = _test_method_names(tests_root / relative)
            self.assertEqual(actual, expected, relative)
            repository_names.extend(actual)
        self.assertEqual(len(repository_names), 28)
        self.assertEqual(len(set(repository_names)), 28)


if __name__ == "__main__":
    unittest.main()
