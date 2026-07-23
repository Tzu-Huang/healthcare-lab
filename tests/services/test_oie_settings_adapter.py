from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.application_composition import assemble_application_dependencies


class OieSettingsAdapterTests(unittest.TestCase):
    def test_shared_update_delegates_without_changing_mapping_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            dependencies = assemble_application_dependencies(
                Path(directory) / "settings.db"
            )
            shared = dependencies.integration_settings_service
            before = shared.get_public("oie")
            fields = before["fields"]
            original_mappings = fields["managedChannels"]
            fields["managementApi"]["username"] = "adapter-user"
            updated = shared.replace("oie", fields)
            self.assertEqual(
                "adapter-user", updated["fields"]["managementApi"]["username"]
            )
            self.assertEqual(
                original_mappings, updated["fields"]["managedChannels"]
            )
            shared.replace(
                "oie",
                updated["fields"],
                secret_replacements={
                    "managementApi.password": "adapter-secret-canary"
                },
            )
            self.assertNotIn("adapter-secret-canary", str(shared.get_public("oie")))

    def test_blank_password_replacement_preserves_specialized_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            dependencies = assemble_application_dependencies(
                Path(directory) / "settings.db"
            )
            shared = dependencies.integration_settings_service
            before = shared.get_effective("oie")["managementApi"]["password"]
            shared.replace(
                "oie",
                shared.get_public("oie")["fields"],
                secret_replacements={"managementApi.password": ""},
            )
            self.assertEqual(
                before, shared.get_effective("oie")["managementApi"]["password"]
            )
