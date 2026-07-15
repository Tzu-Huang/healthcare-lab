from __future__ import annotations

import unittest

from backend.templates.dicom import build_mwl_payload, build_patient_adt_payload


class DicomTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = {
            "profileName": "local-dcm4chee",
            "mwl": {"defaultScheduledStationAETitle": "ECG_AP"},
            "hl7": {
                "sendingApplication": "HEALTHCARE_LAB", "sendingFacility": "LAB_APP",
                "receivingApplication": "DCM4CHEE", "receivingFacility": "DCM4CHEE",
                "patientAssigningAuthority": "local-dcm4chee",
            },
        }

    def test_mwl_payload_is_deterministic(self) -> None:
        order = {
            "id": 7, "requestedAt": "20260715103000", "orderCodeText": "12 Lead ECG",
            "patient": {"mrn": "MRN-7", "firstName": "Ada", "middleName": "", "lastName": "Lovelace", "dob": "18151210", "sex": "F"},
        }
        first = build_mwl_payload(order, self.profile, timestamp_factory=lambda: "20260715103000")
        second = build_mwl_payload(order, self.profile, timestamp_factory=lambda: "20990101000000")
        self.assertEqual(first, second)
        self.assertEqual(first["00080050"]["Value"], ["ACC-000007"])
        self.assertEqual(first["00400100"]["Value"][0]["00400009"]["Value"], ["SPS-000007"])
        self.assertEqual(first["0020000D"]["Value"], ["1.2.826.0.1.3680043.10.543.20260715103000.7"])

    def test_patient_adt_payload_is_deterministic(self) -> None:
        patient = {
            "id": 7,
            "patient": {"mrn": "MRN-7", "firstName": "Ada", "lastName": "Lovelace", "dob": "18151210", "sex": "F"},
            "summary": {"mrn": "MRN-7"}, "visitNumber": "VISIT-7", "patientClass": "O",
        }
        payload = build_patient_adt_payload(
            patient, self.profile, timestamp="20260715103000", timestamp_factory=lambda: "ignored"
        )
        self.assertIn("ADT^A04^ADT_A01|DCMADT20260715103000000007", payload)
        self.assertIn("PID|1||MRN-7^^^local-dcm4chee^MR||Lovelace^Ada", payload)
        self.assertTrue(payload.endswith("VISIT-7"))
