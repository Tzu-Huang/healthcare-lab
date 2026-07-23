from __future__ import annotations

import unittest

from backend.domain.integration_settings import (
    DCM4CHEE_FIELDS,
    DCM4CHEE_SECRET_FIELDS,
    PROFILE_FIELDS,
    PROFILE_SECRET_FIELDS,
    TypedSettingsValidationError,
    dcm4chee_bootstrap_candidate,
    validate_profile,
)


def valid_payload() -> dict:
    return {
        "enabled": True,
        "profileName": "local-dcm4chee",
        "displayName": "Local archive",
        "environmentName": "test",
        "webUiUrl": "http://127.0.0.1:8082/dcm4chee-arc/ui2",
        "dimse": {
            "host": "dcm4chee",
            "port": 11112,
            "calledAETitle": "DCM4CHEE",
            "callingAETitle": "HEALTHCARE_LAB",
        },
        "mwl": {
            "aeTitle": "WORKLIST",
            "defaultScheduledStationAETitle": "ECG_AP",
        },
        "hl7": {
            "host": "dcm4chee",
            "port": 2575,
            "sendingApplication": "HEALTHCARE_LAB",
            "sendingFacility": "LAB_APP",
            "receivingApplication": "DCM4CHEE",
            "receivingFacility": "DCM4CHEE",
            "patientAssigningAuthority": "local-dcm4chee",
        },
        "dicomweb": {
            "baseUrl": "http://dcm4chee:8080/dcm4chee-arc/aets/WORKLIST/rs",
            "qidoRsUrl": "http://dcm4chee:8080/dcm4chee-arc/aets/DCM4CHEE/rs",
            "wadoRsUrl": "http://dcm4chee:8080/dcm4chee-arc/aets/DCM4CHEE/rs",
            "stowRsUrl": "http://dcm4chee:8080/dcm4chee-arc/aets/DCM4CHEE/rs",
        },
        "viewer": {
            "studyUrlTemplate": (
                "http://127.0.0.1:8082/dcm4chee-arc/ui2/#/study/{studyInstanceUid}"
            )
        },
        "uidRoot": "1.2.826.0.1.3680043.10.543",
        "security": {
            "authMode": "none",
            "tlsEnabled": False,
            "tlsVerify": False,
            "username": "",
            "tokenUrl": "",
            "certificatePath": "",
            "privateKeyPath": "",
        },
    }


