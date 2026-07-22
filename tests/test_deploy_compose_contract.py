from pathlib import Path
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
        self.assertIn("HLAB_RESULT_LISTENER_PORT=6665", self.example)
        self.assertIn("aliases never control an OIE host-published port", self.example)

    def test_internal_and_published_defaults_are_documented_separately(self):
        for setting in (
            "HLAB_RESULT_LISTENER_PORT=6665",
            "OIE_AP_RESULT_INGRESS_HOST_PORT=6661",
            "OIE_ORDER_INGRESS_HOST_PORT=6600",
        ):
            self.assertIn(setting, self.example)

    def test_lab_app_uses_published_image_without_source_mount_or_startup_install(self):
        self.assertIn(
            "${LAB_APP_IMAGE:-ghcr.io/tzu-huang/healthcare-lab:1.0.0}",
            self.compose,
        )
        self.assertIn("LAB_APP_IMAGE=ghcr.io/tzu-huang/healthcare-lab:1.0.0", self.example)
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


if __name__ == "__main__":
    unittest.main()
