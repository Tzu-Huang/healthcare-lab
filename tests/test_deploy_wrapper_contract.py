from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


@unittest.skipUnless(POWERSHELL, "PowerShell is required for wrapper contract tests")
class DeployWrapperContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.deploy = self.root / "deploy"
        self.deploy.mkdir()
        shutil.copy2(ROOT / "deploy" / "lab.ps1", self.deploy / "lab.ps1")
        shutil.copy2(
            ROOT / "deploy" / "docker-compose.yml",
            self.deploy / "docker-compose.yml",
        )
        self.bin = self.root / "fake-bin"
        self.bin.mkdir()
        self.invocations = self.root / "docker-arguments.txt"
        self.docker_environment = self.root / "docker-environment.txt"
        (self.bin / "docker.cmd").write_text(
            "@echo off\r\n"
            "echo %*>>\"%FAKE_DOCKER_INVOCATIONS%\"\r\n"
            "echo %GDT_BRIDGE_HOST_PATH%>>\"%FAKE_DOCKER_ENVIRONMENT%\"\r\n"
            "exit /b 0\r\n",
            encoding="utf-8",
        )

    def run_wrapper(self, *arguments: str, extra_env=None):
        env = os.environ.copy()
        env["PATH"] = f"{self.bin}{os.pathsep}{env['PATH']}"
        env["FAKE_DOCKER_INVOCATIONS"] = str(self.invocations)
        env["FAKE_DOCKER_ENVIRONMENT"] = str(self.docker_environment)
        env.pop("GDT_BRIDGE_HOST_PATH", None)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [
                POWERSHELL,
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(self.deploy / "lab.ps1"),
                *arguments,
            ],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def recorded_arguments(self):
        return self.invocations.read_text(encoding="utf-8").splitlines()

    def recorded_gdt_paths(self):
        return self.docker_environment.read_text(encoding="utf-8").splitlines()

    def test_supported_actions_have_deterministic_absolute_compose_arguments(self):
        cases = {
            ("status", "all"): "compose -f",
            ("inspect", "lab-app"): "compose -f",
            ("start", "lab-app"): "compose -f",
            ("stop", "oie"): "compose -f",
            ("restart", "lab-app"): "compose -f",
            ("smoke", "all"): "compose -f",
            ("logs", "lab-app"): "compose -f",
        }
        for arguments, prefix in cases.items():
            with self.subTest(arguments=arguments):
                if self.invocations.exists():
                    self.invocations.unlink()
                result = self.run_wrapper(*arguments)
                self.assertEqual(0, result.returncode, result.stderr)
                calls = self.recorded_arguments()
                self.assertTrue(calls)
                self.assertTrue(calls[0].startswith(prefix), calls[0])
                self.assertIn(str(self.deploy / "docker-compose.yml"), calls[0])
                self.assertNotIn("--env-file", calls[0])

    def test_existing_env_file_is_passed_without_printing_its_values(self):
        canary = "wrapper-secret-canary-ZAC-77"
        (self.root / ".env").write_text(
            f"MEDPLUM_POSTGRES_PASSWORD={canary}\n", encoding="utf-8"
        )

        result = self.run_wrapper("status")

        self.assertEqual(0, result.returncode, result.stderr)
        call = self.recorded_arguments()[0]
        self.assertIn(f"--env-file {self.root / '.env'}", call)
        self.assertNotIn(canary, result.stdout + result.stderr + call)

    def test_start_provisions_default_gdt_directory_only(self):
        result = self.run_wrapper("start", "lab-app")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.root / "instance" / "gdt-bridge").is_dir())
        self.assertIn("up -d lab-app", self.recorded_arguments()[0])

    def test_whole_stack_recreate_preserves_existing_gdt_content(self):
        bridge = self.root / "instance" / "gdt-bridge"
        bridge.mkdir(parents=True)
        marker = bridge / "retained.gdt"
        marker.write_text("persistent-payload", encoding="utf-8")

        result = self.run_wrapper("restart", "all")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            "persistent-payload",
            marker.read_text(encoding="utf-8"),
        )
        self.assertIn("up -d --force-recreate", self.recorded_arguments()[0])

    def test_whole_stack_restart_provisions_but_service_restart_does_not(self):
        result = self.run_wrapper("restart", "lab-app")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse((self.root / "instance").exists())

        result = self.run_wrapper("restart", "all")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.root / "instance" / "gdt-bridge").is_dir())

    def test_advanced_relative_override_creates_only_the_exact_directory(self):
        (self.root / ".env").write_text(
            "GDT_BRIDGE_HOST_PATH=exchange/clinic-a\n", encoding="utf-8"
        )

        result = self.run_wrapper("start")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.root / "exchange" / "clinic-a").is_dir())
        self.assertFalse((self.root / "instance").exists())
        self.assertEqual(
            str((self.root / "exchange" / "clinic-a").resolve()),
            self.recorded_gdt_paths()[0],
        )

    def test_environment_override_takes_precedence_over_env_file(self):
        (self.root / ".env").write_text(
            "GDT_BRIDGE_HOST_PATH=exchange/from-file\n", encoding="utf-8"
        )

        result = self.run_wrapper(
            "start",
            extra_env={"GDT_BRIDGE_HOST_PATH": "exchange/from-process"},
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.root / "exchange" / "from-process").is_dir())
        self.assertFalse((self.root / "exchange" / "from-file").exists())

    def test_broad_override_is_rejected_without_invoking_docker(self):
        canary = "unsafe-value-must-not-be-printed"
        (self.root / ".env").write_text(
            f"GDT_BRIDGE_HOST_PATH={self.root}\n"
            f"MEDPLUM_POSTGRES_PASSWORD={canary}\n",
            encoding="utf-8",
        )

        result = self.run_wrapper("start")

        self.assertNotEqual(0, result.returncode)
        self.assertIn("dedicated directory", result.stderr)
        self.assertNotIn(canary, result.stdout + result.stderr)
        self.assertFalse(self.invocations.exists())

    def test_filesystem_root_override_is_rejected(self):
        filesystem_root = Path(self.root.anchor)
        (self.root / ".env").write_text(
            f"GDT_BRIDGE_HOST_PATH={filesystem_root}\n", encoding="utf-8"
        )

        result = self.run_wrapper("start")

        self.assertNotEqual(0, result.returncode)
        self.assertIn("dedicated directory", result.stderr)
        self.assertFalse(self.invocations.exists())

    def test_file_override_is_rejected_without_modifying_it(self):
        target = self.root / "not-a-directory"
        target.write_text("retain-me", encoding="utf-8")
        (self.root / ".env").write_text(
            f"GDT_BRIDGE_HOST_PATH={target}\n", encoding="utf-8"
        )

        result = self.run_wrapper("start")

        self.assertNotEqual(0, result.returncode)
        self.assertEqual("retain-me", target.read_text(encoding="utf-8"))
        self.assertFalse(self.invocations.exists())


if __name__ == "__main__":
    unittest.main()
