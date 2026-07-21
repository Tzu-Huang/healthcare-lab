import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from backend.domain.oie_management import OieErrorCategory, OieManagementError
from backend.services.oie_diagnostics import OieRuntimeDiagnosticService


NOW = datetime(2026, 7, 21, 4, 5, 6, tzinfo=timezone.utc)


class FakeClient:
    def __init__(self, *, channel="STARTED", stats=None, failure=None, live_ports=None):
        self.channel = channel
        self.stats = stats or {"availability": "available", "queued": 0, "errors": 0}
        self.failure = failure
        self.live_ports = live_ports or []

    def login(self):
        if self.failure: raise self.failure

    def close(self):
        pass

    def current_user(self):
        return SimpleNamespace(identifier="admin")

    def channel_status(self, _channel_id):
        return SimpleNamespace(status=self.channel)

    def destination_statistics(self, _channel_id):
        return SimpleNamespace(values=self.stats)

    def ports_in_use(self):
        return SimpleNamespace(values={"items": self.live_ports})


def service(client, listener=None, ports=None):
    return OieRuntimeDiagnosticService(
        lambda: client,
        lambda: listener or {"state": "running", "running": True},
        lambda: ports or {"valid": True, "conflicts": [], "expectedPorts": []},
        channel_id="oru-channel", clock=lambda: NOW,
    )


class OieRuntimeDiagnosticTests(unittest.TestCase):
    def test_partial_probe_failure_preserves_other_layers_and_redacts_error(self):
        client = FakeClient(failure=OieManagementError(OieErrorCategory.CONNECTION, "MSH|^~\\&|PATIENT password-canary"))
        report = service(client).diagnose()
        probes = {item["layer"]: item for item in report["probes"]}
        self.assertEqual("unavailable", probes["management-api"]["state"])
        self.assertEqual("healthy", probes["hlab-listener"]["state"])
        self.assertNotIn("password-canary", repr(report))
        self.assertNotIn("MSH|", repr(report))
        self.assertEqual("2026-07-21T04:05:06Z", report["observedAt"])

    def test_unavailable_statistics_are_not_reported_as_zero(self):
        report = service(FakeClient(stats={"availability": "unsupported"})).diagnose()
        delivery = next(item for item in report["probes"] if item["layer"] == "delivery-state")
        self.assertEqual(("unavailable", "unsupported"), (delivery["state"], delivery["category"]))
        self.assertNotIn("evidence", delivery)

    def test_zero_and_queued_delivery_states_are_distinct(self):
        zero = service(FakeClient(stats={"availability": "available", "queued": 0, "errors": 0})).diagnose()
        queued = service(FakeClient(stats={"availability": "available", "queued": 3, "errors": 0})).diagnose()
        zero_delivery = next(item for item in zero["probes"] if item["layer"] == "delivery-state")
        queued_delivery = next(item for item in queued["probes"] if item["layer"] == "delivery-state")
        self.assertEqual(("healthy", "available", {"queued": 0, "errors": 0}),
                         (zero_delivery["state"], zero_delivery["category"], zero_delivery["evidence"]))
        self.assertEqual(("degraded", "destination-queued", {"queued": 3, "errors": 0}),
                         (queued_delivery["state"], queued_delivery["category"], queued_delivery["evidence"]))

    def test_port_conflict_deployment_failure_listener_degradation_and_errors_are_distinct(self):
        report = service(
            FakeClient(channel="STOPPED", stats={"availability": "available", "queued": 4, "errors": 2}),
            listener={"state": "degraded", "running": False, "errorCategory": "port-conflict", "lastError": "secret"},
            ports={"valid": False, "conflicts": [6665]},
        ).diagnose()
        probes = {item["layer"]: item for item in report["probes"]}
        self.assertEqual("port-conflict", probes["hlab-listener"]["category"])
        self.assertEqual("not-deployed", probes["managed-channel"]["category"])
        self.assertEqual("port-conflict", probes["port-contract"]["category"])
        self.assertEqual({"queued": 4, "errors": 2}, probes["delivery-state"]["evidence"])
        self.assertNotIn("secret", repr(report))

    def test_live_external_owner_conflicts_with_managed_listener_port(self):
        report = service(
            FakeClient(live_ports=[{"id": "external", "name": "External", "port": "6661"}]),
            ports={
                "valid": True, "conflicts": [],
                "expectedPorts": [{"logicalType": "hlab-oru-to-hlab", "port": 6661, "channelId": "oru-channel"}],
            },
        ).diagnose()
        port_probe = next(item for item in report["probes"] if item["layer"] == "port-contract")
        self.assertEqual(("degraded", "port-conflict"), (port_probe["state"], port_probe["category"]))
        self.assertEqual({"conflictCount": 1}, port_probe["evidence"])

    def test_live_managed_owner_is_not_a_port_conflict(self):
        report = service(
            FakeClient(live_ports=[{"id": "oru-channel", "name": "Managed", "port": 6661}]),
            ports={
                "valid": True, "conflicts": [],
                "expectedPorts": [{"logicalType": "hlab-oru-to-hlab", "port": 6661, "channelId": "oru-channel"}],
            },
        ).diagnose()
        port_probe = next(item for item in report["probes"] if item["layer"] == "port-contract")
        self.assertEqual(("healthy", "valid"), (port_probe["state"], port_probe["category"]))


if __name__ == "__main__":
    unittest.main()
