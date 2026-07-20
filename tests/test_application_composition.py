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
                "oie_settings_repository",
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


if __name__ == "__main__":
    unittest.main()
