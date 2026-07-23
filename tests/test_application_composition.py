from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path

from backend.application_composition import (
    ApplicationDependencies,
    assemble_application_dependencies,
)


class ApplicationCompositionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.directory.cleanup()

    def test_assembly_initializes_declared_owners_with_one_database_lock(self):
        dependencies = assemble_application_dependencies(
            Path(self.directory.name) / "lab.db"
        )

        self.assertEqual(
            {field.name for field in dataclasses.fields(ApplicationDependencies)},
            {
                "database",
                "integration_settings_repository",
                "integration_settings_service",
                "oie_settings_repository",
                "oie_settings_service",
                "lab_repository",
                "oie_repository",
                "patient_repository",
                "order_repository",
                "dcm4chee_patient_sync_repository",
                "dcm4chee_mwl_repository",
                "dcm4chee_result_repository",
                "dcm4chee_mwl_attempt_coordinator",
                "dcm4chee_workflow_coordinator",
                "fhir_ledger",
                "patient_fhir",
                "order_fhir",
                "gdt_repository",
                "gdt_workflow",
            },
        )
        self.assertTrue(Path(dependencies.database.path).exists())
        self.assertIs(dependencies.patient_repository.lock, dependencies.database.lock)
        self.assertIs(dependencies.order_repository.lock, dependencies.database.lock)
        self.assertIs(dependencies.lab_repository.lock, dependencies.database.lock)

    def test_dependency_result_is_data_only_and_has_no_dynamic_forwarding(self):
        self.assertTrue(dataclasses.is_dataclass(ApplicationDependencies))
        self.assertNotIn("__getattr__", ApplicationDependencies.__dict__)
        declared_methods = {
            name
            for name, value in ApplicationDependencies.__dict__.items()
            if callable(value) and not name.startswith("__")
        }
        self.assertEqual(declared_methods, set())

    def test_production_source_has_no_removed_facade_or_broad_extension(self):
        project_root = Path(__file__).resolve().parents[1]
        forbidden = (
            "Demo" + "Store",
            "backend." + "lab_store",
            "backend." + "application" + "_defaults",
            'extensions["' + "demo" + "_" + "store" + '"]',
            "extensions['" + "demo" + "_" + "store" + "']",
        )
        production_files = [project_root / "app.py", *project_root.glob("backend/**/*.py")]

        violations = {
            str(path.relative_to(project_root)): token
            for path in production_files
            for token in forbidden
            if token in path.read_text(encoding="utf-8")
        }

        self.assertEqual(violations, {})


if __name__ == "__main__":
    unittest.main()
