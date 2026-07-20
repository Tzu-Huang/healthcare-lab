from ._owners import register_cases
from ._store_case_library import HealthcareLabStoreTests as _StoreCaseLibrary


class Dcm4cheeStoreTests(_StoreCaseLibrary):
    """Own dcm4chee mapping and Patient-sync persistence assertions."""


register_cases(
    Dcm4cheeStoreTests,
    (
        "test_dcm4chee_mapping_backfills_from_existing_attempts",
        "test_dcm4chee_patient_sync_mapping_attempt_and_patient_view",
        "test_dcm4chee_patient_sync_failure_is_retryable",
    ),
)
del _StoreCaseLibrary
