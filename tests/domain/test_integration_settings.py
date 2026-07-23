from __future__ import annotations

import unittest

from backend.domain.integration_settings import (
    SecretAction,
    TypedSettingsValidationError,
    medplum_bootstrap_candidate,
    remove_secret,
    replace_secret,
    validate_profile,
)


class IntegrationSettingsDomainTests(unittest.TestCase):
    def test_closed_registry_rejects_unknown_profile_without_echoing_payload(self):
        canary = "do-not-echo-this"
        with self.assertRaises(TypedSettingsValidationError) as caught:
            validate_profile("arbitrary", {"secret": canary})
        self.assertNotIn(canary, str(caught.exception))
        self.assertEqual("unknown_profile", caught.exception.as_dict()["fields"][0]["code"])

    def test_medplum_profile_is_typed_and_rejects_unknown_fields(self):
        with self.assertRaises(TypedSettingsValidationError) as caught:
            validate_profile(
                "medplum",
                {
                    "baseUrl": "http://medplum:8103/fhir/R4",
                    "clientId": "",
                    "scope": "",
                    "tokenUrl": "",
                    "authGraceSeconds": 300,
                    "enabled": True,
                    "arbitrary": "no",
                },
            )
        self.assertEqual("arbitrary", caught.exception.as_dict()["fields"][0]["field"])

    def test_bootstrap_candidate_uses_safe_local_default(self):
        profile = medplum_bootstrap_candidate({})
        self.assertEqual("http://medplum:8103/fhir/R4", profile.fields["baseUrl"])
        self.assertEqual(300, profile.fields["authGraceSeconds"])

    def test_secret_commands_do_not_reveal_replacement_in_repr(self):
        mutation = replace_secret("secret-canary")
        self.assertEqual(SecretAction.REPLACE, mutation.action)
        self.assertNotIn("secret-canary", repr(mutation))
        self.assertEqual(SecretAction.PRESERVE, replace_secret(" ").action)
        self.assertEqual(SecretAction.REMOVE, remove_secret().action)
