"""Shared SQLite connection and ordered migration infrastructure."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

MigrationStep = Callable[[sqlite3.Connection], None]
MaintenanceStep = Callable[[sqlite3.Connection], None]


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: MigrationStep


class SQLiteDatabase:
    """Own one SQLite path, write lock, connection policy, and migration lifecycle."""

    def __init__(
        self,
        path: str | Path,
        *,
        migrations: Iterable[Migration] = (),
        maintenance: Iterable[MaintenanceStep] = (),
        timestamp_factory: Callable[[], str] | None = None,
    ) -> None:
        self.path = str(path)
        self.lock = RLock()
        self._migrations = tuple(migrations)
        self._maintenance = tuple(maintenance)
        self._timestamp = timestamp_factory or self._utc_timestamp
        self._validate_migrations()

    @staticmethod
    def _utc_timestamp() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _validate_migrations(self) -> None:
        versions = [migration.version for migration in self._migrations]
        if any(version <= 0 for version in versions):
            raise ValueError("Migration versions must be positive integers.")
        if versions != sorted(set(versions)):
            raise ValueError("Migration versions must be unique and strictly increasing.")
        if any(not migration.name.strip() for migration in self._migrations):
            raise ValueError("Migration names must not be empty.")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.lock:
            self._ensure_migration_ledger()
            applied = self._applied_migrations()
            for migration in self._migrations:
                recorded_name = applied.get(migration.version)
                if recorded_name is not None:
                    if recorded_name != migration.name:
                        raise RuntimeError(
                            f"Migration {migration.version} is recorded as "
                            f"'{recorded_name}', expected '{migration.name}'."
                        )
                    continue
                with self.connect() as connection:
                    migration.apply(connection)
                    connection.execute(
                        """
                        INSERT INTO schema_migrations (version, name, applied_at)
                        VALUES (?, ?, ?)
                        """,
                        (migration.version, migration.name, self._timestamp()),
                    )
            if self._maintenance:
                with self.connect() as connection:
                    for step in self._maintenance:
                        step(connection)

    def _ensure_migration_ledger(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    applied_at TEXT NOT NULL
                )
                """
            )

    def _applied_migrations(self) -> dict[int, str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT version, name FROM schema_migrations ORDER BY version"
            ).fetchall()
        return {int(row["version"]): str(row["name"]) for row in rows}
