import unittest

from backend.services.oie_settings import OieSettingsService


class FakeRepository:
    def __init__(self):
        self.profile = {"profileName": "local-oie"}
        self.updated_with = None

    def get(self):
        return self.profile

    def update(self, payload):
        self.updated_with = payload
        return {**self.profile, "updated": True}


class OieSettingsServiceTest(unittest.TestCase):
    def test_get_and_update_delegate_to_repository(self):
        repository = FakeRepository()
        service = OieSettingsService(repository)

        self.assertEqual(repository.profile, service.get_profile())
        self.assertTrue(service.update_profile({"managementApi": {}})["updated"])
        self.assertEqual({"managementApi": {}}, repository.updated_with)


if __name__ == "__main__":
    unittest.main()
