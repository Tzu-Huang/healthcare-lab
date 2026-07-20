from ._owners import register_cases
from ._api_case_library import HealthcareLabApiTests as _ApiCaseLibrary


class OrderApiTests(_ApiCaseLibrary):
    """Own local and FHIR Order API contracts."""


register_cases(
    OrderApiTests,
    (
        "test_order_api_creates_and_lists_local_orm_order",
        "test_order_api_creates_only_fhir_service_request",
        "test_order_api_preserves_fhir_service_request_sync_failure",
        "test_historical_fhir_task_is_excluded_from_active_api_contracts",
        "test_order_api_rejects_missing_patient",
    ),
)
del _ApiCaseLibrary
