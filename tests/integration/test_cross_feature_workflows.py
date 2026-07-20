from ._owners import register_cases
from ._api_case_library import HealthcareLabApiTests as _ApiCaseLibrary


class CrossFeatureWorkflowTests(_ApiCaseLibrary):
    """Own only workflows that assert coordination across feature boundaries."""


register_cases(
    CrossFeatureWorkflowTests,
    (
        "test_patient_api_creates_dicom_patient_and_syncs_dcm4chee",
        "test_patient_api_preserves_dicom_patient_when_dcm4chee_sync_fails",
        "test_patient_api_creates_fhir_patient_and_syncs_medplum",
        "test_patient_api_preserves_fhir_patient_when_sync_fails_and_retry_succeeds",
        "test_order_api_creates_dcm4chee_mwl_after_dicom_patient_sync",
        "test_gdt_result_api_imports_and_matches_local_order",
        "test_oie_result_api_persists_and_matches_order_result",
    ),
)
del _ApiCaseLibrary
