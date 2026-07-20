from ._owners import register_cases
from ._api_case_library import HealthcareLabApiTests as _ApiCaseLibrary


class GdtApiTests(_ApiCaseLibrary):
    """Own GDT protocol, bridge, import, and watcher API contracts."""


register_cases(
    GdtApiTests,
    (
        "test_gdt_bridge_config_api_updates_shared_folder_path",
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
)
del _ApiCaseLibrary
