from __future__ import annotations

import unittest

from backend.services.integration_settings import MedplumEffectiveSettings
from backend.services.medplum_runtime import MedplumRuntimeProvider


class _Settings:
    def __init__(self) -> None:
        self.current = MedplumEffectiveSettings(
            base_url="http://medplum:8103/fhir/R4",
            web_ui_url="http://127.0.0.1:3000",
            client_id="client",
            client_secret="secret",
            scope="",
            token_url="",
            auth_grace_seconds=300,
            timeout_seconds=10,
            enabled=True,
        )

    def get_effective(self, profile_type):
        assert profile_type == "medplum"
        return self.current


class MedplumRuntimeProviderTests(unittest.TestCase):
    def test_reuses_manager_for_unchanged_profile_and_invalidates_on_change(self):
        settings = _Settings()
        runtime = MedplumRuntimeProvider(settings)

        first = runtime.auth_manager()
        self.assertIs(first, runtime.auth_manager())

        settings.current = MedplumEffectiveSettings(
            **{
                **settings.current.__dict__,
                "client_secret": "rotated",
            }
        )
        self.assertIsNot(first, runtime.auth_manager())

    def test_disabled_profile_has_no_effective_base_url_or_credentials(self):
        settings = _Settings()
        settings.current = MedplumEffectiveSettings(
            **{**settings.current.__dict__, "enabled": False}
        )
        runtime = MedplumRuntimeProvider(settings)

        self.assertEqual("", runtime.base_url())
        self.assertFalse(runtime.auth_manager().is_configured())


if __name__ == "__main__":
    unittest.main()
