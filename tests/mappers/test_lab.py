import unittest

from backend.mappers.lab import project_operation, project_server


class LabMapperTests(unittest.TestCase):
    def test_server_and_operation_projection_preserve_public_shapes(self):
        server = project_server({
            "id": 1, "name": "Tool", "server_type": "Test Tool", "description": "", "host": "127.0.0.1",
            "port": 9000, "base_url": "http://127.0.0.1:9000", "protocol": "HTTP", "enabled": 1,
            "version": "1", "check_config_json": '{"path":"/health"}', "control_type": "external",
            "backing_service": "tool", "supported_actions_json": '["status"]', "operation_timeout_seconds": 30,
            "smoke_profile": "tool", "overall_status": "Healthy", "process_status": "Healthy",
            "application_status": "Healthy", "protocol_status": "Healthy", "last_check_at": "checked",
            "recent_error": "", "created_at": "created", "updated_at": "updated",
        })
        operation = project_operation({
            "id": 2, "server_id": 1, "service_name": "Tool", "action": "status", "operator": "tester",
            "result": "Healthy", "duration_ms": 12, "progress_json": '[{"status":"completed"}]',
            "error_text": "", "started_at": "started", "completed_at": "completed",
        })

        self.assertTrue(server["enabled"])
        self.assertEqual(server["checkConfig"], {"path": "/health"})
        self.assertEqual(server["operation"]["supportedActions"], ["status"])
        self.assertEqual(server["checks"], {"process": "Healthy", "application": "Healthy", "protocol": "Healthy"})
        self.assertEqual(operation["progress"], [{"status": "completed"}])


if __name__ == "__main__":
    unittest.main()
