import tempfile
import unittest
from pathlib import Path

from backend.application_composition import assemble_application_dependencies


class APDeviceProfileServiceTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.dependencies = assemble_application_dependencies(
            Path(self.root.name) / "app.db",
            configuration={"AP_PROFILE_ENVIRONMENT": "lab"},
        )
        self.service = self.dependencies.ap_device_profile_service

    @staticmethod
    def profile(profile_id="ap-main"):
        return {
            "id": profile_id, "name": "Main AP", "environment": "lab",
            "enabled": True, "isDefault": False, "metadata": {},
            "hl7": {
                "enabled": True, "host": "ap.internal", "port": 6671,
                "sendingApplication": "ECG_AP", "sendingFacility": "CARDIOLOGY",
                "receivingApplication": "ECG_AP", "receivingFacility": "CARDIOLOGY",
            },
            "gdt": {"enabled": False},
            "dicom": {"enabled": False},
        }

    def test_effective_projection_requires_enabled_default(self):
        self.service.create(self.profile())
        self.assertEqual(self.service.protocol_projection("hl7"), {"enabled": False})
        self.service.select_default("ap-main")
        self.assertEqual(
            self.service.protocol_projection("hl7")["host"], "ap.internal"
        )

    def test_diagnostics_and_observation_are_value_safe(self):
        self.service._tcp_probe = lambda host, port, timeout: True
        self.service.create(self.profile())
        result = self.service.diagnose("ap-main")
        self.assertEqual(result["checks"][0]["state"], "transport-reachable")
        observed = self.service.record_observation(
            {
                "profileId": "ap-main", "protocol": "hl7", "direction": "outbound",
                "observedAt": "2026-07-24T00:00:00Z", "outcomeCode": "succeeded",
                "correlation": {"traceId": "trace-1"},
            }
        )
        self.assertNotIn("payload", observed)

    def test_diagnostics_preserve_partial_protocol_results(self):
        payload = self.profile("ap-partial")
        payload["dicom"] = {
            "enabled": True, "aeTitle": "ECG_AP", "host": "dicom-ap",
            "port": 11112, "mwlCallingAETitle": "ECG_AP",
            "scheduledStationAETitle": "ECG_AP", "resultDeliveryRole": "scu",
        }
        self.service.create(payload)
        self.service._tcp_probe = (
            lambda host, port, timeout: host == "ap.internal"
        )

        report = self.service.diagnose("ap-partial")

        self.assertEqual(report["state"], "degraded")
        self.assertEqual(
            [item["state"] for item in report["checks"]],
            ["transport-reachable", "unreachable"],
        )

    def test_gdt_and_dicom_consumers_share_effective_ap_snapshot(self):
        payload = self.profile("ap-protocols")
        payload["hl7"] = {"enabled": False}
        payload["gdt"] = {
            "enabled": True,
            "senderId": "ECG_AP",
            "receiverId": "HLAB",
            "bridgeProfile": "local-gdt-bridge",
        }
        payload["dicom"] = {
            "enabled": True,
            "aeTitle": "ECG_AP",
            "host": "ap.internal",
            "port": 11112,
            "mwlCallingAETitle": "ECG_AP",
            "scheduledStationAETitle": "ECG_AP",
            "resultDeliveryRole": "scu",
        }
        self.service.create(payload)
        self.service.select_default("ap-protocols")

        gdt = self.dependencies.integration_settings_service.get_effective("gdt-bridge")
        dcm = self.dependencies.integration_settings_service.get_effective("dcm4chee")

        self.assertEqual((gdt.sender_id, gdt.receiver_id), ("ECG_AP", "HLAB"))
        self.assertEqual(
            dcm.profile["mwl"]["defaultScheduledStationAETitle"], "ECG_AP"
        )


if __name__ == "__main__":
    unittest.main()
