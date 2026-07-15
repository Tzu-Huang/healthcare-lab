import json
import unittest

from backend.domain.dicom import (
    datasets_from_response_body,
    identifiers_from_dataset,
    normalize_uid_root,
    result_metadata_from_dataset,
    validate_dcm4chee_profile,
    verification_query_from_mapping,
)


def valid_profile():
    return {
        "profileName": "local-dcm4chee",
        "displayName": "Local archive",
        "environmentName": "test",
        "webUiUrl": "http://dcm4chee.test/ui",
        "dimse": {
            "host": "dcm4chee.test",
            "port": 11112,
            "calledAETitle": "DCM4CHEE",
            "callingAETitle": "HEALTHCARE_LAB",
        },
        "mwl": {
            "aeTitle": "WORKLIST",
            "defaultScheduledStationAETitle": "ECG_AP",
        },
        "hl7": {
            "host": "dcm4chee.test",
            "port": 2575,
            "sendingApplication": "HEALTHCARE_LAB",
            "sendingFacility": "LAB_APP",
            "receivingApplication": "DCM4CHEE",
            "receivingFacility": "DCM4CHEE",
            "patientAssigningAuthority": "local-dcm4chee",
        },
        "dicomweb": {
            "baseUrl": "http://dcm4chee.test/rs",
            "qidoRsUrl": "http://dcm4chee.test/rs",
            "wadoRsUrl": "http://dcm4chee.test/rs",
            "stowRsUrl": "http://dcm4chee.test/rs",
        },
        "security": {
            "authMode": "none",
            "tlsEnabled": False,
            "tlsVerify": False,
            "certificatePath": "",
            "privateKeyPath": "",
        },
    }


class DicomDomainTest(unittest.TestCase):
    def test_parses_dicom_json_and_builds_verification_query(self):
        dataset = {
            "00100020": {"vr": "LO", "Value": ["MRN-7"]},
            "00080050": {"vr": "SH", "Value": ["ACC-000007"]},
            "0020000D": {"vr": "UI", "Value": ["1.2.3"]},
            "0020000E": {"vr": "UI", "Value": ["1.2.3.1"]},
            "00080018": {"vr": "UI", "Value": ["1.2.3.1.1"]},
            "00400100": {"vr": "SQ", "Value": [{"00400009": {"vr": "SH", "Value": ["SPS-7"]}}]},
        }
        self.assertEqual(datasets_from_response_body(json.dumps([{"attrs": dataset}])), [dataset])
        self.assertEqual(identifiers_from_dataset(dataset)["scheduled_procedure_step_id"], "SPS-7")
        self.assertEqual(result_metadata_from_dataset(dataset)["series_instance_uid"], "1.2.3.1")
        self.assertEqual(
            verification_query_from_mapping({"accessionNumber": "ACC-000007", "patientId": "MRN-7"}),
            {"AccessionNumber": "ACC-000007", "PatientID": "MRN-7"},
        )

    def test_uid_root_validation_rejects_invalid_components(self):
        self.assertEqual(normalize_uid_root("1.2.840"), "1.2.840")
        with self.assertRaisesRegex(Exception, "leading zeroes"):
            normalize_uid_root("1.02.3")

    def test_complete_profile_is_healthy(self):
        result = validate_dcm4chee_profile(valid_profile())

        self.assertTrue(result["valid"])
        self.assertEqual("Healthy", result["status"])
        self.assertTrue(all(check["status"] == "Healthy" for check in result["checks"]))

    def test_invalid_ports_urls_and_tls_settings_are_reported_by_field(self):
        profile = valid_profile()
        profile["dimse"]["port"] = 0
        profile["hl7"]["port"] = "invalid"
        profile["dicomweb"]["qidoRsUrl"] = "not-a-url"
        profile["security"]["certificatePath"] = "client.pem"

        result = validate_dcm4chee_profile(profile)
        failed_fields = {
            check["field"] for check in result["checks"] if check["status"] == "Down"
        }

        self.assertFalse(result["valid"])
        self.assertEqual("Down", result["status"])
        self.assertTrue(
            {"dimse.port", "hl7.port", "dicomweb.qidoRsUrl", "security.certificatePath"}
            <= failed_fields
        )


if __name__ == "__main__":
    unittest.main()
