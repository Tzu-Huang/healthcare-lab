from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class SharedComponentOwnershipTests(unittest.TestCase):
    def test_shared_components_have_documented_consumers_or_reserved_scope(self):
        map_source = (ROOT / "docs/frontend-module-map.md").read_text(encoding="utf-8")
        component_root = ROOT / "frontend/static/js/components"
        view_sources = {
            str(path.relative_to(ROOT / "frontend/static/js")).replace("\\", "/"):
            path.read_text(encoding="utf-8")
            for directory in ("views", "settings")
            for path in (ROOT / "frontend/static/js" / directory).glob("*.js")
        }

        for component in component_root.glob("*.js"):
            relative_import = f'../components/{component.name}'
            consumers = [name for name, source in view_sources.items() if relative_import in source]
            self.assertIn(f"`components/{component.name}`", map_source)
            if component.name == "settings-shell.js":
                self.assertEqual(["settings/oie.js"], consumers)
            else:
                self.assertGreaterEqual(len(consumers), 2, component.name)

    def test_shared_components_do_not_branch_on_feature_identity(self):
        feature_branch = re.compile(r"\b(dashboard|patient|order|fhir|medplum|dcm4chee|oie|gdt)-view\b")
        for component in (ROOT / "frontend/static/js/components").glob("*.js"):
            source = component.read_text(encoding="utf-8")
            self.assertIsNone(feature_branch.search(source), component.name)


if __name__ == "__main__":
    unittest.main()
