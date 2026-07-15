import tempfile
import unittest
from pathlib import Path

from backend.domain.errors import SimulatorValidationError
from backend.lab_store import DemoStore


class LabRepositoryCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = DemoStore(Path(self.directory.name) / "lab.db")
        self.repository = self.store

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


if __name__ == "__main__":
    unittest.main()
