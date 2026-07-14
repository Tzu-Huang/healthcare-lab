import unittest

from backend.clients.dcm4chee import dcm4chee_archive_rs_base_url


class Dcm4cheeClientTest(unittest.TestCase):
    def test_archive_url_uses_called_ae_instead_of_worklist_ae(self):
        profile = {
            "dicomweb": {"baseUrl": "http://pacs.test/dcm4chee-arc/aets/WORKLIST/rs"},
            "dimse": {"calledAETitle": "DCM4CHEE"},
            "mwl": {"aeTitle": "WORKLIST"},
        }

        self.assertEqual(
            "http://pacs.test/dcm4chee-arc/aets/DCM4CHEE/rs",
            dcm4chee_archive_rs_base_url(profile),
        )


if __name__ == "__main__":
    unittest.main()
