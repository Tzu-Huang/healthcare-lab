from ._owners import register_cases
from ._api_case_library import HealthcareLabApiTests as _ApiCaseLibrary


class PatientApiTests(_ApiCaseLibrary):
    """Own local Patient API and protocol-bound patient behavior."""


register_cases(
    PatientApiTests,
    (
        "test_patient_api_allocates_blank_mrn_and_rejects_duplicate",
        "test_integration_patient_lists_filter_to_their_own_protocol",
        "test_patient_api_creates_fhir_local_patient_without_medplum_base",
    ),
)
del _ApiCaseLibrary
