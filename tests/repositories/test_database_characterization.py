import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.application_composition import assemble_application_dependencies


class SQLiteDatabaseCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.directory.name) / "lab.db"

    def tearDown(self):
        self.directory.cleanup()

    def test_connection_configuration_and_close_behavior(self):
        store = assemble_application_dependencies(self.database_path)

        with store.database.connect() as connection:
            self.assertIs(connection.row_factory, sqlite3.Row)
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA busy_timeout").fetchone()[0], 5000)
            self.assertEqual(connection.execute("SELECT 1 AS value").fetchone()["value"], 1)

        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_connection_commits_success_and_rolls_back_exception(self):
        store = assemble_application_dependencies(self.database_path)

        with store.database.connect() as connection:
            connection.execute(
                "INSERT INTO local_identifier_sequences (name, next_value) VALUES (?, ?)",
                ("committed", 7),
            )

        with self.assertRaisesRegex(RuntimeError, "abort transaction"):
            with store.database.connect() as connection:
                connection.execute(
                    "INSERT INTO local_identifier_sequences (name, next_value) VALUES (?, ?)",
                    ("rolled_back", 8),
                )
                raise RuntimeError("abort transaction")

        with store.database.connect() as connection:
            rows = connection.execute(
                "SELECT name, next_value FROM local_identifier_sequences "
                "WHERE name IN ('committed', 'rolled_back') ORDER BY name"
            ).fetchall()
        self.assertEqual([(row["name"], row["next_value"]) for row in rows], [("committed", 7)])

    def test_store_and_extracted_repository_share_one_write_lock(self):
        store = assemble_application_dependencies(self.database_path)

        self.assertIs(store.oie_settings_repository._lock, store.database.lock)
        self.assertIs(store.oie_settings_repository._connect.__self__, store.database)

    def test_unversioned_reopen_preserves_rows_and_user_managed_seed_values(self):
        store = assemble_application_dependencies(self.database_path)
        patient = store.patient_repository.create_patient_record(
            {
                "mrn": "MRN-900001",
                "firstName": "Legacy",
                "lastName": "Patient",
                "dob": "19850412",
                "sex": "F",
            }
        )
        oie = next(item for item in store.lab_repository.list_servers() if item["name"] == "OIE")
        store.lab_repository.update_server(oie["id"], {"host": "legacy-oie.example.test"})
        settings = store.oie_settings_repository.get()
        settings["managementApi"].update(
            {
                "baseUrl": "https://legacy-oie.example.test/api",
                "username": "legacy-operator",
                "password": "legacy-secret",
            }
        )
        store.oie_settings_repository.update(settings)

        reopened = assemble_application_dependencies(self.database_path)

        self.assertEqual(reopened.patient_repository.get_patient_record(patient["id"])["summary"]["mrn"], "MRN-900001")
        reopened_oie = next(item for item in reopened.lab_repository.list_servers() if item["name"] == "OIE")
        self.assertEqual(reopened_oie["host"], "legacy-oie.example.test")
        reopened_settings = reopened.oie_settings_repository.get()
        self.assertEqual(reopened_settings["managementApi"]["baseUrl"], "https://legacy-oie.example.test/api")
        self.assertEqual(reopened_settings["managementApi"]["username"], "legacy-operator")

    def test_partial_legacy_lab_server_schema_is_upgraded_before_seeding(self):
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            """
            CREATE TABLE lab_servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                server_type TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                host TEXT NOT NULL DEFAULT '',
                port INTEGER,
                base_url TEXT NOT NULL DEFAULT '',
                protocol TEXT NOT NULL DEFAULT 'None',
                enabled INTEGER NOT NULL DEFAULT 1,
                version TEXT NOT NULL DEFAULT '',
                check_config_json TEXT NOT NULL DEFAULT '{}',
                overall_status TEXT NOT NULL DEFAULT 'Unknown',
                process_status TEXT NOT NULL DEFAULT 'Unknown',
                application_status TEXT NOT NULL DEFAULT 'Unknown',
                protocol_status TEXT NOT NULL DEFAULT 'Unknown',
                last_check_at TEXT NOT NULL DEFAULT '',
                recent_error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO lab_servers (
                name, server_type, description, host, port, base_url, protocol,
                created_at, updated_at
            ) VALUES ('OIE', 'Interface Engine', '', 'legacy-host', 8080, '', 'HTTP', 'old', 'old')
            """
        )
        connection.commit()
        connection.close()

        store = assemble_application_dependencies(self.database_path)

        with store.database.connect() as connection:
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(lab_servers)")}
        self.assertTrue(
            {
                "control_type",
                "backing_service",
                "supported_actions_json",
                "operation_timeout_seconds",
                "smoke_profile",
            }.issubset(columns)
        )
        oie = next(item for item in store.lab_repository.list_servers() if item["name"] == "OIE")
        self.assertEqual(oie["host"], "legacy-host")
