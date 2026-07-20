from ._owners import register_cases
from ._store_case_library import HealthcareLabStoreTests as _StoreCaseLibrary


class PatientOrderStoreTests(_StoreCaseLibrary):
    """Own Patient and generic Order persistence assertions."""


register_cases(
    PatientOrderStoreTests,
    (
        "test_patient_mrn_sequence_allocates_persists_and_does_not_reuse_deleted_values",
        "test_patient_mrn_sequence_skips_explicit_collision",
        "test_duplicate_explicit_mrn_is_rejected_without_patient_side_effects",
        "test_patient_protocol_filter_and_workbenches_keep_protocol_boundaries",
        "test_local_order_record_persists_orm_payload",
        "test_local_patient_modes_generate_protocol_specific_payloads",
        "test_generated_mrn_propagates_across_patient_modes_and_into_order_snapshot",
    ),
)
del _StoreCaseLibrary
