import unittest

from ._case_support import *

class TemplateOwnershipTests(StoreCaseSupport):
    """Focused assertion owner for TemplateOwnershipTests."""

    def test_healthcare_lab_template_excludes_ap_simulator_views(self):
        template_root = Path(__file__).parents[2] / "frontend" / "templates"
        template = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                template_root / "shell" / "sidebar.html",
                template_root / "views" / "dashboard.html",
            )
        )

        self.assertIn('id="lab-console-view"', template)
        self.assertIn("Server Health Dashboard", template)
        self.assertNotIn('data-category-target="gdt-hospital-view"', template)
        self.assertNotIn('id="gdt-ap-view"', template)
        self.assertNotIn("GDT AP Simulator", template)
        self.assertNotIn('id="ap-gdt-order-list"', template)

if __name__ == "__main__":
    unittest.main()
