import unittest

from backend.domain.dicom import validate_dcm4chee_profile


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
