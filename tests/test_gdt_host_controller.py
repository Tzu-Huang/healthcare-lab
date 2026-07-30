from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


def unused_loopback_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


@unittest.skipUnless(POWERSHELL, "PowerShell is required for controller tests")
class GdtHostControllerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.deploy = self.root / "deploy"
        self.deploy.mkdir()
        for name in (
            "gdt-host-controller.ps1",
            "gdt-host-path.ps1",
            "docker-compose.yml",
        ):
            shutil.copy2(ROOT / "deploy" / name, self.deploy / name)
        self.controller_port = unused_loopback_port()
        self.app_port = unused_loopback_port()
        self.origin = f"http://127.0.0.1:{self.app_port}"
        self.base_url = f"http://127.0.0.1:{self.controller_port}"
        controller_env = os.environ.copy()
        controller_env.pop("GDT_BRIDGE_HOST_PATH", None)
        self.process = subprocess.Popen(
            [
                POWERSHELL, "-NoProfile", "-NonInteractive", "-File",
                str(self.deploy / "gdt-host-controller.ps1"),
                "-Mode", "serve", "-RepoDir", str(self.root),
                "-Port", str(self.controller_port),
                "-LabAppPort", str(self.app_port),
            ],
            cwd=self.root,
            env=controller_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self.addCleanup(self.stop_controller)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                self.request("/v1/status", origin=self.origin)
                break
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)
        else:
            self.fail("controller did not start")

    def stop_controller(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

    def request(self, path, *, origin=None, method="GET", body=None, token=None):
        headers = {}
        if origin is not None:
            headers["Origin"] = origin
        if token is not None:
            headers["X-Healthcare-Lab-Controller"] = token
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        request = urllib.request.Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())

    def test_status_exposes_only_bounded_deployment_metadata(self):
        status, body = self.request("/v1/status", origin=self.origin)
        self.assertEqual(200, status)
        self.assertEqual("/data/gdt-bridge", body["applicationPath"])
        self.assertEqual("default", body["source"])
        self.assertEqual("/data/gdt-bridge/inbox", body["derived"]["inbox"])
        self.assertNotIn("token", body)

    def test_missing_or_untrusted_origin_is_rejected(self):
        for origin in (None, "null", "https://example.invalid"):
            with self.subTest(origin=origin):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self.request("/v1/status", origin=origin)
                self.assertEqual(403, caught.exception.code)

    def test_apply_requires_installation_token(self):
        target = str(self.root / "exchange" / "clinic")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request(
                "/v1/apply", origin=self.origin, method="POST",
                body={"hostPath": target},
            )
        self.assertEqual(403, caught.exception.code)
        self.assertFalse((self.root / "exchange").exists())

    def test_apply_rejects_extra_fields_and_unsafe_paths_without_mutation(self):
        _, session = self.request("/v1/session", origin=self.origin)
        token = session["token"]
        cases = (
            {"hostPath": str(self.root / "safe"), "service": "oie"},
            {"hostPath": "relative/path"},
            {"hostPath": str(self.root)},
        )
        for body in cases:
            with self.subTest(body=body):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self.request(
                        "/v1/apply", origin=self.origin, method="POST",
                        body=body, token=token,
                    )
                self.assertEqual(400, caught.exception.code)
        self.assertFalse((self.root / "safe").exists())
        self.assertFalse((self.root / "relative").exists())

    def test_controller_records_installation_scoped_process_identity(self):
        identity_path = self.root / "instance" / "deployment" / "gdt-controller.pid"
        identity = json.loads(identity_path.read_text(encoding="utf-8"))

        self.assertEqual(self.process.pid, identity["pid"])
        self.assertEqual(str(self.deploy / "gdt-host-controller.ps1"), identity["scriptPath"])
        self.assertEqual(str(self.root), identity["repoDir"])

    def test_second_controller_cannot_delete_running_controller_identity(self):
        identity_path = self.root / "instance" / "deployment" / "gdt-controller.pid"
        original_identity = json.loads(identity_path.read_text(encoding="utf-8"))
        duplicate = subprocess.run(
            [
                POWERSHELL, "-NoProfile", "-NonInteractive", "-File",
                str(self.deploy / "gdt-host-controller.ps1"),
                "-Mode", "serve", "-RepoDir", str(self.root),
                "-Port", str(self.controller_port),
                "-LabAppPort", str(self.app_port),
            ],
            cwd=self.root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )

        self.assertNotEqual(0, duplicate.returncode)
        self.assertTrue(identity_path.is_file())
        current_identity = json.loads(identity_path.read_text(encoding="utf-8"))
        self.assertEqual(original_identity, current_identity)
        status, _ = self.request("/v1/status", origin=self.origin)
        self.assertEqual(200, status)

    def test_locked_down_process_fallback_requires_matching_start_identity(self):
        source = (ROOT / "deploy" / "lab.ps1").read_text(encoding="utf-8")

        self.assertIn("$Identity.startedAt", source)
        self.assertIn("$Controller.StartTime.ToUniversalTime()", source)
        self.assertIn("$StartIdentityMatches", source)
        self.assertIn("-and $StartIdentityMatches", source)

    def test_controller_normalizes_docker_desktop_mount_sources(self):
        source = (self.deploy / "gdt-host-controller.ps1").read_text(encoding="utf-8")
        self.assertIn('"/run/desktop/mnt/host/"', source)
        self.assertIn('"/host_mnt/"', source)
        self.assertIn("Convert-DockerMountSourceToHostPath", source)

    def test_worker_contract_verifies_state_mount_and_role_diagnostics(self):
        source = (self.deploy / "gdt-host-controller.ps1").read_text(encoding="utf-8")

        self.assertIn("$Container.State.Running", source)
        self.assertIn('$_.Destination -eq "/data/gdt-bridge"', source)
        self.assertIn("/api/settings/gdt-bridge/diagnostics", source)
        self.assertIn("Confirm-LabAppDeployment -HostPath $HostPath", source)

    def test_failed_operation_contract_preserves_stage_and_remediation(self):
        source = (self.deploy / "gdt-host-controller.ps1").read_text(encoding="utf-8")

        self.assertIn("failedStage = $FailedStage", source)
        self.assertIn("errorCode = $ErrorCode", source)
        self.assertIn("remediation = $Remediation", source)
        for stage in ("validating", "provisioning", "persisting", "recreating", "verifying"):
            self.assertIn(f'"{stage}"', source)


if __name__ == "__main__":
    unittest.main()
