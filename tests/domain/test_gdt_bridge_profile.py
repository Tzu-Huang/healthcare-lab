from __future__ import annotations

import unittest

from backend.domain.gdt_bridge_profile import (
    GDT_BRIDGE_APPLICATION_PATH,
    GDT_BRIDGE_DEFAULT_FIELDS,
    gdt_bridge_bootstrap_candidate,
    validate_gdt_bridge_profile,
)
from backend.domain.integration_settings import TypedSettingsValidationError


class GdtBridgeProfileTests(unittest.TestCase):
    def test_safe_defaults_are_canonical(self):
        profile = validate_gdt_bridge_profile(GDT_BRIDGE_DEFAULT_FIELDS)
        self.assertEqual("gdt-bridge", profile.profile_type)
        self.assertEqual(GDT_BRIDGE_APPLICATION_PATH, profile.fields["applicationPath"])
        self.assertEqual(2.0, profile.fields["pollSeconds"])

    def test_legacy_bootstrap_maps_all_runtime_fields(self):
        profile = gdt_bridge_bootstrap_candidate(
            {
                "GDT_BRIDGE_ENABLED": False,
                "GDT_BRIDGE_PATH": r"C:\bridge",
                "GDT_BRIDGE_RECEIVER_ID": "RECV_1",
                "GDT_BRIDGE_SENDER_ID": "SEND-1",
                "GDT_BRIDGE_FILENAME_PROFILE": "gdt35",
                "GDT_BRIDGE_IMPORT_SUCCESS_MODE": "delete",
                "GDT_BRIDGE_WATCH_POLL_SECONDS": 4,
                "GDT_BRIDGE_STABLE_SECONDS": 2,
            }
        )
        self.assertEqual("C:/bridge", profile.fields["applicationPath"])
        self.assertEqual(("RECV_1", "SEND-1"), (
            profile.fields["receiverId"], profile.fields["senderId"]
        ))
        self.assertFalse(profile.fields["enabled"])

    def test_invalid_complete_mutation_returns_stable_value_free_issues(self):
        fields = dict(GDT_BRIDGE_DEFAULT_FIELDS)
        fields.update(
            applicationPath="../patient-name",
            filenameProfile="gdt35",
            receiverId="",
            senderId="contains space",
            pollSeconds=0,
            stableSeconds=True,
            extra="secret value",
        )
        with self.assertRaises(TypedSettingsValidationError) as captured:
            validate_gdt_bridge_profile(fields)
        projection = captured.exception.as_dict()
        self.assertEqual("settings_validation_failed", projection["code"])
        issue_keys = {(item["field"], item["code"]) for item in projection["fields"]}
        self.assertIn(("extra", "unknown_field"), issue_keys)
        self.assertIn(("applicationPath", "invalid_absolute_path"), issue_keys)
        self.assertIn(("receiverId", "required_for_filename_profile"), issue_keys)
        self.assertIn(("pollSeconds", "invalid_bounded_number"), issue_keys)
        self.assertNotIn("patient-name", str(projection))
        self.assertNotIn("secret value", str(projection))


if __name__ == "__main__":
    unittest.main()
