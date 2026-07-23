import unittest
from unittest.mock import Mock

from backend.clients.medplum import MedplumAuthManager
from backend.services.medplum_diagnostics import MedplumDiagnosticService


class MedplumDiagnosticServiceTest(unittest.TestCase):
    def manager(self, configured=True):
        manager = Mock(spec=MedplumAuthManager)
        manager.is_configured.return_value = configured
        manager.get_access_token.return_value = "token-canary"
        return manager

    def test_success_uses_bounded_urls_and_returns_no_resources_or_token(self):
        fhir_request = Mock(
            side_effect=[
                (200, {"resourceType": "CapabilityStatement", "secret": "metadata-canary"}),
                (200, {"resourceType": "Bundle", "entry": [{"secret": "patient-canary"}]}),
            ]
        )
        result = MedplumDiagnosticService(
            enabled=True,
            base_url="https://example.test/fhir/R4/",
            auth_manager=self.manager(),
            timeout_seconds=9,
            fhir_request=fhir_request,
        ).diagnose()

        self.assertEqual("healthy", result["state"])
        self.assertEqual(
            ["metadata", "oauth", "authenticated-read"],
            [stage["stage"] for stage in result["stages"]],
        )
        self.assertEqual(
            "https://example.test/fhir/R4/Patient?_count=1",
            fhir_request.call_args_list[1].args[0],
        )
        self.assertEqual(9, fhir_request.call_args_list[0].kwargs["timeout_seconds"])
        rendered = str(result)
        for canary in ("token-canary", "metadata-canary", "patient-canary"):
            self.assertNotIn(canary, rendered)

    def test_disabled_profile_performs_no_network_or_authentication(self):
        manager = self.manager()
        fhir_request = Mock()

        result = MedplumDiagnosticService(
            enabled=False,
            base_url="https://example.test/fhir/R4",
            auth_manager=manager,
            timeout_seconds=5,
            fhir_request=fhir_request,
        ).diagnose()

        self.assertEqual("disabled", result["state"])
        self.assertTrue(all(stage["state"] == "disabled" for stage in result["stages"]))
        manager.get_access_token.assert_not_called()
        fhir_request.assert_not_called()

    def test_missing_credentials_skips_read_but_keeps_metadata_result(self):
        fhir_request = Mock(return_value=(200, {"resourceType": "CapabilityStatement"}))

        result = MedplumDiagnosticService(
            enabled=True,
            base_url="https://example.test/fhir/R4",
            auth_manager=self.manager(configured=False),
            timeout_seconds=5,
            fhir_request=fhir_request,
        ).diagnose()

        self.assertEqual(["passed", "failed", "skipped"], [s["state"] for s in result["stages"]])
        self.assertEqual(1, fhir_request.call_count)

    def test_failures_are_value_free_and_metadata_remains_independent(self):
        manager = self.manager()
        manager.get_access_token.side_effect = RuntimeError(
            "secret-canary Authorization: Bearer token-canary response-body-canary"
        )
        fhir_request = Mock(side_effect=RuntimeError("metadata-body-canary"))

        result = MedplumDiagnosticService(
            enabled=True,
            base_url="https://example.test/fhir/R4",
            auth_manager=manager,
            timeout_seconds=5,
            fhir_request=fhir_request,
        ).diagnose()

        self.assertEqual(["failed", "failed", "skipped"], [s["state"] for s in result["stages"]])
        rendered = str(result)
        for canary in ("secret-canary", "token-canary", "response-body-canary", "metadata-body-canary"):
            self.assertNotIn(canary, rendered)


if __name__ == "__main__":
    unittest.main()
