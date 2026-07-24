from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ComposePortContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compose = (ROOT / "deploy" / "docker-compose.yml").read_text(encoding="utf-8")
        cls.example = (ROOT / ".env.example").read_text(encoding="utf-8")

    def test_host_publications_have_endpoint_specific_names(self):
        self.assertIn("${OIE_AP_RESULT_INGRESS_HOST_PORT:-6661}:6661", self.compose)
        self.assertIn("${OIE_ORDER_INGRESS_HOST_PORT:-6600}:6600", self.compose)
        self.assertNotIn("${OIE_MLLP_RESULT_PORT:-6661}:6661", self.compose)
        self.assertNotIn("${OIE_MLLP_ORDER_PORT:-6600}:6600", self.compose)

    def test_hlab_listener_has_bounded_legacy_alias(self):
        self.assertIn(
            "${HLAB_RESULT_LISTENER_PORT:-${OIE_MLLP_RESULT_PORT:-6665}}",
            self.compose,
        )
        self.assertEqual(1, self.compose.count("${OIE_MLLP_RESULT_PORT"))
        self.assertNotIn("HLAB_RESULT_LISTENER_PORT=6665", self.example)
        self.assertIn("Deprecated OIE listener aliases", self.example)

    def test_internal_and_published_defaults_are_documented_separately(self):
        for setting in (
            "OIE_AP_RESULT_INGRESS_HOST_PORT=6661",
            "OIE_ORDER_INGRESS_HOST_PORT=6600",
        ):
            self.assertIn(setting, self.example)
        self.assertIn(
            "OIE_MLLP_RESULT_PORT: ${HLAB_RESULT_LISTENER_PORT:-",
            self.compose,
        )

    def test_dcm4chee_compose_defaults_do_not_use_lab_app_loopback(self):
        internal_settings = (
            "DCM4CHEE_DIMSE_HOST=dcm4chee",
            "DCM4CHEE_HL7_HOST=dcm4chee",
            "DCM4CHEE_DICOMWEB_BASE_URL=http://dcm4chee:8080/dcm4chee-arc/aets/WORKLIST/rs",
            "DCM4CHEE_QIDO_RS_URL=http://dcm4chee:8080/dcm4chee-arc/aets/DCM4CHEE/rs",
            "DCM4CHEE_WADO_RS_URL=http://dcm4chee:8080/dcm4chee-arc/aets/DCM4CHEE/rs",
            "DCM4CHEE_STOW_RS_URL=http://dcm4chee:8080/dcm4chee-arc/aets/DCM4CHEE/rs",
        )
        for setting in internal_settings:
            self.assertNotIn(setting, self.example)
        self.assertNotIn("DCM4CHEE_WEB_UI_URL=", self.example)
        self.assertNotIn("DCM4CHEE_DIMSE_HOST=127.0.0.1", self.example)
        self.assertNotIn("DCM4CHEE_HL7_HOST=127.0.0.1", self.example)
        self.assertNotIn(
            "DCM4CHEE_DICOMWEB_BASE_URL=http://127.0.0.1:8082",
            self.example,
        )

        for variable in (
            "DCM4CHEE_DIMSE_HOST",
            "DCM4CHEE_HL7_HOST",
            "DCM4CHEE_DICOMWEB_BASE_URL",
            "DCM4CHEE_QIDO_RS_URL",
            "DCM4CHEE_WADO_RS_URL",
            "DCM4CHEE_STOW_RS_URL",
        ):
            self.assertIn(f"{variable}: ${{{variable}:-", self.compose)

    def test_application_owned_settings_are_not_required_deployment_template_values(self):
        for setting in (
            "MEDPLUM_SCOPE=",
            "MEDPLUM_WEB_UI_URL=",
            "GDT_BRIDGE_FILENAME_PROFILE=",
            "DCM4CHEE_DIMSE_HOST=",
        ):
            self.assertNotIn(setting, self.example)
        self.assertIn("New installs should use Settings instead.", self.example)

    def test_lab_app_uses_published_image_without_source_mount_or_startup_install(self):
        self.assertIn(
            "${LAB_APP_IMAGE:-ghcr.io/tzu-huang/healthcare-lab:1.0.1}",
            self.compose,
        )
        self.assertIn("LAB_APP_IMAGE=ghcr.io/tzu-huang/healthcare-lab:1.0.1", self.example)
        self.assertNotIn("- ..:/workspace", self.compose)
        self.assertNotIn("pip install", self.compose)
        self.assertNotIn("python app.py", self.compose)
        self.assertNotIn("working_dir: /workspace", self.compose)

    def test_lab_app_preserves_runtime_mounts_and_network_contract(self):
        for contract in (
            "lab-app-instance:/app/instance",
            "/data/gdt-bridge",
            "/var/run/docker.sock:/var/run/docker.sock",
            '"${LAB_APP_PORT:-5000}:5000"',
            '"6665"',
        ):
            self.assertIn(contract, self.compose)

    def test_compose_does_not_require_or_inject_repository_env_file(self):
        self.assertNotIn("env_file:", self.compose)
        self.assertNotIn("../.env", self.compose)

    def test_compose_passes_only_explicit_legacy_bootstrap_allowlist(self):
        for setting in (
            "MEDPLUM_CLIENT_ID",
            "MEDPLUM_CLIENT_SECRET",
            "GDT_BRIDGE_RECEIVER_ID",
            "OPENEMR_DB_HOST",
            "DCM4CHEE_PASSWORD",
        ):
            self.assertIn(f"{setting}: ${{{setting}:-", self.compose)
        self.assertNotIn("env_file:", self.compose)

    def test_dcm4chee_internal_and_host_hl7_ports_have_distinct_owners(self):
        self.assertIn(
            "DCM4CHEE_HL7_PORT: ${DCM4CHEE_HL7_PORT:-2575}",
            self.compose,
        )
        self.assertIn(
            '"${DCM4CHEE_HL7_HOST_PORT:-2575}:2575"',
            self.compose,
        )

    def test_persistence_contract_survives_compatible_lab_app_replacement(self):
        self.assertIn("lab-app-instance:/app/instance", self.compose)
        self.assertIn(
            "${GDT_BRIDGE_HOST_PATH:-../instance/gdt-bridge}:/data/gdt-bridge",
            self.compose,
        )
        self.assertIn("lab-app-instance:", self.compose)
        self.assertNotIn("container_name:", self.compose)

    def test_release_defaults_do_not_use_unbounded_latest_images(self):
        self.assertNotIn(":latest", self.compose)
        for image in (
            "nextgenhealthcare/connect:4.5.2@sha256:",
            "postgres:16-alpine@sha256:",
            "redis:7-alpine@sha256:",
            "medplum/medplum-server@sha256:",
            "medplum/medplum-app@sha256:",
            "dcm4che/postgres-dcm4chee:16.13-35@sha256:",
            "dcm4che/slapd-dcm4chee:2.6.13-35.0@sha256:",
            "dcm4che/dcm4chee-arc-psql:5.35.0@sha256:",
        ):
            self.assertIn(image, self.compose)


