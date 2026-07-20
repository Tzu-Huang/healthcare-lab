import contextlib
import socket
import subprocess
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from backend.application_composition import assemble_application_dependencies


ROOT = Path(__file__).resolve().parents[1]


def require_disposable_path(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise AssertionError(f"resource escapes disposable root: {resolved_candidate}") from exc
    if ROOT / "instance" == resolved_candidate or ROOT / "instance" in resolved_candidate.parents:
        raise AssertionError(f"repository instance resource is prohibited: {resolved_candidate}")
    return resolved_candidate


@contextlib.contextmanager
def prohibit_live_resources():
    message = "live external resources are prohibited by characterization tests"
    with (
        patch.object(urllib.request, "urlopen", side_effect=AssertionError(message)),
        patch.object(socket, "create_connection", side_effect=AssertionError(message)),
        patch.object(subprocess, "run", side_effect=AssertionError(message)),
        patch.object(subprocess, "Popen", side_effect=AssertionError(message)),
    ):
        yield


class DisposableResourceGuardTests(unittest.TestCase):
    def test_protocol_store_database_is_below_explicit_temporary_root(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            database_path = require_disposable_path(
                temporary_root, temporary_root / "protocol-characterization.db"
            )

            store = assemble_application_dependencies(database_path)

            self.assertEqual(Path(store.database.path).resolve(), database_path)
            self.assertNotIn(ROOT / "instance", database_path.parents)

    def test_repository_instance_and_other_non_temporary_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            prohibited = (
                ROOT / "instance" / "healthcare-lab.db",
                ROOT / "outside-characterization.db",
            )
            for path in prohibited:
                with self.subTest(path=path), self.assertRaisesRegex(
                    AssertionError, "resource escapes disposable root"
                ):
                    require_disposable_path(temporary_root, path)

    def test_network_socket_and_process_entry_points_fail_without_doubles(self):
        with prohibit_live_resources():
            operations = (
                lambda: urllib.request.urlopen("https://example.invalid"),
                lambda: socket.create_connection(("127.0.0.1", 9)),
                lambda: subprocess.run(["docker", "version"], check=False),
                lambda: subprocess.Popen(["docker", "version"]),
            )
            for operation in operations:
                with self.subTest(operation=operation), self.assertRaisesRegex(
                    AssertionError, "live external resources are prohibited"
                ):
                    operation()


if __name__ == "__main__":
    unittest.main()
