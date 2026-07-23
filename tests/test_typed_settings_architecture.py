from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TypedSettingsArchitectureTests(unittest.TestCase):
    def test_medplum_consumers_do_not_read_legacy_flask_configuration(self):
        violations = {}
        pattern = re.compile(
            r"""(?:app|current_app)\.config\[['"]MEDPLUM_(?:CLIENT_ID|CLIENT_SECRET|SCOPE|TOKEN_URL|AUTH_GRACE_SECONDS)['"]\]"""
        )
        for path in (ROOT / "backend").rglob("*.py"):
            matches = pattern.findall(path.read_text(encoding="utf-8"))
            if matches:
                violations[str(path.relative_to(ROOT))] = matches
        self.assertEqual({}, violations)

    def test_raw_typed_settings_sql_is_repository_owned(self):
        allowed = {
            Path("backend/repositories/integration_settings.py"),
            Path("backend/repositories/schema.py"),
        }
        violations = {}
        for path in (ROOT / "backend").rglob("*.py"):
            relative = path.relative_to(ROOT)
            if relative in allowed:
                continue
            text = path.read_text(encoding="utf-8")
            tables = re.findall(
                r"integration_settings_(?:profiles|secrets|mutation_audits)", text
            )
            if tables:
                violations[str(relative)] = tables
        self.assertEqual({}, violations)

    def test_settings_api_does_not_depend_on_flask_request_context_for_reads(self):
        service = (
            ROOT / "backend/services/integration_settings.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("current_app", service)
        self.assertNotIn("flask", service.lower())
        self.assertNotIn("os.environ", service)
