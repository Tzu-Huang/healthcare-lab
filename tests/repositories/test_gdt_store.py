from ._owners import register_cases
from ._store_case_library import HealthcareLabStoreTests as _StoreCaseLibrary


class GdtStoreTests(_StoreCaseLibrary):
    """Own GDT order, result, and workflow persistence assertions."""


register_cases(
    GdtStoreTests,
    (
        "test_gdt_order_creation_persists_fixed_ekg01_order",
        "test_gdt_patient_number_override_is_snapshotted",
        "test_gdt_result_import_persists_canonical_message_attachments_and_events",
        "test_gdt_unmatched_result_is_persisted",
        "test_gdt_result_without_order_identifier_does_not_guess_latest_patient_order",
        "test_gdt_order_events_do_not_include_other_order_lifecycle_events",
        "test_gdt_order_creation_rejects_non_mvp_8402_codes",
    ),
)
del _StoreCaseLibrary
