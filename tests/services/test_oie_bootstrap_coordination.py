import unittest

from backend.services.oie_bootstrap_coordination import (
    BootstrapCommandError,
    OieBootstrapCoordinator,
)


CHANNELS = [
    {"logicalType": "hlab-orm-to-ap", "classification": "unchanged", "outcome": "no-op", "status": ""},
    {"logicalType": "hlab-oru-to-hlab", "classification": "unchanged", "outcome": "no-op", "status": "STARTED"},
]


class FakeRepository:
    def __init__(self, latest=None, *, fail=False):
        self.value = latest
        self.fail = fail
        self.calls = []

    def start_run(self, **values):
        if self.fail:
            raise RuntimeError("database contained password=secret")
        self.calls.append(("start", values))
        self.value = {
            "runId": values["run_id"], "trigger": values["trigger"], "mode": values["mode"],
            "state": "running", "startedAt": values["started_at"], "completedAt": "",
            "attempts": 0, "outcome": "", "errorCategory": "", "guidanceCode": "",
            "channels": [],
        }

    def update_attempts(self, run_id, attempts):
        self.calls.append(("attempts", run_id, attempts))
        self.value["attempts"] = attempts

    def complete_run(self, run_id, **values):
        self.calls.append(("complete", run_id, values))
        self.value.update({
            "state": "completed", "completedAt": values["completed_at"],
            "attempts": values["attempts"], "outcome": values["outcome"],
            "errorCategory": values["error_category"], "guidanceCode": values["guidance_code"],
            "channels": values["channels"],
        })

    def latest_status(self, *, current_run_id=""):
        if self.fail:
            raise RuntimeError("database contained password=secret")
        if self.value is None:
            return None
        value = dict(self.value)
        if value["state"] == "running" and value["runId"] != current_run_id:
            value["state"] = "interrupted"
        return value


class FakeBootstrap:
    def __init__(self, result=None):
        self.result = result or {
            "outcome": "success", "attempts": 2, "errorCategory": "", "channels": CHANNELS,
        }
        self.calls = 0
        self.attempt_observer = lambda _attempts: None

    def run(self):
        self.calls += 1
        self.attempt_observer(1)
        self.attempt_observer(2)
        return self.result


class FakeThread:
    created = []

    def __init__(self, *, target, name, daemon):
        self.target, self.name, self.daemon = target, name, daemon
        self.started = False
        self.__class__.created.append(self)

    def start(self):
        self.started = True


def completed_timeout():
    return {
        "runId": "old", "trigger": "startup", "mode": "create-missing",
        "state": "completed", "startedAt": "2026-07-23T01:00:00+00:00",
        "completedAt": "2026-07-23T01:00:10+00:00", "attempts": 3,
        "outcome": "timeout", "errorCategory": "connection",
        "guidanceCode": "verify-oie-readiness", "channels": CHANNELS,
    }


class OieBootstrapCoordinatorTests(unittest.TestCase):
    def setUp(self):
        FakeThread.created = []

    def coordinator(self, repository=None, bootstrap=None, mode="create-missing"):
        return OieBootstrapCoordinator(
            bootstrap or FakeBootstrap(),
            repository or FakeRepository(),
            mode=mode,
            thread_factory=FakeThread,
            timestamp_factory=lambda: "2026-07-23T02:00:00+00:00",
            run_id_factory=lambda: "run-1",
        )

    def test_startup_records_running_attempts_and_completion(self):
        repository = FakeRepository()
        bootstrap = FakeBootstrap()
        coordinator = self.coordinator(repository, bootstrap)

        thread = coordinator.start_startup()
        running = coordinator.status()

        self.assertTrue(thread.started)
        self.assertEqual(("running", False), (running["state"], running["retryEligible"]))
        self.assertEqual(0, bootstrap.calls)

        thread.target()
        completed = coordinator.status()
        self.assertEqual(("completed", "success", 2), (
            completed["state"], completed["outcome"], completed["attempts"],
        ))
        self.assertEqual(1, bootstrap.calls)
        self.assertEqual([1, 2], [
            call[2] for call in repository.calls if call[0] == "attempts"
        ])

    def test_only_one_worker_can_run(self):
        coordinator = self.coordinator()
        coordinator.start_startup()

        with self.assertRaises(BootstrapCommandError) as raised:
            coordinator.start_startup()

        self.assertEqual("already-running", raised.exception.category)
        self.assertEqual(1, len(FakeThread.created))

    def test_retry_requires_allowlisted_recoverable_status(self):
        recoverable = self.coordinator(FakeRepository(completed_timeout()))

        result = recoverable.retry()

        self.assertTrue(result["accepted"])
        self.assertEqual("retry", result["trigger"])
        self.assertEqual("running", result["state"])

        blocked_value = completed_timeout()
        blocked_value.update(
            outcome="success", errorCategory="",
            channels=[
                {**CHANNELS[0], "classification": "drifted", "outcome": "blocked"},
                CHANNELS[1],
            ],
        )
        blocked = self.coordinator(FakeRepository(blocked_value))
        with self.assertRaises(BootstrapCommandError) as raised:
            blocked.retry()
        self.assertEqual("retry-not-eligible", raised.exception.category)

    def test_disabled_and_unavailable_status_never_start_worker(self):
        disabled = self.coordinator(mode="off")
        self.assertEqual(("disabled", False), (
            disabled.status()["state"], disabled.status()["retryEligible"],
        ))
        with self.assertRaises(BootstrapCommandError):
            disabled.retry()

        unavailable = self.coordinator(FakeRepository(fail=True))
        status = unavailable.status()
        self.assertEqual(("unavailable", "status-unavailable"), (
            status["state"], status["errorCategory"],
        ))
        self.assertNotIn("secret", repr(status))
        self.assertEqual([], FakeThread.created)

    def test_status_read_never_invokes_bootstrap(self):
        bootstrap = FakeBootstrap()
        coordinator = self.coordinator(FakeRepository(completed_timeout()), bootstrap)

        for _ in range(3):
            coordinator.status()

        self.assertEqual(0, bootstrap.calls)
        self.assertEqual([], FakeThread.created)


if __name__ == "__main__":
    unittest.main()
