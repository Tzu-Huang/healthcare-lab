import tempfile
import unittest
from pathlib import Path

from backend.domain.errors import SimulatorValidationError
from backend.lab_store import DemoStore


class LabRepositoryCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = DemoStore(Path(self.directory.name) / "lab.db")
        self.repository = self.store.lab_repository

    def tearDown(self):
        self.directory.cleanup()

    def test_server_crud_health_and_projection(self):
        created = self.repository.create_lab_server(
            {
                "name": "Disposable Lab",
                "serverType": "Test Tool",
                "protocol": "HTTP",
                "baseUrl": "http://127.0.0.1:9010",
                "checkConfig": {"path": "/health"},
            }
        )
        self.assertEqual(created["checkConfig"], {"path": "/health"})
        updated = self.repository.update_lab_server(
            created["id"], {"description": "characterized", "enabled": False}
        )
        self.assertFalse(updated["enabled"])
        healthy = self.repository.update_lab_server_health(
            created["id"],
            overall_status="Healthy",
            process_status="Healthy",
            application_status="Healthy",
            protocol_status="Healthy",
            version="1.2.3",
        )
        self.assertEqual(healthy["overallStatus"], "Healthy")
        self.assertEqual(healthy["version"], "1.2.3")
        self.assertEqual(self.repository.get_lab_server(created["id"]), healthy)

    def test_operation_history_and_validation_errors(self):
        server = self.repository.list_lab_servers()[0]
        operation = self.repository.record_lab_operation(
            server["id"],
            service_name=server["name"],
            action="restart",
            operator="tester",
            result="failed",
            duration_ms=-1,
            progress=[{"step": "start", "status": "failed"}],
            error_text="boom",
        )
        self.assertEqual(operation["durationMs"], 0)
        self.assertEqual(operation["progress"][0]["status"], "failed")
        self.assertEqual(self.repository.list_lab_operations(server["id"])[0], operation)
        with self.assertRaisesRegex(SimulatorValidationError, "Unsupported lab operation"):
            self.repository.record_lab_operation(
                server["id"], service_name=server["name"], action="purge",
                operator="tester", result="failed"
            )
        with self.assertRaisesRegex(SimulatorValidationError, "Base URL"):
            self.repository.create_lab_server(
                {"name": "Bad", "serverType": "Test Tool", "protocol": "HTTP",
                 "baseUrl": "localhost:9010"}
            )

    def test_store_and_database_share_write_lock(self):
        self.assertIs(self.store.lock, self.store.database.lock)
        self.assertIs(self.repository.lock, self.store.database.lock)

    def test_store_compatibility_delegates_match_direct_repository(self):
        self.assertEqual(self.store.list_lab_servers(), self.repository.list_servers())
        server_id = self.store.list_lab_servers()[0]["id"]
        self.assertEqual(self.store.get_lab_server(server_id), self.repository.get_server(server_id))

    def test_operation_metadata_is_seeded_non_destructively(self):
        oie = next(item for item in self.repository.list_lab_servers() if item["name"] == "OIE")
        self.assertEqual(oie["operation"]["controlType"], "docker-compose")
        self.assertEqual(oie["operation"]["backingService"], "oie")
        self.assertIn("restart", oie["operation"]["supportedActions"])
        self.assertEqual(oie["operation"]["smokeProfile"], "oie")

        self.repository.update_lab_server(
            oie["id"],
            {"host": "10.10.10.10", "baseUrl": "http://10.10.10.10:18080"},
        )
        reopened = DemoStore(self.store.path).lab_repository
        updated = reopened.get_lab_server(oie["id"])

        self.assertEqual(updated["host"], "10.10.10.10")
        self.assertEqual(updated["baseUrl"], "http://10.10.10.10:18080")
        self.assertEqual(updated["operation"]["backingService"], "oie")

    def test_custom_operation_metadata_can_be_persisted(self):
        created = self.repository.create_lab_server(
            {
                "name": "Custom Lab Tool",
                "serverType": "Test Tool",
                "protocol": "HTTP",
                "baseUrl": "http://127.0.0.1:9000",
                "operation": {
                    "controlType": "external",
                    "backingService": "custom-tool",
                    "supportedActions": ["status", "smoke"],
                    "timeoutSeconds": 30,
                    "smokeProfile": "custom",
                },
            }
        )

        self.assertEqual(created["operation"]["controlType"], "external")
        self.assertEqual(created["operation"]["backingService"], "custom-tool")
        self.assertEqual(created["operation"]["supportedActions"], ["status", "smoke"])
        self.assertEqual(created["operation"]["timeoutSeconds"], 30)
        self.assertEqual(created["operation"]["smokeProfile"], "custom")

        with self.assertRaisesRegex(SimulatorValidationError, "Unsupported lab operation action"):
            self.repository.update_lab_server(
                created["id"], {"operation": {"supportedActions": ["purge"]}}
            )

    def test_operation_history_persists_progress_and_errors(self):
        medplum = next(
            item for item in self.repository.list_lab_servers() if item["name"] == "Medplum"
        )
        operation = self.repository.record_lab_operation(
            medplum["id"],
            service_name="Medplum",
            action="restart",
            operator="tester",
            result="failed",
            duration_ms=1250,
            progress=[
                {"step": "stop", "status": "completed"},
                {"step": "start", "status": "failed"},
            ],
            error_text="container failed",
        )

        self.assertEqual(operation["serviceName"], "Medplum")
        self.assertEqual(operation["action"], "restart")
        self.assertEqual(operation["operator"], "tester")
        self.assertEqual(operation["durationMs"], 1250)
        self.assertEqual(operation["progress"][1]["status"], "failed")
        self.assertEqual(operation["error"], "container failed")
        self.assertEqual(
            self.repository.list_lab_operations(medplum["id"])[0]["id"], operation["id"]
        )

        with self.assertRaisesRegex(SimulatorValidationError, "Unsupported lab operation action"):
            self.repository.record_lab_operation(
                medplum["id"], service_name="Medplum", action="purge",
                operator="tester", result="failed"
            )


if __name__ == "__main__":
    unittest.main()
