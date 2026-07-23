import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.domain.errors import SimulatorValidationError
from backend.services.gdt_bridge_diagnostics import (
    DOCUMENTED_GDT_DIRECTORY_ROLES,
    confined_gdt_bridge_dirs,
    diagnose_gdt_bridge_dirs,
    probe_gdt_bridge_write_delete,
    provision_gdt_bridge_dirs,
)


class GdtBridgeHealthTest(unittest.TestCase):
    def test_provisioning_creates_only_documented_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "bridge"

            result = provision_gdt_bridge_dirs(root)

            self.assertEqual(list(DOCUMENTED_GDT_DIRECTORY_ROLES), result["created"])
            self.assertEqual([], result["existing"])
            self.assertEqual(
                set(DOCUMENTED_GDT_DIRECTORY_ROLES),
                {item.name for item in root.iterdir()},
            )
            second = provision_gdt_bridge_dirs(root)
            self.assertEqual([], second["created"])
            self.assertEqual(list(DOCUMENTED_GDT_DIRECTORY_ROLES), second["existing"])

    def test_existing_symlink_escape_is_rejected_without_mutating_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "bridge"
            outside = parent / "outside"
            root.mkdir()
            outside.mkdir()
            try:
                (root / "inbox").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("Directory symlinks are unavailable on this platform.")

            with self.assertRaises(SimulatorValidationError):
                confined_gdt_bridge_dirs(root)
            self.assertEqual([], list(outside.iterdir()))

    def test_missing_paths_are_bounded_and_do_not_create_anything(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "patient-canary" / "bridge"

            result = diagnose_gdt_bridge_dirs(root)

            self.assertEqual("degraded", result["state"])
            self.assertFalse(root.exists())
            rendered = str(result)
            self.assertNotIn("patient-canary", rendered)
            self.assertNotIn(str(root), rendered)

    def test_empty_folders_are_healthy_without_enumerating_contents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "bridge"
            provision_gdt_bridge_dirs(root)

            result = diagnose_gdt_bridge_dirs(root)

            self.assertEqual("healthy", result["state"])
            self.assertTrue(all(check["state"] == "passed" for check in result["checks"]))

    def test_read_failure_has_value_free_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "phi-canary"
            provision_gdt_bridge_dirs(root)
            with patch("backend.services.gdt_bridge_diagnostics.os.access", return_value=False):
                result = diagnose_gdt_bridge_dirs(root)

            self.assertEqual("degraded", result["state"])
            self.assertTrue(all(check["code"] == "read-denied" for check in result["checks"]))
            self.assertNotIn("phi-canary", str(result))

    def test_write_probe_is_empty_and_is_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "bridge"
            provision_gdt_bridge_dirs(root)
            diagnostic = root / "diagnostic"

            result = probe_gdt_bridge_write_delete(root)

            self.assertEqual(
                {"role": "write-delete", "state": "passed", "code": "writable"},
                result,
            )
            self.assertEqual([], list(diagnostic.iterdir()))

    def test_write_and_delete_failures_use_distinct_bounded_codes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "bridge"
            provision_gdt_bridge_dirs(root)
            with patch("backend.services.gdt_bridge_diagnostics.os.open", side_effect=OSError):
                write_result = probe_gdt_bridge_write_delete(root)
            self.assertEqual("write-failed", write_result["code"])

            original_unlink = Path.unlink
            calls = 0

            def fail_first_unlink(path, *args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise OSError("phi-bearing-file-name.gdt")
                return original_unlink(path, *args, **kwargs)

            with patch.object(Path, "unlink", fail_first_unlink):
                delete_result = probe_gdt_bridge_write_delete(root)
            self.assertEqual("delete-failed", delete_result["code"])
            self.assertNotIn("phi-bearing-file-name.gdt", str(delete_result))
            self.assertEqual([], list((root / "diagnostic").iterdir()))


if __name__ == "__main__":
    unittest.main()
