from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ContainerReleaseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        cls.dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        cls.requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    def test_image_contains_owned_runtime_files(self):
        for instruction in (
            "COPY app.py ./",
            "COPY backend ./backend",
            "COPY frontend ./frontend",
            "COPY requirements.txt ./",
        ):
            self.assertIn(instruction, self.dockerfile)

    def test_image_uses_single_worker_production_wsgi(self):
        self.assertIn("gunicorn>=23.0,<24.0", self.requirements)
        self.assertIn('"gunicorn"', self.dockerfile)
        self.assertIn('"--workers", "1"', self.dockerfile)
        self.assertIn('"backend.app_factory:app"', self.dockerfile)
        self.assertNotIn('CMD ["python", "app.py"]', self.dockerfile)

    def test_image_declares_runtime_and_traceability_contracts(self):
        self.assertIn("EXPOSE 5000 6665", self.dockerfile)
        self.assertIn('VOLUME ["/app/instance", "/data/gdt-bridge"]', self.dockerfile)
        self.assertIn("HEALTHCHECK", self.dockerfile)
        self.assertIn("org.opencontainers.image.revision", self.dockerfile)
        self.assertIn("org.opencontainers.image.version", self.dockerfile)

    def test_build_context_excludes_local_state_and_secrets(self):
        excluded = {
            line.strip()
            for line in self.dockerignore.splitlines()
            if line.strip() and not line.startswith("#")
        }
        for path in (
            ".git",
            ".env",
            ".venv",
            "instance",
            "tests",
            "openspec",
            "__pycache__",
        ):
            self.assertIn(path, excluded)

        self.assertNotIn("COPY .", self.dockerfile)


if __name__ == "__main__":
    unittest.main()
