import unittest

from backend.domain.oie_management import OieManagementConfig, OieTlsMode
from backend.services.oie_settings import OieSettingsService, create_oie_management_client


class FakeRepository:
    def __init__(self):
        self.profile = {
            "profileName": "local-oie",
            "resultListener": {"host": "0.0.0.0", "port": 6665},
        }
        self.updated_with = None

    def get(self):
        return self.profile

    def update(self, payload):
        self.updated_with = payload
        return {**self.profile, "updated": True, "resultListener": payload.get("resultListener", self.profile["resultListener"])}


class OieSettingsServiceTest(unittest.TestCase):
    def test_get_and_update_delegate_to_repository(self):
        repository = FakeRepository()
        service = OieSettingsService(repository)

        self.assertEqual(repository.profile, service.get_profile())
        result = service.update_profile({"managementApi": {}})
        self.assertTrue(result.profile["updated"])
        self.assertFalse(result.runtime_reload_required)
        self.assertEqual({"managementApi": {}}, repository.updated_with)

    def test_update_reports_changed_listener_intent_without_applying_runtime(self):
        repository = FakeRepository()
        service = OieSettingsService(repository)

        result = service.update_profile({"resultListener": {"host": "127.0.0.1", "port": 7777}})

        self.assertTrue(result.runtime_reload_required)
        self.assertEqual(7777, result.profile["resultListener"]["port"])

    def test_private_settings_are_adapted_only_at_client_construction(self):
        password = "composition-password-canary"

        class Source:
            def get_management_api_configuration(self):
                return {
                    "base_url": "https://oie.example.test/",
                    "username": " operator ",
                    "password": password,
                    "tls_verify": False,
                    "timeout_seconds": 12.5,
                }

        captured = []

        def client_factory(config):
            captured.append(config)
            return object()

        client = create_oie_management_client(Source(), client_factory=client_factory)

        self.assertIsNotNone(client)
        self.assertEqual(1, len(captured))
        config = captured[0]
        self.assertIsInstance(config, OieManagementConfig)
        self.assertEqual("https://oie.example.test", config.base_url)
        self.assertEqual("operator", config.username)
        self.assertEqual(password, config.password)
        self.assertEqual(OieTlsMode.LOCAL_SELF_SIGNED, config.tls_mode)
        self.assertEqual((12.5, 12.5), (config.connect_timeout, config.read_timeout))
        self.assertNotIn(password, repr(config))

    def test_http_configuration_keeps_verified_mode_without_network_or_database(self):
        class Source:
            def get_management_api_configuration(self):
                return {
                    "base_url": "http://oie:8080",
                    "username": "admin",
                    "password": "secret",
                    "tls_verify": False,
                    "timeout_seconds": 10,
                }

        captured = []
        create_oie_management_client(Source(), client_factory=lambda config: captured.append(config))

        self.assertEqual(OieTlsMode.VERIFIED, captured[0].tls_mode)


if __name__ == "__main__":
    unittest.main()
