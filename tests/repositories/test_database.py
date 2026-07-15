import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.repositories.database import Migration, SQLiteDatabase


class SQLiteDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.directory.name) / "database.db"

    def tearDown(self):
        self.directory.cleanup()

    def test_connection_preserves_configuration_commit_rollback_and_close(self):
        database = SQLiteDatabase(self.database_path)
        database.initialize()

        with database.connect() as connection:
            self.assertIs(connection.row_factory, sqlite3.Row)
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA busy_timeout").fetchone()[0], 5000)
            connection.execute("CREATE TABLE values_table (value TEXT NOT NULL)")
            connection.execute("INSERT INTO values_table VALUES ('committed')")

        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with database.connect() as connection:
                connection.execute("INSERT INTO values_table VALUES ('rolled-back')")
                raise RuntimeError("rollback")

        with database.connect() as connection:
            values = [row["value"] for row in connection.execute("SELECT value FROM values_table")]
        self.assertEqual(values, ["committed"])
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_migrations_run_once_in_order_and_maintenance_runs_on_reopen(self):
        calls = []

        def first(connection):
            calls.append("migration-1")
            connection.execute("CREATE TABLE records (value TEXT NOT NULL)")

        def second(connection):
            calls.append("migration-2")
            connection.execute("INSERT INTO records VALUES ('seeded-by-migration')")

        def maintenance(connection):
            calls.append("maintenance")
            connection.execute(
                "INSERT INTO records SELECT 'maintained' "
                "WHERE NOT EXISTS (SELECT 1 FROM records WHERE value = 'maintained')"
            )

        database = SQLiteDatabase(
            self.database_path,
            migrations=(Migration(1, "create-records", first), Migration(2, "seed-record", second)),
            maintenance=(maintenance,),
            timestamp_factory=lambda: "2026-07-15T00:00:00+00:00",
        )
        database.initialize()
        database.initialize()

        self.assertEqual(calls, ["migration-1", "migration-2", "maintenance", "maintenance"])
        with database.connect() as connection:
            ledger = [
                (row["version"], row["name"], row["applied_at"])
                for row in connection.execute("SELECT * FROM schema_migrations ORDER BY version")
            ]
            values = [row["value"] for row in connection.execute("SELECT value FROM records ORDER BY value")]
        self.assertEqual(
            ledger,
            [
                (1, "create-records", "2026-07-15T00:00:00+00:00"),
                (2, "seed-record", "2026-07-15T00:00:00+00:00"),
            ],
        )
        self.assertEqual(values, ["maintained", "seeded-by-migration"])

    def test_failed_migration_is_not_recorded_and_corrected_rerun_resumes(self):
        calls = []

        def first(connection):
            calls.append("first")
            connection.execute("CREATE TABLE records (value TEXT NOT NULL)")

        def failing(connection):
            calls.append("failing")
            connection.execute("INSERT INTO records VALUES ('must-roll-back')")
            raise RuntimeError("injected migration failure")

        database = SQLiteDatabase(
            self.database_path,
            migrations=(Migration(1, "create-records", first), Migration(2, "populate", failing)),
        )
        with self.assertRaisesRegex(RuntimeError, "injected migration failure"):
            database.initialize()

        with database.connect() as connection:
            ledger = connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
            values = connection.execute("SELECT value FROM records").fetchall()
        self.assertEqual([row["version"] for row in ledger], [1])
        self.assertEqual(values, [])

        def corrected(connection):
            calls.append("corrected")
            connection.execute("INSERT INTO records VALUES ('recovered')")

        def third(connection):
            calls.append("third")
            connection.execute("CREATE INDEX idx_records_value ON records(value)")

        resumed = SQLiteDatabase(
            self.database_path,
            migrations=(
                Migration(1, "create-records", first),
                Migration(2, "populate", corrected),
                Migration(3, "index-records", third),
            ),
        )
        resumed.initialize()

        self.assertEqual(calls, ["first", "failing", "corrected", "third"])
        with resumed.connect() as connection:
            ledger = connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
            values = connection.execute("SELECT value FROM records").fetchall()
        self.assertEqual([row["version"] for row in ledger], [1, 2, 3])
        self.assertEqual([row["value"] for row in values], ["recovered"])

    def test_migration_registry_rejects_non_monotonic_versions(self):
        noop = lambda connection: None
        with self.assertRaisesRegex(ValueError, "unique and strictly increasing"):
            SQLiteDatabase(
                self.database_path,
                migrations=(Migration(2, "second", noop), Migration(1, "first", noop)),
            )
