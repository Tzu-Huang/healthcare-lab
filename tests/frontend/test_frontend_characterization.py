from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "frontend" / "static" / "js" / "views" / "application.js"
BOOTSTRAP = ROOT / "frontend" / "static" / "js" / "app.js"
STYLE_LOADER = ROOT / "frontend" / "static" / "styles.css"
STYLE_OWNERS = (
    ROOT / "frontend" / "static" / "css" / "base.css",
    ROOT / "frontend" / "static" / "css" / "layout.css",
    ROOT / "frontend" / "static" / "css" / "components.css",
    ROOT / "frontend" / "static" / "css" / "views" / "application.css",
)
TEMPLATE_ROOT = ROOT / "frontend" / "templates"
INDEX_TEMPLATE = TEMPLATE_ROOT / "index.html"

FEATURES = {
    "dashboard": "lab-console-view",
    "patient": "patient-view",
    "fhir": "medplum-view",
    "order": "order-view",
    "dcm4chee": "dcm4chee-view",
    "oie": "oie-view",
    "gdt": "gdt-view",
}


class FrontendCharacterizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
        cls.style_loader = STYLE_LOADER.read_text(encoding="utf-8")
        cls.styles = "\n".join(path.read_text(encoding="utf-8") for path in STYLE_OWNERS)
        cls.template = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(TEMPLATE_ROOT.rglob("*.html"))
        )

    def test_every_current_feature_has_navigation_and_a_view_root(self):
        for feature, view_id in FEATURES.items():
            with self.subTest(feature=feature):
                self.assertIn(f'id="{view_id}"', self.template)
                self.assertIn(f'data-nav-target="{view_id}"', self.template)
                self.assertIn(f'"{view_id}"', self.script)

    def test_application_shell_delegates_sidebar_and_workspaces_to_owned_partials(self):
        index = INDEX_TEMPLATE.read_text(encoding="utf-8")
        expected_partials = {
            "shell/sidebar.html",
            "views/dashboard.html",
            "views/patient.html",
            "views/fhir.html",
            "views/order.html",
            "views/dcm4chee.html",
            "views/oie.html",
            "views/gdt.html",
            "views/settings.html",
        }
        for partial in expected_partials:
            with self.subTest(partial=partial):
                self.assertIn(f"{{% include '{partial}' %}}", index)
                self.assertTrue((TEMPLATE_ROOT / partial).is_file())
        for view_id in FEATURES.values():
            with self.subTest(view=view_id):
                self.assertNotIn(f'id="{view_id}"', index)
        self.assertNotIn('class="app-sidebar"', index)

    def test_shared_request_contract_covers_transport_and_business_failures(self):
        client = (ROOT / "frontend" / "static" / "js" / "api" / "client.js").read_text(encoding="utf-8")
        self.assertIn("export async function requestJson(", client)
        self.assertIn("export async function requestJsonAllowBusinessFailure(", client)
        self.assertIn("!response.ok || payload.success === false", client)
        self.assertIn("if (!response.ok)", client)

    def test_navigation_characterizes_feature_activation(self):
        activation_calls = {
            "lab-console-view": "refreshDashboard",
            "patient-view": "refreshPatients",
            "medplum-view": "refreshMedplumInventory",
            "order-view": "refreshOrderWorkspace",
            "dcm4chee-view": "refreshDcm4cheeConsole",
            "oie-view": "refreshOieInventory",
            "gdt-view": "refreshGdtConsole",
        }
        for view_id, call in activation_calls.items():
            with self.subTest(view=view_id):
                self.assertRegex(
                    self.script,
                    rf'(?s)registerViewActivation\("{re.escape(view_id)}".*?{re.escape(call)}',
                )

    def test_cross_view_gdt_order_flow_is_characterized(self):
        self.assertIn("function openGdtOrderFlow()", self.script)
        self.assertIn('setActiveView("order-view")', self.script)
        self.assertIn('selector.value = "gdt"', self.script)

    def test_startup_registers_one_dom_content_loaded_boundary(self):
        self.assertEqual(
            1,
            self.bootstrap.count('document.addEventListener("DOMContentLoaded", initializeApplication)'),
        )

    def test_responsive_layout_contract_is_present(self):
        self.assertIn("@media (max-width:", self.styles)
        for selector in (".app-shell", ".app-sidebar", ".patient-grid"):
            with self.subTest(selector=selector):
                self.assertIn(selector, self.styles)

    def test_global_stylesheet_is_an_ordered_thin_loader(self):
        self.assertEqual(
            [
                '@import url("./css/base.css");',
                '@import url("./css/layout.css");',
                '@import url("./css/components.css");',
                '@import url("./css/views/application.css");',
                '@import url("./css/views/settings.css");',
            ],
            self.style_loader.splitlines(),
        )

    def test_stylesheet_layers_do_not_split_selector_rules(self):
        owners = [path.read_text(encoding="utf-8") for path in STYLE_OWNERS]
        for path, source in zip(STYLE_OWNERS, owners, strict=True):
            with self.subTest(path=path.name):
                self.assertTrue(source.rstrip().endswith("}"))
        self.assertTrue(owners[2].lstrip().startswith("button,\n.button {"))

    def test_feature_selector_families_are_scoped_to_their_workspace(self):
        scoped_families = {
            "#lab-console-view": r"\.(?:lab-console(?![\s,{:.#\[]|$)|lab-summary|lab-server|dashboard-|resource-usage|resource-item)",
            "#medplum-view": r"\.medplum-(?!workspace(?:[\s,{:.#\[]|$))",
            "#order-view": r"\.order-(?!workspace(?:[\s,{:.#\[]|$))",
            "#dcm4chee-view": r"\.dcm4chee-(?!workspace(?:[\s,{:.#\[]|$))",
            "#oie-view": r"\.oie-(?!workspace(?:[\s,{:.#\[]|$))",
            "#gdt-view": r"\.gdt-(?!console(?:[\s,{:.#\[]|$))",
        }
        for line in self.styles.splitlines():
            selector = line.strip()
            if not selector.startswith(('.', '#')):
                continue
            for workspace, family in scoped_families.items():
                if re.match(family, selector):
                    with self.subTest(selector=selector, workspace=workspace):
                        self.fail(f"feature-only selector is not scoped beneath {workspace}: {selector}")


if __name__ == "__main__":
    unittest.main()
