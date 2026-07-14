import unittest
from pathlib import Path

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

    def test_invalid_app_port_is_rejected(self):
        with self.assertRaises(ValidationError):
            parse_app_port("70000")


if __name__ == "__main__":
    unittest.main()
