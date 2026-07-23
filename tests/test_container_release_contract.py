from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ContainerReleaseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        cls.dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        cls.requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        cls.root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        cls.deploy_readme = (ROOT / "deploy" / "README.md").read_text(encoding="utf-8")
        cls.release_guide = (ROOT / "docs" / "container-release.md").read_text(encoding="utf-8")
        cls.release_checklist = (
            ROOT / "docs" / "releases" / "v1.0.0-checklist.md"
        ).read_text(encoding="utf-8")

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
        self.assertIn('"backend.wsgi:app"', self.dockerfile)
        self.assertIn("docs/Dashboard_to_OIE_to_AP.xml", self.dockerfile)
        self.assertIn("docs/AP_RESULT_TO_LAB.xml", self.dockerfile)
        self.assertIn("!docs/Dashboard_to_OIE_to_AP.xml", self.dockerignore)
        self.assertIn("!docs/AP_RESULT_TO_LAB.xml", self.dockerignore)
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
            "**/__pycache__",
            "**/*.py[cod]",
        ):
            self.assertIn(path, excluded)

        self.assertNotIn("COPY .", self.dockerfile)

    def test_operator_docs_define_docker_only_install_and_supported_boundary(self):
        combined = "\n".join((self.root_readme, self.deploy_readme, self.release_guide))
        for contract in (
            "ghcr.io/tzu-huang/healthcare-lab:1.0.0",
            "linux/amd64",
            "Docker Compose",
            "/var/run/docker.sock",
            "trusted",
            "public-Internet",
            "production patient data",
        ):
            self.assertIn(contract, combined)

    def test_release_guide_covers_tags_backup_upgrade_and_rollback(self):
        for contract in (
            "`1.0.0`",
            "`latest`",
            "`edge`",
            "## Backup, upgrade, and rollback",
            "lab-app-instance",
            "LAB_APP_IMAGE",
        ):
            self.assertIn(contract, self.release_guide)

    def test_v1_release_checklist_defers_publication_and_verifies_artifacts(self):
        for contract in (
            "does not create the Git tag",
            "OpenSpec verification",
            "Image inspection",
            "unauthenticated `docker pull",
            "Post-publication smoke",
        ):
            self.assertIn(contract, self.release_checklist)


if __name__ == "__main__":
    unittest.main()
