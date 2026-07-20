from ._owners import register_cases
from ._api_case_library import HealthcareLabApiTests as _ApiCaseLibrary


class FhirApiTests(_ApiCaseLibrary):
    """Own FHIR inventory, diagnostics, preview, and synchronization APIs."""


register_cases(
    FhirApiTests,
    (
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
)
del _ApiCaseLibrary