@unittest.skipUnless(shutil.which("docker"), "Docker CLI is required")
class ComposeRenderContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.deploy = self.root / "deploy"
        self.deploy.mkdir()
        shutil.copy2(
            ROOT / "deploy" / "docker-compose.yml",
            self.deploy / "docker-compose.yml",
        )

    def render(self, env_file: Path | None = None):
        command = ["docker", "compose"]
        if env_file:
            command += ["--env-file", str(env_file)]
        command += ["-f", str(self.deploy / "docker-compose.yml"), "config"]
        env = os.environ.copy()
        for key in tuple(env):
            if key.startswith(
                (
                    "LAB_",
                    "OIE_",
                    "HLAB_",
                    "MEDPLUM_",
                    "DCM4CHEE_",
                    "GDT_",
                    "ECG_",
                )
            ):
                env.pop(key)
        return subprocess.run(
            command,
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_renders_with_deliberately_absent_root_env(self):
        self.assertFalse((self.root / ".env").exists())

        result = self.render()

        self.assertEqual(0, result.returncode, result.stderr)
        rendered = result.stdout
        for contract in (
            "ghcr.io/tzu-huang/healthcare-lab:1.0.1",
            "nextgenhealthcare/connect:4.5.2@sha256:",
            "published: \"5000\"",
            "published: \"6600\"",
            "source: lab-app-instance",
            "target: /app/instance",
            "target: /data/gdt-bridge",
            "name: interoperability-lab",
        ):
            self.assertIn(contract, rendered)
        self.assertNotIn("env_file:", rendered)

    def test_bounded_advanced_overrides_render_without_secret_output(self):
        canary = "compose-secret-canary-ZAC-77"
        override_path = self.root / "clinic-gdt"
        env_file = self.root / "advanced.env"
        env_file.write_text(
            "\n".join(
                (
                    "LAB_APP_IMAGE=registry.example/lab:2.0.0",
                    "LAB_APP_PORT=15000",
                    "OIE_HTTP_PORT=18080",
                    f"GDT_BRIDGE_HOST_PATH={override_path}",
                    "MEDPLUM_POSTGRES_USER=lab_operator",
                    f"MEDPLUM_POSTGRES_PASSWORD={canary}",
                    "DCM4CHEE_LDAP_ROOTPASS=hardened-local-secret",
                )
            )
            + "\n",
            encoding="utf-8",
        )

        result = self.render(env_file)

        self.assertEqual(0, result.returncode, result.stderr)
        rendered = result.stdout
        for contract in (
            "registry.example/lab:2.0.0",
            'published: "15000"',
            'published: "18080"',
            f"source: {override_path}",
            "POSTGRES_USER: lab_operator",
        ):
            self.assertIn(contract, rendered)
        # Compose config necessarily projects runtime credentials, so the
        # contract verifies stderr/diagnostics remain value-free and avoids
        # persisting the rendered output as test evidence.
        self.assertNotIn(canary, result.stderr)


if __name__ == "__main__":
    unittest.main()
