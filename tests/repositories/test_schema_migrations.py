import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.application_composition import assemble_application_dependencies
from backend.repositories.database import SQLiteDatabase
from backend.repositories.schema import ADDITIVE_COLUMNS, APPLICATION_MIGRATIONS


class ApplicationSchemaMigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    @staticmethod
    def _schema_inventory(database_path):
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        objects = connection.execute(
            """
            SELECT type, name
            FROM sqlite_master
            WHERE type IN ('table', 'index')
              AND name NOT LIKE 'sqlite_%'
              AND name != 'schema_migrations'
            ORDER BY type, name
            """
        ).fetchall()
        tables = [row["name"] for row in objects if row["type"] == "table"]
        indexes = [row["name"] for row in objects if row["type"] == "index"]
        columns = {
            table: [
                (row["name"], row["type"], row["notnull"], row["dflt_value"], row["pk"])
                for row in connection.execute(f"PRAGMA table_info({table})")
            ]
            for table in tables
        }
        connection.close()
        return tables, indexes, columns

    def test_fresh_migrated_schema_matches_legacy_initializer(self):
        legacy_path = self.root / "legacy.db"
        migrated_path = self.root / "migrated.db"
        assemble_application_dependencies(legacy_path)

        database = SQLiteDatabase(migrated_path, migrations=APPLICATION_MIGRATIONS)
        database.initialize()

        legacy = self._schema_inventory(legacy_path)
        migrated = self._schema_inventory(migrated_path)
        self.assertEqual(migrated, legacy)
        self.assertEqual(len(migrated[0]), 23)
        self.assertEqual(len(migrated[1]), 20)

    def test_current_unversioned_database_is_recorded_without_data_loss(self):
        database_path = self.root / "current.db"
        store = assemble_application_dependencies(database_path)
        patient = store.patient_repository.create_patient_record(
            {
                "mrn": "MRN-UNVERSIONED-1",
                "firstName": "Current",
                "lastName": "Database",
                "dob": "19850412",
                "sex": "F",
            }
        )

        database = SQLiteDatabase(database_path, migrations=APPLICATION_MIGRATIONS)
        database.initialize()
        database.initialize()

        with database.connect() as connection:
            versions = [
                row["version"]
                for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")
            ]
            preserved = connection.execute(
                "SELECT mrn FROM local_patient_records WHERE id = ?", (patient["id"],)
            ).fetchone()
        self.assertEqual(versions, [1, 2, 3, 4, 5, 6])
        self.assertEqual(preserved["mrn"], "MRN-UNVERSIONED-1")

    def test_partial_legacy_columns_are_added_before_indexes(self):
        database_path = self.root / "partial.db"
        connection = sqlite3.connect(database_path)
        connection.execute(
            """
            CREATE TABLE local_dcm4chee_result_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_record_id INTEGER NOT NULL,
                mapping_id INTEGER,
                last_refreshed_at TEXT NOT NULL DEFAULT ''
            )
            """
        )
        connection.commit()
        connection.close()

        database = SQLiteDatabase(database_path, migrations=APPLICATION_MIGRATIONS)
        database.initialize()

        with database.connect() as connection:
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(local_dcm4chee_result_records)")
            }
            indexes = {
                row["name"]
                for row in connection.execute("PRAGMA index_list(local_dcm4chee_result_records)")
            }
        self.assertIn("refresh_generation", columns)
        self.assertIn("idx_dcm4chee_result_generation", indexes)

    def test_additive_column_registry_matches_the_target_schema(self):
        database_path = self.root / "columns.db"
        database = SQLiteDatabase(database_path, migrations=APPLICATION_MIGRATIONS)
        database.initialize()

        with database.connect() as connection:
            for table_name, column_name, _definition in ADDITIVE_COLUMNS:
                columns = {
                    row["name"]
                    for row in connection.execute(f"PRAGMA table_info({table_name})")
                }
                self.assertIn(column_name, columns, f"{table_name}.{column_name}")
