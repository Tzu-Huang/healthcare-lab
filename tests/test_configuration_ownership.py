from __future__ import annotations

import re
import unittest
from pathlib import Path

from backend.configuration_ownership import (
    CONFIGURATION_OWNERSHIP,
    OWNERSHIP_CATEGORIES,
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
