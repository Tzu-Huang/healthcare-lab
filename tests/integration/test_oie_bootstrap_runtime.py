import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app_factory import create_app


class FakeThread:
    created = []

    def __init__(self, *, target, name, daemon):
        self.target = target
        self.name = name
        self.daemon = daemon
        self.started = False
        self.__class__.created.append(self)

    def start(self):
        self.started = True


class OieBootstrapRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = str(Path(self.directory.name) / "bootstrap-runtime.db")
        FakeThread.created = []

    def tearDown(self):
        self.directory.cleanup()

    def create(self, *, activate_runtime=True, mode="create-missing"):
        environment = {
            "OIE_BOOTSTRAP_MODE": mode,
            "HLAB_RESULT_LISTENER_HOST": "127.0.0.1",
            "HLAB_RESULT_LISTENER_PORT": "0",
        }
        with patch.dict("os.environ", environment, clear=False), patch(
            "backend.services.oie_workflow.OieWorkflowService.auto_start_listener"
        ):
            return create_app(
                self.path,
                activate_runtime=activate_runtime,
                bootstrap_thread_factory=FakeThread,
            )

    def test_enabled_runtime_starts_one_named_daemon_without_running_inline(self):
        app = self.create()

        self.assertEqual(1, len(FakeThread.created))
        thread = FakeThread.created[0]
        self.assertTrue(thread.started)
        self.assertTrue(thread.daemon)
        self.assertEqual("oie-managed-channel-bootstrap", thread.name)
        self.assertIs(thread, app.extensions["oie_channel_bootstrap_thread"])
        self.assertIsNotNone(app.extensions["oie_channel_bootstrap"])

    def test_off_and_runtime_disabled_modes_do_not_start_bootstrap(self):
        off = self.create(mode="off")
        disabled = self.create(activate_runtime=False)

        self.assertEqual([], FakeThread.created)
        self.assertNotIn("oie_channel_bootstrap_thread", off.extensions)
        self.assertNotIn("oie_channel_bootstrap_thread", disabled.extensions)

    def test_bootstrap_failure_is_deferred_from_http_availability(self):
        app = self.create()
        bootstrap = app.extensions["oie_channel_bootstrap"]

        def fail():
            raise RuntimeError("simulated bootstrap failure")

        bootstrap.run = fail
        FakeThread.created[0].target = bootstrap.run
        with self.assertRaisesRegex(RuntimeError, "simulated bootstrap failure"):
            FakeThread.created[0].target()
        response = app.test_client().get("/")

        self.assertLess(response.status_code, 500)
        self.assertEqual(1, len(FakeThread.created))


if __name__ == "__main__":
    unittest.main()
