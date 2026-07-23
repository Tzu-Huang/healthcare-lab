from __future__ import annotations

import unittest

from backend.domain.gdt_bridge_profile import GDT_BRIDGE_DEFAULT_FIELDS
from backend.repositories.gdt_bridge_profile import GdtBridgeProfileRepository


class _TypedProfilesSpy:
    def __init__(self):
        self.calls = []

    def exists(self, profile_type):
        self.calls.append(("exists", profile_type))
        return False

    def create_if_missing(self, profile, **options):
        self.calls.append(("create", profile, options))
        return True

    def get_private(self, profile_type):
        return {"profileType": profile_type}

    def get_public(self, profile_type):
        return {"profileType": profile_type}

    def replace(self, profile, **options):
        self.calls.append(("replace", profile, options))
        return {"fields": profile.fields}


class GdtBridgeProfileRepositoryTests(unittest.TestCase):
    def test_adapter_uses_closed_profile_identity_and_value_free_bootstrap(self):
        typed_profiles = _TypedProfilesSpy()
        repository = GdtBridgeProfileRepository(typed_profiles)
        self.assertFalse(repository.exists())
        self.assertTrue(repository.bootstrap_if_missing({}))
        _, profile, options = typed_profiles.calls[-1]
        self.assertEqual("gdt-bridge", profile.profile_type)
        self.assertEqual({}, options["secrets"])
        self.assertEqual("legacy-environment", options["bootstrap_source"])

    def test_replace_validates_before_delegating_without_secret_mutations(self):
        typed_profiles = _TypedProfilesSpy()
        repository = GdtBridgeProfileRepository(typed_profiles)
        result = repository.replace(GDT_BRIDGE_DEFAULT_FIELDS, actor="operator")
        self.assertEqual("/data/gdt-bridge", result["fields"]["applicationPath"])
        _, profile, options = typed_profiles.calls[-1]
        self.assertEqual("local-gdt-bridge", profile.profile_name)
        self.assertEqual({}, options["secret_mutations"])
        self.assertEqual("operator", options["actor"])


if __name__ == "__main__":
    unittest.main()
