import unittest

from backend.domain.errors import SimulatorValidationError
from backend.domain.lab import validate_server_payload


class LabDomainTests(unittest.TestCase):
    def test_server_payload_normalization_preserves_storage_shape(self):
        self.assertEqual(validate_server_payload({
            "name": " Tool ", "serverType": "Test Tool", "protocol": "HTTP",
            "baseUrl": "http://127.0.0.1", "enabled": 0, "checkConfig": {"path": "/health"},
            "operation": {"supportedActions": ["status", "smoke"], "timeoutSeconds": "30"},
        }), {
            "name": "Tool", "server_type": "Test Tool", "base_url": "http://127.0.0.1",
            "protocol": "HTTP", "enabled": 0, "check_config_json": '{"path": "/health"}',
            "supported_actions_json": '["status", "smoke"]', "operation_timeout_seconds": 30,
        })

    def test_server_payload_errors_are_unchanged(self):
        with self.assertRaisesRegex(SimulatorValidationError, "Server name is required"):
            validate_server_payload({"serverType": "Test Tool", "protocol": "None"})
        with self.assertRaisesRegex(SimulatorValidationError, "Port must be an integer"):
            validate_server_payload({"name": "Tool", "serverType": "Test Tool", "protocol": "TCP", "port": "bad"})


if __name__ == "__main__":
    unittest.main()
