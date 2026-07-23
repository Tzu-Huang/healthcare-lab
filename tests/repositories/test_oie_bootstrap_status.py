import sqlite3
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

from backend.repositories.oie_bootstrap_status import OieBootstrapStatusRepository
from backend.services.oie_bootstrap_coordination import OieBootstrapCoordinator


class InlineThread:
    def __init__(self, *, target, name, daemon):
        self.target = target
        self.name = name
        self.daemon = daemon
        self.started = False

    def start(self):
        self.started = True
        self.target()


class UnsupportedVersionBootstrap:
    attempt_observer = lambda self, _attempts: None

    def run(self):
        self.attempt_observer(1)
        channels = [
            {
                "logicalType": logical_type,
                "classification": "unavailable",
                "outcome": "timeout",
                "status": "",
                "errorCategory": "unsupported-version",
            }
            for logical_type in ("hlab-orm-to-ap", "hlab-oru-to-hlab")
        ]
        return {
            "outcome": "timeout",
            "attempts": 1,
            "errorCategory": "unsupported-version",
            "channels": channels,
        }


class OieBootstrapStatusRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "status.db"
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE oie_bootstrap_runs (
                    run_id TEXT PRIMARY KEY,
                    trigger TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    state TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    attempts INTEGER NOT NULL,
                    outcome TEXT NOT NULL,
                    error_category TEXT NOT NULL,
                    guidance_code TEXT NOT NULL
                );
                CREATE TABLE oie_bootstrap_channel_outcomes (
                    run_id TEXT NOT NULL,
                    logical_type TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_category TEXT NOT NULL,
                    guidance_code TEXT NOT NULL,
                    PRIMARY KEY (run_id, logical_type),
                    FOREIGN KEY (run_id) REFERENCES oie_bootstrap_runs(run_id)
                );
                """
            )
        self.repository = OieBootstrapStatusRepository(self.connect, RLock())

    def tearDown(self):
        self.temporary_directory.cleanup()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database_path)
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

    @staticmethod
    def channels():
        return [
            {
                "logicalType": "hlab-orm-to-ap",
                "classification": "missing",
                "outcome": "success",
                "status": "STARTED",
                "errorCategory": "",
                "guidanceCode": "",
            },
            {
                "logicalType": "hlab-oru-to-hlab",
                "classification": "unchanged",
                "outcome": "no-op",
                "status": "DEPLOYED",
                "errorCategory": "",
                "guidanceCode": "",
            },
        ]

    def start(self, run_id="run-1"):
        self.repository.start_run(
            run_id=run_id,
            trigger="startup",
            mode="create-missing",
            started_at="2026-07-23T10:00:00+00:00",
        )

    def test_start_and_attempt_progress_are_projected_for_current_run(self):
        self.start()
        self.repository.update_attempts("run-1", 3)

        status = self.repository.latest_status(current_run_id="run-1")

        self.assertEqual("running", status["state"])
        self.assertEqual(3, status["attempts"])
        self.assertEqual([], status["channels"])

    def test_complete_run_atomically_persists_projection_across_reopen(self):
        self.start()
        self.repository.complete_run(
            "run-1",
            completed_at="2026-07-23T10:01:00+00:00",
            attempts=2,
            outcome="success",
            error_category="",
            guidance_code="",
            channels=self.channels(),
        )

        reopened = OieBootstrapStatusRepository(self.connect, RLock())
        status = reopened.latest_status()

        self.assertEqual("completed", status["state"])
        self.assertEqual("success", status["outcome"])
        self.assertEqual(2, status["attempts"])
        self.assertEqual(
            ["hlab-orm-to-ap", "hlab-oru-to-hlab"],
            [item["logicalType"] for item in status["channels"]],
        )

    def test_coordinator_persists_unsupported_version_with_canonical_guidance(self):
        coordinator = OieBootstrapCoordinator(
            UnsupportedVersionBootstrap(),
            self.repository,
            mode="create-missing",
            thread_factory=InlineThread,
            run_lock=threading.Lock(),
            state_lock=threading.Lock(),
            timestamp_factory=lambda: "2026-07-23T10:00:00+00:00",
            run_id_factory=lambda: "unsupported-run",
        )

        coordinator.start_startup()
        status = coordinator.status()

        self.assertEqual("completed", status["state"])
        self.assertEqual("unsupported-version", status["errorCategory"])
        self.assertEqual("verify-oie-version", status["guidanceCode"])
        self.assertEqual(
            {"unsupported-version"},
            {item["errorCategory"] for item in status["channels"]},
        )
        self.assertEqual(
            {"verify-oie-version"},
            {item["guidanceCode"] for item in status["channels"]},
        )

    def test_stale_running_row_is_projected_as_interrupted_without_mutation(self):
        self.start()

        stale = self.repository.latest_status()
        current = self.repository.latest_status(current_run_id="run-1")

        self.assertEqual("interrupted", stale["state"])
        self.assertEqual("interrupted", stale["outcome"])
        self.assertEqual("retry-bootstrap", stale["guidanceCode"])
        self.assertEqual("running", current["state"])

    def test_invalid_channel_evidence_rolls_back_completion(self):
        self.start()
        unsafe = self.channels()
        unsafe[0]["errorCategory"] = "password=secret"

        with self.assertRaises(ValueError):
            self.repository.complete_run(
                "run-1",
                completed_at="2026-07-23T10:01:00+00:00",
                attempts=1,
                outcome="partial-failure",
                error_category="failure",
                guidance_code="inspect-bootstrap-diagnostics",
                channels=unsafe,
            )

        status = self.repository.latest_status(current_run_id="run-1")
        self.assertEqual("running", status["state"])
        self.assertEqual([], status["channels"])

    def test_completion_requires_each_canonical_channel_exactly_once(self):
        self.start()

        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.repository.complete_run(
                "run-1",
                completed_at="2026-07-23T10:01:00+00:00",
                attempts=1,
                outcome="success",
                error_category="",
                guidance_code="",
                channels=[self.channels()[0], self.channels()[0]],
            )

    def test_completed_run_cannot_be_updated_or_completed_twice(self):
        self.start()
        arguments = dict(
            completed_at="2026-07-23T10:01:00+00:00",
            attempts=1,
            outcome="success",
            error_category="",
            guidance_code="",
            channels=self.channels(),
        )
        self.repository.complete_run("run-1", **arguments)

        with self.assertRaises(KeyError):
            self.repository.update_attempts("run-1", 2)
        with self.assertRaises(KeyError):
            self.repository.complete_run("run-1", **arguments)

    def test_latest_status_returns_none_before_any_run(self):
        self.assertIsNone(self.repository.latest_status())


if __name__ == "__main__":
    unittest.main()
