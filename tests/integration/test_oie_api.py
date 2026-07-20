from ._owners import register_cases
from ._api_case_library import HealthcareLabApiTests as _ApiCaseLibrary


class OieApiTests(_ApiCaseLibrary):
    """Own OIE settings, result listener, and send-operation APIs."""


register_cases(
    OieApiTests,
    (
        "test_oie_settings_api_returns_secret_safe_local_defaults",
        "test_oie_settings_api_updates_profile_without_changing_listener_runtime",
        "test_oie_settings_api_validates_fields_and_rejects_atomically",
        "test_oie_settings_api_preserves_replaces_and_never_exposes_password",
        "test_oie_result_api_keeps_unknown_patient_unmatched",
        "test_oie_result_api_rejects_unsupported_message_with_failure_ack",
        "test_oie_result_listener_status_defaults_to_port_6665",
        "test_oie_result_listener_start_reports_bind_failure",
        "test_oie_send_order_records_ack_acceptance",
        "test_oie_send_order_uses_configured_default_endpoint",
        "test_oie_send_order_records_transport_error",
    ),
)
del _ApiCaseLibrary
