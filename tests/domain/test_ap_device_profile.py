import unittest

from backend.domain.ap_device_profile import (
    validate_ap_device_observation,
    validate_ap_device_profile,
)
from backend.domain.integration_settings import TypedSettingsValidationError


def valid_profile():
    return {
        "id": "ap-1",
        "name": "  Main   ECG AP ",
        "environment": "LOCAL",
        "enabled": True,
        "isDefault": True,
        "metadata": {"manufacturer": "Example", "model": "ECG-1"},
        "hl7": {
            "enabled": True, "host": "ecg-ap", "port": 6671,
            "sendingApplication": "ECG_AP", "sendingFacility": "CARDIOLOGY",
            "receivingApplication": "HLAB", "receivingFacility": "LAB",
        },
        "gdt": {
            "enabled": True, "senderId": "ECG_AP", "receiverId": "HLAB",
            "bridgeProfile": "local-gdt-bridge",
        },
        "dicom": {
            "enabled": True, "aeTitle": "ECG_AP", "host": "ecg-ap", "port": 11112,
            "mwlCallingAETitle": "ECG_AP", "scheduledStationAETitle": "ECG_AP",
            "resultDeliveryRole": "scu",
        },
    }


class APDeviceProfileTest(unittest.TestCase):
    def test_normalizes_and_returns_immutable_profile(self):
        profile = validate_ap_device_profile(valid_profile())
        self.assertEqual(profile.name, "Main ECG AP")
        self.assertEqual(profile.normalized_name, "main ecg ap")
        self.assertEqual(profile.environment, "local")
        with self.assertRaises(TypeError):
            profile.metadata["model"] = "changed"

    def test_disabled_sections_may_be_incomplete(self):
        payload = valid_profile()
        payload["hl7"] = {"enabled": False}
        payload["gdt"] = {"enabled": False}
        payload["dicom"] = {"enabled": False}
        profile = validate_ap_device_profile(payload)
        self.assertIsNone(profile.hl7.port)

    def test_enabled_sections_are_complete_and_ports_are_bounded(self):
        payload = valid_profile()
        payload["hl7"]["port"] = 70000
        payload["gdt"]["bridgeProfile"] = ""
        payload["dicom"]["aeTitle"] = "TOO_LONG_AE_TITLE_1"
        with self.assertRaises(TypedSettingsValidationError) as caught:
            validate_ap_device_profile(payload)
        fields = {issue.field for issue in caught.exception.issues}
        self.assertTrue({"hl7.port", "gdt.bridgeProfile", "dicom.aeTitle"} <= fields)

    def test_rejects_unknown_or_non_allowlisted_metadata(self):
        payload = valid_profile()
        payload["metadata"]["patientId"] = "patient-1"
        with self.assertRaises(TypedSettingsValidationError) as caught:
            validate_ap_device_profile(payload)
        self.assertIn("metadata.patientId", {issue.field for issue in caught.exception.issues})

    def test_observation_is_closed_normalized_and_immutable(self):
        observation = validate_ap_device_observation({
            "profileId": "ap-1", "protocol": "HL7", "direction": "OUTBOUND",
            "observedAt": "2026-07-24T10:00:00+08:00", "outcomeCode": "SUCCEEDED",
            "correlation": {"traceId": "trace-1"},
        })
        self.assertEqual(observation.protocol, "hl7")
        self.assertEqual(observation.observed_at.isoformat(), "2026-07-24T02:00:00+00:00")
        with self.assertRaises(TypeError):
            observation.correlation["traceId"] = "changed"

    def test_observation_rejects_payload_and_clinical_identifiers(self):
        payload = {
            "profileId": "ap-1", "protocol": "hl7", "direction": "inbound",
            "observedAt": "2026-07-24T02:00:00Z", "outcomeCode": "failed",
            "correlation": {"patientId": "secret"}, "rawPayload": "MSH|...",
        }
        with self.assertRaises(TypedSettingsValidationError) as caught:
            validate_ap_device_observation(payload)
        fields = {issue.field for issue in caught.exception.issues}
        self.assertTrue({"rawPayload", "correlation.patientId"} <= fields)


if __name__ == "__main__":
    unittest.main()
