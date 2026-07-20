from ._owners import register_cases
from ._store_case_library import HealthcareLabStoreTests as _StoreCaseLibrary


class FhirStoreTests(_StoreCaseLibrary):
    """Own FHIR ledger, order, mapping, and synchronization persistence."""


register_cases(
    FhirStoreTests,
    (
        "test_fhir_patient_common_fields_and_paired_ledger_metadata",
        "test_fhir_workflow_record_persists_status_identifier_and_resource",
        "test_fhir_workflow_mapping_metadata_covers_supported_resources",
        "test_fhir_order_builds_service_request_and_requires_synced_patient",
        "test_fhir_sync_attempts_and_failure_details_are_preserved",
        "test_fhir_sync_success_preserves_medplum_reference_and_ordering",
        "test_fhir_synced_record_update_marks_changed_payload_pending",
    ),
)
del _StoreCaseLibrary
