from ._owners import register_cases
from ._api_case_library import HealthcareLabApiTests as _ApiCaseLibrary


class ApplicationShellTests(_ApiCaseLibrary):
    """Own Flask shell, route registration, and static rendering contracts."""


register_cases(
    ApplicationShellTests,
    (
        "test_index_serves_dashboard_only_ui",
        "test_native_module_assets_use_conditional_revalidation",
        "test_frontend_exposes_dashboard_children_and_gdt_workspace_order_action",
        "test_sidebar_views_hide_inactive_pages",
        "test_only_healthcare_lab_routes_are_registered",
    ),
)
del _ApiCaseLibrary
