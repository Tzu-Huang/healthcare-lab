import socket
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from backend.app_factory import create_app
from backend.application_composition import assemble_application_dependencies


class OieListenerLifecycleIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.bootstrap_environment = patch.dict(
            "os.environ", {"OIE_BOOTSTRAP_MODE": "off"}, clear=False
        )
        self.bootstrap_environment.start()
        self.directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.directory.name) / "lab.db"

    def tearDown(self):
        self.directory.cleanup()
        self.bootstrap_environment.stop()

    @staticmethod
    def _free_port():
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        return port

    @staticmethod
    def _payload(port, *, auto_start=True):
        return {
            "managementApi": {
                "baseUrl": "http://oie:8080", "username": "admin",
                "tlsVerify": False, "timeoutSeconds": 10,
            },
            "resultListener": {
                "host": "127.0.0.1", "port": port,
                "mllpFraming": True, "autoStart": auto_start,
            },
            "managedChannels": [],
        }

    def _seed(self, port, *, auto_start=True):
        dependencies = assemble_application_dependencies(self.database_path)
        dependencies.oie_settings_repository.update(self._payload(port, auto_start=auto_start))

    def test_composition_auto_starts_once_from_persisted_settings(self):
        port = self._free_port()
        self._seed(port)

        app = create_app(str(self.database_path))
        listener = app.extensions["oie_result_listener"]
        try:
            status = listener.status()
            self.assertEqual("running", status["state"])
            self.assertEqual(("127.0.0.1", port), (status["host"], status["port"]))
        finally:
            listener.stop()

        restarted = create_app(str(self.database_path))
        try:
            self.assertEqual("running", restarted.extensions["oie_result_listener"].status()["state"])
        finally:
            restarted.extensions["oie_result_listener"].stop()

    def test_disabled_auto_start_does_not_bind(self):
        port = self._free_port()
        self._seed(port, auto_start=False)

        app = create_app(str(self.database_path))

        self.assertEqual("stopped", app.extensions["oie_result_listener"].status()["state"])

    def test_port_conflict_degrades_listener_but_keeps_http_available(self):
        occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        occupied.bind(("127.0.0.1", 0))
        occupied.listen(1)
        port = occupied.getsockname()[1]
        self._seed(port)
        try:
            app = create_app(str(self.database_path))
            client = app.test_client()
            response = client.get("/api/oie/result-listener/status")
        finally:
            occupied.close()

        self.assertEqual(200, response.status_code)
        self.assertEqual("degraded", response.get_json()["item"]["state"])
        self.assertTrue(response.get_json()["item"]["lastError"])

    def test_retry_reloads_corrected_persisted_configuration(self):
        occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        occupied.bind(("127.0.0.1", 0))
        occupied.listen(1)
        blocked_port = occupied.getsockname()[1]
        self._seed(blocked_port)
        app = create_app(str(self.database_path))
        client = app.test_client()
        occupied.close()
        available_port = self._free_port()
        payload = self._payload(available_port)
        self.assertEqual(200, client.put("/api/oie/settings", json=payload).status_code)
        try:
            response = client.post("/api/oie/result-listener/retry")
            self.assertEqual(200, response.status_code)
            self.assertEqual("running", response.get_json()["item"]["state"])
            self.assertEqual(available_port, response.get_json()["item"]["port"])
        finally:
            app.extensions["oie_result_listener"].stop()

    def test_changed_running_configuration_requires_stop_and_stop_is_temporary(self):
        first_port = self._free_port()
        second_port = self._free_port()
        self._seed(first_port)
        app = create_app(str(self.database_path))
        client = app.test_client()
        self.assertEqual(200, client.put("/api/oie/settings", json=self._payload(second_port)).status_code)

        rejected = client.post("/api/oie/result-listener/retry")

        self.assertEqual(400, rejected.status_code)
        self.assertIn("Stop the current listener", rejected.get_json()["error"])
        stopped = client.post("/api/oie/result-listener/stop").get_json()["item"]
        self.assertEqual("stopped", stopped["state"])
        self.assertTrue(
            app.extensions["oie_workflow_service"]
            ._listener_configuration_source
            .get_result_listener_configuration()["auto_start"]
        )


if __name__ == "__main__":
    unittest.main()
