from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SettingsWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.template = (ROOT / "frontend/templates/views/settings.html").read_text(encoding="utf-8")
        self.view = (ROOT / "frontend/static/js/views/settings.js").read_text(encoding="utf-8")
        self.registry = (ROOT / "frontend/static/js/settings/registry.js").read_text(encoding="utf-8")
        self.workspace = (ROOT / "frontend/static/js/settings/workspace.js").read_text(encoding="utf-8")
        self.oie = (ROOT / "frontend/static/js/settings/oie.js").read_text(encoding="utf-8")
        self.readiness = (ROOT / "frontend/static/js/api/readiness.js").read_text(encoding="utf-8")
        self.css = (ROOT / "frontend/static/css/views/settings.css").read_text(encoding="utf-8")

    def test_registry_has_exact_accessible_sections_without_openemr(self):
        labels = ("Overview", "Medplum", "OIE", "GDT Bridge", "dcm4chee", "AP / External Devices", "Deployment & Diagnostics")
        for label in labels:
            self.assertIn(f'label: "{label}"', self.registry)
        combined = (self.template + self.registry + self.workspace).lower()
        self.assertNotIn("openemr", combined)
        self.assertIn('role="tablist"', self.template)
        self.assertIn('role="tabpanel"', self.template)
        self.assertIn('["ArrowLeft", "ArrowRight", "Home", "End"]', self.workspace)

    def test_readiness_guidance_is_derived_and_optional_sections_do_not_block(self):
        self.assertNotIn("cursor", self.workspace.lower())
        self.assertIn("section.required", self.workspace)
        for section in ("gdt-bridge", "dcm4chee", "external-devices"):
            self.assertRegex(self.registry, rf'id: "{section}", label: .* required: false')
        self.assertIn("Continue setup with", self.workspace)
        self.assertIn("Optional integrations may remain disabled", self.workspace)

    def test_overview_and_bounded_diagnostics_are_modular(self):
        self.assertIn('"/api/settings/readiness"', self.readiness)
        self.assertIn('method: "POST"', self.readiness)
        for element_id in ("settings-overview-cards", "settings-run-all-checks", "settings-all-checks-results"):
            self.assertIn(f'id="{element_id}"', self.template)
        self.assertIn("unavailable providers do not hide successful results", self.workspace)
        self.assertIn("initializeSettingsWorkspace(root)", self.view)
        self.assertIn("refreshSettingsWorkspace(root)", self.view)
        self.assertIn("SETTINGS_MODULES.forEach", self.view)
        self.assertIn("module.initialize(root)", self.view)
        self.assertIn("module.refresh(root)", self.view)
        self.assertNotIn("managementPayload", self.view)
        self.assertIn("managementPayload", self.oie)

    def test_registry_contract_owns_integration_lifecycle_and_layers(self):
        self.assertIn("export function defineSettingsModule", self.registry)
        self.assertIn('id: "oie", label: "OIE", required: true', self.registry)
        self.assertIn("initialize: initializeOieSettingsSection", self.registry)
        self.assertIn("refresh: refreshOieSettings", self.registry)
        for owner in ("view", "api", "state", "style"):
            self.assertIn(f"{owner}:", self.registry)
        self.assertIn("export function moduleById", self.registry)
        self.assertNotIn("initializeOieSettingsSection(root)", self.view)

    def test_activation_advanced_and_responsive_contracts(self):
        for label in ("Applies immediately", "Restart required", "Apply / Redeploy required", "Container recreation required"):
            self.assertIn(label, self.workspace)
        self.assertGreaterEqual(self.template.count("<summary>Advanced</summary>"), 5)
        self.assertIn("@media", self.css)
        self.assertIn(".settings-tabs", self.css)
        self.assertIn("overflow-x: auto", self.css)


if __name__ == "__main__":
    unittest.main()