class Dcm4cheeSettingsTests(unittest.TestCase):
    def test_profile_is_closed_registered_and_canonical(self):
        profile = validate_profile("dcm4chee", valid_payload())

        self.assertEqual("dcm4chee", profile.profile_type)
        self.assertEqual("local-dcm4chee", profile.profile_name)
        self.assertEqual(DCM4CHEE_FIELDS, PROFILE_FIELDS["dcm4chee"])
        self.assertEqual(
            frozenset({"password", "token", "clientSecret"}),
            DCM4CHEE_SECRET_FIELDS,
        )
        self.assertEqual(DCM4CHEE_SECRET_FIELDS, PROFILE_SECRET_FIELDS["dcm4chee"])
        self.assertNotIn("localLabOnly", profile.fields["security"])

    def test_bootstrap_defaults_separate_browser_and_application_networks(self):
        profile = dcm4chee_bootstrap_candidate({})

        self.assertEqual(
            "http://127.0.0.1:8082/dcm4chee-arc/ui2", profile.fields["webUiUrl"]
        )
        self.assertEqual("dcm4chee", profile.fields["dimse"]["host"])
        self.assertEqual("dcm4chee", profile.fields["hl7"]["host"])
        self.assertTrue(
            profile.fields["dicomweb"]["baseUrl"].startswith("http://dcm4chee:8080/")
        )
        self.assertEqual(
            "http://dcm4chee:8080/dcm4chee-arc/aets/DCM4CHEE/rs",
            profile.fields["dicomweb"]["qidoRsUrl"],
        )

    def test_urls_ports_ae_titles_and_uid_return_stable_field_codes(self):
        payload = valid_payload()
        payload["webUiUrl"] = "javascript:bad"
        payload["dimse"]["port"] = True
        payload["dimse"]["calledAETitle"] = "X" * 17
        payload["hl7"]["port"] = 70000
        payload["dicomweb"]["qidoRsUrl"] = "/relative"
        payload["viewer"]["studyUrlTemplate"] = "https://viewer.test/study"
        payload["uidRoot"] = "1.02.3"

        with self.assertRaises(TypedSettingsValidationError) as caught:
            validate_profile("dcm4chee", payload)

        result = {
            (issue["field"], issue["code"])
            for issue in caught.exception.as_dict()["fields"]
        }
        self.assertIn(("webUiUrl", "invalid_url"), result)
        self.assertIn(("dimse.port", "invalid_port"), result)
        self.assertIn(("hl7.port", "invalid_port"), result)
        self.assertIn(("dimse.calledAETitle", "invalid_ae_title"), result)
        self.assertIn(("dicomweb.qidoRsUrl", "invalid_url"), result)
        self.assertIn(
            ("viewer.studyUrlTemplate", "missing_study_uid_placeholder"), result
        )
        self.assertIn(("uidRoot", "invalid_uid_root"), result)

    def test_nested_unknown_fields_and_hl7_separators_are_rejected(self):
        payload = valid_payload()
        payload["security"]["password"] = "must-not-be-public"
        payload["hl7"]["sendingFacility"] = "LAB|APP"

        with self.assertRaises(TypedSettingsValidationError) as caught:
            validate_profile("dcm4chee", payload)

        result = caught.exception.as_dict()["fields"]
        self.assertIn(
            {
                "field": "security.password",
                "code": "unknown_field",
                "reason": "security.password is not supported.",
            },
            result,
        )
        self.assertTrue(
            any(
                item["field"] == "hl7.sendingFacility"
                and item["code"] == "invalid_hl7_identity"
                for item in result
            )
        )
        self.assertNotIn("must-not-be-public", str(caught.exception))

    def test_tls_auth_and_mounted_reference_combinations_are_enforced(self):
        payload = valid_payload()
        payload["security"].update(
            {
                "authMode": "mtls",
                "tlsEnabled": False,
                "tlsVerify": True,
                "certificatePath": "relative/client.pem",
                "privateKeyPath": "/run/secrets/../client.key",
            }
        )

        with self.assertRaises(TypedSettingsValidationError) as caught:
            validate_profile("dcm4chee", payload)

        codes = {
            (item["field"], item["code"])
            for item in caught.exception.as_dict()["fields"]
        }
        self.assertIn(("security.tlsVerify", "requires_tls"), codes)
        self.assertIn(("security.certificatePath", "invalid_mounted_reference"), codes)
        self.assertIn(("security.privateKeyPath", "invalid_mounted_reference"), codes)
        self.assertIn(("security.authMode", "mtls_material_required"), codes)

    def test_basic_and_oauth2_require_public_auth_metadata(self):
        basic = valid_payload()
        basic["security"]["authMode"] = "basic"
        with self.assertRaises(TypedSettingsValidationError) as basic_error:
            validate_profile("dcm4chee", basic)
        self.assertTrue(
            any(
                issue.field == "security.username"
                and issue.code == "required_for_auth_mode"
                for issue in basic_error.exception.issues
            )
        )

        oauth = valid_payload()
        oauth["security"].update({"authMode": "oauth2", "username": "client-id"})
        with self.assertRaises(TypedSettingsValidationError) as oauth_error:
            validate_profile("dcm4chee", oauth)
        self.assertTrue(
            any(
                issue.field == "security.tokenUrl" and issue.code == "invalid_url"
                for issue in oauth_error.exception.issues
            )
        )

    def test_bootstrap_accepts_legacy_string_port_and_boolean_values(self):
        profile = dcm4chee_bootstrap_candidate(
            {
                "DCM4CHEE_DIMSE_PORT": "11113",
                "DCM4CHEE_HL7_PORT": "2576",
                "DCM4CHEE_TLS_ENABLED": "false",
                "DCM4CHEE_TLS_VERIFY": "false",
            }
        )
        self.assertEqual(11113, profile.fields["dimse"]["port"])
        self.assertEqual(2576, profile.fields["hl7"]["port"])
        self.assertFalse(profile.fields["security"]["tlsEnabled"])


if __name__ == "__main__":
    unittest.main()
