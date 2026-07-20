from ._owners import register_cases
from ._api_case_library import HealthcareLabApiTests as _ApiCaseLibrary


class DashboardLabApiTests(_ApiCaseLibrary):
    """Own dashboard, lab server, health, and controlled runtime APIs."""


register_cases(
    DashboardLabApiTests,
    (
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
)
del _ApiCaseLibrary
