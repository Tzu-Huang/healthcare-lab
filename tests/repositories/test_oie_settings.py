import tempfile
import unittest
from pathlib import Path

from backend.lab_store import DemoStore
from backend.repositories.oie_settings import OieSettingsRepository


class OieSettingsRepositoryTest(unittest.TestCase):
    def test_store_exposes_repository_with_seeded_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DemoStore(Path(directory) / "lab.db")

            self.assertIsInstance(store.oie_settings_repository, OieSettingsRepository)
            self.assertEqual("local-oie", store.oie_settings_repository.get()["profileName"])


if __name__ == "__main__":
    unittest.main()
