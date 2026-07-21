from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ComposePortContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compose = (ROOT / "deploy" / "docker-compose.yml").read_text(encoding="utf-8")
        cls.example = (ROOT / ".env.example").read_text(encoding="utf-8")

    def test_host_publications_have_endpoint_specific_names(self):
        self.assertIn("${OIE_AP_RESULT_INGRESS_HOST_PORT:-6661}:6661", self.compose)
        self.assertIn("${OIE_ORDER_INGRESS_HOST_PORT:-6600}:6600", self.compose)
        self.assertNotIn("${OIE_MLLP_RESULT_PORT:-6661}:6661", self.compose)
        self.assertNotIn("${OIE_MLLP_ORDER_PORT:-6600}:6600", self.compose)

    def test_hlab_listener_has_bounded_legacy_alias(self):
        self.assertIn(
            "${HLAB_RESULT_LISTENER_PORT:-${OIE_MLLP_RESULT_PORT:-6665}}",
            self.compose,
        )
        self.assertEqual(1, self.compose.count("${OIE_MLLP_RESULT_PORT"))
        self.assertIn("HLAB_RESULT_LISTENER_PORT=6665", self.example)
        self.assertIn("aliases never control an OIE host-published port", self.example)

    def test_internal_and_published_defaults_are_documented_separately(self):
        for setting in (
            "HLAB_RESULT_LISTENER_PORT=6665",
            "OIE_AP_RESULT_INGRESS_HOST_PORT=6661",
            "OIE_ORDER_INGRESS_HOST_PORT=6600",
        ):
            self.assertIn(setting, self.example)


if __name__ == "__main__":
    unittest.main()
