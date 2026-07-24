from __future__ import annotations

import re
import unittest
from pathlib import Path

from backend.configuration_ownership import (
    CONFIGURATION_OWNERSHIP,
    DEPLOYMENT_ONLY,
    OWNERSHIP_CATEGORIES,
    RUNTIME_PERSISTED,
    ownership_for,
)


ROOT = Path(__file__).resolve().parents[1]


def declared_deployment_keys() -> set[str]:
    keys: set[str] = set()
    for relative in (".env.example", "deploy/docker-compose.yml"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        keys.update(re.findall(r"(?m)^#?\s*([A-Z][A-Z0-9_]+)=", text))
        keys.update(re.findall(r"\$\{([A-Z][A-Z0-9_]+)", text))
    return keys


class ConfigurationOwnershipContractTests(unittest.TestCase):
    def test_every_declared_environment_and_compose_key_has_exactly_one_owner(self):
        self.assertEqual(declared_deployment_keys(), set(CONFIGURATION_OWNERSHIP))
        self.assertTrue(
            all(item.category in OWNERSHIP_CATEGORIES for item in CONFIGURATION_OWNERSHIP.values())
        )

    def test_each_entry_has_restart_and_bootstrap_contract(self):
        for key, item in CONFIGURATION_OWNERSHIP.items():
            with self.subTest(key=key):
                self.assertTrue(item.owner)
                self.assertTrue(item.activation)
                self.assertTrue(item.bootstrap)

    def test_unknown_keys_fail_closed(self):
        with self.assertRaisesRegex(KeyError, "Unsupported configuration key"):
            ownership_for("ARBITRARY_SETTINGS_KEY")

    def test_published_matrix_references_every_registered_key(self):
        documentation = (ROOT / "docs/configuration-ownership.md").read_text(encoding="utf-8")
        missing = [key for key in CONFIGURATION_OWNERSHIP if f"`{key}`" not in documentation]
        self.assertEqual([], missing)

    def test_deployment_only_values_are_never_typed_profile_bootstrap_inputs(self):
        for key, item in CONFIGURATION_OWNERSHIP.items():
            if item.category == DEPLOYMENT_ONLY:
                with self.subTest(key=key):
                    self.assertEqual("never", item.bootstrap)
                    self.assertEqual("Docker Compose", item.owner)

        typed_bootstrap_sources = "\n".join(
            (ROOT / relative).read_text(encoding="utf-8")
            for relative in (
                "backend/domain/integration_settings.py",
                "backend/domain/gdt_bridge_profile.py",
            )
        )
        leaked = [
            key
            for key, item in CONFIGURATION_OWNERSHIP.items()
            if item.category == DEPLOYMENT_ONLY and f'"{key}"' in typed_bootstrap_sources
        ]
        self.assertEqual([], leaked)

    def test_runtime_consumers_do_not_read_migrated_environment_directly(self):
        runtime_keys = {
            key
            for key, item in CONFIGURATION_OWNERSHIP.items()
            if item.category == RUNTIME_PERSISTED
        }
        violations: list[str] = []
        for path in (ROOT / "backend").rglob("*.py"):
            relative = path.relative_to(ROOT).as_posix()
            if relative in {
                "backend/config.py",
                "backend/configuration_ownership.py",
                "backend/domain/integration_settings.py",
                "backend/domain/gdt_bridge_profile.py",
            }:
                continue
            source = path.read_text(encoding="utf-8")
            for key in runtime_keys:
                direct_reads = (
                    rf"os\.environ(?:\.get)?\(\s*['\"]{re.escape(key)}['\"]",
                    rf"os\.getenv\(\s*['\"]{re.escape(key)}['\"]",
                )
                if any(re.search(pattern, source) for pattern in direct_reads):
                    violations.append(f"{relative}: {key}")
        self.assertEqual([], violations)
