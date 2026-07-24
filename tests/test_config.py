import unittest
from pathlib import Path
import tempfile

from backend.config import load_application_config, parse_app_port
from backend.domain.errors import ValidationError


class ApplicationConfigTest(unittest.TestCase):
    def test_defaults_preserve_existing_runtime_endpoints(self):
        config = load_application_config("instance", environ={})

        self.assertEqual("healthcare_lab", config["PROJECT_MODE"])
        self.assertEqual("localhost", config["OIE_MLLP_ORDER_HOST"])
        self.assertEqual(6600, config["OIE_MLLP_ORDER_PORT"])
        self.assertEqual("0.0.0.0", config["OIE_MLLP_RESULT_HOST"])
        self.assertEqual(6665, config["OIE_MLLP_RESULT_PORT"])
        self.assertEqual("create-missing", config["OIE_BOOTSTRAP_MODE"])
        self.assertEqual(120.0, config["OIE_BOOTSTRAP_TIMEOUT_SECONDS"])
        self.assertEqual(2.0, config["OIE_BOOTSTRAP_RETRY_INTERVAL_SECONDS"])
        self.assertEqual(str(Path("instance") / "gdt-bridge"), config["GDT_BRIDGE_PATH"])

    def test_explicit_database_and_environment_values_are_applied(self):
        config = load_application_config(
            "instance",
            "custom.db",
            environ={
                "PROJECT_MODE": "test",
                "OIE_MLLP_ORDER_PORT": "7777",
                "GDT_BRIDGE_IMPORT_SUCCESS_MODE": "delete",
            },
        )

        self.assertEqual("custom.db", config["DATABASE_PATH"])
        self.assertEqual("test", config["PROJECT_MODE"])
        self.assertEqual(7777, config["OIE_MLLP_ORDER_PORT"])
        self.assertEqual("delete", config["GDT_BRIDGE_IMPORT_SUCCESS_MODE"])

    def test_explicit_bootstrap_configuration_is_applied(self):
        config = load_application_config("instance", environ={
            "OIE_BOOTSTRAP_MODE": "off",
            "OIE_BOOTSTRAP_TIMEOUT_SECONDS": "30.5",
            "OIE_BOOTSTRAP_RETRY_INTERVAL_SECONDS": "0.25",
        })

        self.assertEqual("off", config["OIE_BOOTSTRAP_MODE"])
        self.assertEqual(30.5, config["OIE_BOOTSTRAP_TIMEOUT_SECONDS"])
        self.assertEqual(0.25, config["OIE_BOOTSTRAP_RETRY_INTERVAL_SECONDS"])

    def test_application_secrets_load_from_compose_secret_files(self):
        with tempfile.TemporaryDirectory() as directory:
            secret_directory = Path(directory)
            (secret_directory / "MEDPLUM_CLIENT_SECRET").write_text(
                "legacy-secret\n", encoding="utf-8"
            )
            config = load_application_config(
                "instance",
                environ={},
                secret_directory=secret_directory,
            )

        self.assertEqual("legacy-secret", config["MEDPLUM_CLIENT_SECRET"])

    def test_invalid_bootstrap_configuration_is_rejected(self):
        invalid = (
            {"OIE_BOOTSTRAP_MODE": "force"},
            {"OIE_BOOTSTRAP_TIMEOUT_SECONDS": "0"},
            {"OIE_BOOTSTRAP_RETRY_INTERVAL_SECONDS": "not-a-number"},
        )
        for environ in invalid:
            with self.subTest(environ=environ), self.assertRaises(ValidationError):
                load_application_config("instance", environ=environ)

    def test_invalid_app_port_is_rejected(self):
        with self.assertRaises(ValidationError):
            parse_app_port("70000")


if __name__ == "__main__":
    unittest.main()
