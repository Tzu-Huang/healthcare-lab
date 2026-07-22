import unittest

from backend.domain.oie_management import OieErrorCategory, OieManagementError
from backend.services.oie_channel_bootstrap import BOOTSTRAP_ACTOR, OieManagedChannelBootstrap


def item(logical_type, classification="missing", status=""):
    return {"logicalType": logical_type, "classification": classification, "status": status}


class FakeLifecycle:
    def __init__(self, inventories, *, create_outcome="success", deploy_outcome="success", deploy_status="STARTED"):
        self.inventories = list(inventories)
        self.create_outcome = create_outcome
        self.deploy_outcome = deploy_outcome
        self.deploy_status = deploy_status
        self.calls = []

    def inspect(self):
        self.calls.append(("inspect",))
        value = self.inventories.pop(0) if len(self.inventories) > 1 else self.inventories[0]
        if isinstance(value, Exception):
            raise value
        return value

    def preview(self, logical_type, operation, *, actor):
        self.calls.append(("preview", logical_type, operation, actor))
        return {"permitted": True, "previewToken": f"{logical_type}-{operation}"}

    def execute(self, logical_type, operation, token, *, actor):
        self.calls.append(("execute", logical_type, operation, actor))
        if operation == "create":
            return {"outcome": self.create_outcome, "steps": []}
        return {"outcome": self.deploy_outcome, "status": self.deploy_status, "steps": []}


class FakeTime:
    def __init__(self):
        self.value = 0.0
        self.sleeps = []

    def clock(self):
        return self.value

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.value += seconds


class OieManagedChannelBootstrapTests(unittest.TestCase):
    def bootstrap(self, lifecycle, fake_time=None, timeout=5, interval=1):
        fake_time = fake_time or FakeTime()
        return OieManagedChannelBootstrap(
            lifecycle, timeout_seconds=timeout, retry_interval_seconds=interval,
            clock=fake_time.clock, sleeper=fake_time.sleep,
        )

    def test_clean_startup_creates_deploys_and_verifies_both_channels(self):
        lifecycle = FakeLifecycle([[
            item("hlab-orm-to-ap"), item("hlab-oru-to-hlab"),
            item(None, "external"),
        ]])

        result = self.bootstrap(lifecycle).run()

        self.assertEqual("success", result["outcome"])
        self.assertEqual(["success", "success"], [value["outcome"] for value in result["channels"]])
        mutations = [call for call in lifecycle.calls if call[0] == "execute"]
        self.assertEqual(4, len(mutations))
        self.assertTrue(all(call[3] == BOOTSTRAP_ACTOR for call in mutations))

    def test_restart_and_partial_pair_mutate_only_missing_channel(self):
        lifecycle = FakeLifecycle([[
            item("hlab-orm-to-ap", "unchanged", "STOPPED"),
            item("hlab-oru-to-hlab", "missing"),
        ]])

        result = self.bootstrap(lifecycle).run()

        self.assertEqual(["no-op", "success"], [value["outcome"] for value in result["channels"]])
        self.assertFalse(any(call[0] == "execute" and call[1] == "hlab-orm-to-ap" for call in lifecycle.calls))

    def test_delayed_readiness_retries_until_inventory_is_available(self):
        unavailable = OieManagementError(OieErrorCategory.CONNECTION, "secret upstream body")
        lifecycle = FakeLifecycle([unavailable, unavailable, [
            item("hlab-orm-to-ap", "unchanged"), item("hlab-oru-to-hlab", "unchanged"),
        ]])
        fake_time = FakeTime()

        result = self.bootstrap(lifecycle, fake_time).run()

        self.assertEqual(3, result["attempts"])
        self.assertEqual([1, 1], fake_time.sleeps)
        self.assertNotIn("secret upstream body", str(result))

    def test_timeout_is_safe_and_stops_without_mutation(self):
        unavailable = OieManagementError(OieErrorCategory.AUTHENTICATION, "password=secret")
        lifecycle = FakeLifecycle([unavailable])
        fake_time = FakeTime()

        result = self.bootstrap(lifecycle, fake_time, timeout=2, interval=1).run()

        self.assertEqual("timeout", result["outcome"])
        self.assertEqual("authentication", result["errorCategory"])
        self.assertNotIn("secret", str(result))
        self.assertFalse(any(call[0] != "inspect" for call in lifecycle.calls))

    def test_unsupported_version_is_retried_and_reported_safely(self):
        unsupported = OieManagementError(
            OieErrorCategory.UNSUPPORTED_VERSION, "server returned private details"
        )
        lifecycle = FakeLifecycle([unsupported])

        result = self.bootstrap(lifecycle, timeout=1, interval=1).run()

        self.assertEqual("timeout", result["outcome"])
        self.assertEqual("unsupported-version", result["errorCategory"])
        self.assertNotIn("private details", str(result))

    def test_drift_conflict_and_external_inventory_are_never_mutated(self):
        lifecycle = FakeLifecycle([[
            item("hlab-orm-to-ap", "drifted"), item("hlab-oru-to-hlab", "conflict"),
            {"logicalType": None, "classification": "external"},
        ]])

        result = self.bootstrap(lifecycle).run()

        self.assertEqual(["blocked", "blocked"], [value["outcome"] for value in result["channels"]])
        self.assertEqual([("inspect",)], lifecycle.calls)

    def test_create_or_deploy_failure_stops_replay_for_that_channel(self):
        for create_outcome, deploy_outcome, expected_calls in (
            ("partial-failure", "success", 1),
            ("success", "partial-failure", 2),
        ):
            with self.subTest(create=create_outcome, deploy=deploy_outcome):
                lifecycle = FakeLifecycle([[
                    item("hlab-orm-to-ap", "missing"), item("hlab-oru-to-hlab", "unchanged"),
                ]], create_outcome=create_outcome, deploy_outcome=deploy_outcome)
                result = self.bootstrap(lifecycle).run()
                executions = [call for call in lifecycle.calls if call[0] == "execute"]
                self.assertEqual(expected_calls, len(executions))
                self.assertIn(result["channels"][0]["outcome"], {"failure", "partial-failure"})


if __name__ == "__main__":
    unittest.main()
