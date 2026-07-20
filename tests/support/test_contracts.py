import tempfile
import unittest
from pathlib import Path

from tests.support import (
    DisposableAppCase,
    FakeDbConnection,
    FakeDockerSocketLabOperationAdapter,
    FakeHttpResponse,
)


class SupportContractTests(unittest.TestCase):
    def test_http_response_double_preserves_context_and_status_contract(self):
        response = FakeHttpResponse(b"ok", status=201)
        with response as active:
            self.assertIs(active, response)
            self.assertEqual(active.status, 201)
            self.assertEqual(active.read(), b"ok")

    def test_database_double_exposes_rows_and_close_state(self):
        connection = FakeDbConnection(rows=[{"id": 1}])
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            self.assertEqual(cursor.fetchall(), [{"id": 1}])
        connection.close()
        self.assertTrue(connection.closed)

    def test_docker_double_records_control_request_without_socket(self):
        adapter = FakeDockerSocketLabOperationAdapter()
        result = adapter.run("stop", "oie", timeout_seconds=10)
        self.assertEqual(result["returnCode"], 0)
        self.assertEqual(adapter.requested_paths, ["/containers/container-1/stop?t=10"])

    def test_disposable_app_case_declares_explicit_temp_root(self):
        with tempfile.TemporaryDirectory() as root:
            case = DisposableAppCase("runTest")
            case.temp_dir = tempfile.TemporaryDirectory(dir=root)
            self.assertTrue(Path(case.temp_dir.name).is_relative_to(Path(root)))
            case.temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
