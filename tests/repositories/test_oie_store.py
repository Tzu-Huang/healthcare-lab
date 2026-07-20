from ._owners import register_cases
from ._store_case_library import HealthcareLabStoreTests as _StoreCaseLibrary


class OieStoreTests(_StoreCaseLibrary):
    """Own OIE result acknowledgements and transport persistence."""


register_cases(
    OieStoreTests,
    ("test_order_send_result_persists_ack_and_transport_error",),
)
del _StoreCaseLibrary
