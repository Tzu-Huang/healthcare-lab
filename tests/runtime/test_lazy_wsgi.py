import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.runtime.lazy_wsgi import LazyWsgiApplication


ROOT = Path(__file__).parents[2]


class LazyWsgiApplicationTest(unittest.TestCase):
    def test_factory_runs_only_when_application_is_used(self):
        created = []
        concrete = object()
        application = LazyWsgiApplication(lambda: created.append(True) or concrete)

        self.assertEqual([], created)
        self.assertIs(concrete, application.get())
        self.assertIs(concrete, application.get())
        self.assertEqual([True], created)

    def test_importing_app_factory_does_not_create_default_database(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = os.environ.copy()
            environment["PYTHONPATH"] = os.pathsep.join(
                filter(None, (str(ROOT), environment.get("PYTHONPATH", "")))
            )
            result = subprocess.run(
                [
                    str(ROOT / ".venv" / "Scripts" / "python.exe"),
                    "-c",
                    "import backend.app_factory",
                ],
                cwd=directory,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse((Path(directory) / "instance" / "healthcare-lab.db").exists())


if __name__ == "__main__":
    unittest.main()
