from ._owners import register_cases
from ._store_case_library import HealthcareLabStoreTests as _StoreCaseLibrary


class CompatibilityStoreTests(_StoreCaseLibrary):
    """Own retained DemoStore migration coverage for the ZAC-65 handoff."""


register_cases(
    CompatibilityStoreTests,
    ("test_oie_settings_profile_migration_preserves_existing_workflow_records",),
)
del _StoreCaseLibrary
