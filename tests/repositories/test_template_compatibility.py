from ._owners import register_cases
from ._store_case_library import HealthcareLabStoreTests as _StoreCaseLibrary


class TemplateOwnershipTests(_StoreCaseLibrary):
    """Own the retained application-template boundary characterization."""


register_cases(
    TemplateOwnershipTests,
    ("test_healthcare_lab_template_excludes_ap_simulator_views",),
)
del _StoreCaseLibrary
