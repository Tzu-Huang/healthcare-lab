from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class EcgViewerExecutableBehaviorTests(unittest.TestCase):
    def test_node_behavior_suite(self):
        result = subprocess.run(
            [
                "node",
                "--experimental-vm-modules",
                "--test",
                str(ROOT / "tests/frontend/ecg_viewer_behavior.mjs"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        self.assertEqual(
            0,
            result.returncode,
            msg=f"{result.stdout}\n{result.stderr}",
        )
        self.assertIn("pass 4", result.stdout)
        self.assertIn("fail 0", result.stdout)


if __name__ == "__main__":
    unittest.main()
