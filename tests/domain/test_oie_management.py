import unittest

from backend.domain.oie_management import (
    OieErrorCategory,
    OieManagementConfig,
    OieManagementError,
    OieTlsMode,
    classify_oie_version,
)


class OieManagementContractTests(unittest.TestCase):
    def test_configuration_is_normalized_immutable_and_secret_safe(self):
        config = OieManagementConfig(
            " https://oie.example.test/ ", " admin ", "password-canary",
            OieTlsMode.LOCAL_SELF_SIGNED, 2, 7,
        )

        self.assertEqual("https://oie.example.test", config.base_url)
        self.assertEqual("admin", config.username)
        self.assertNotIn("password-canary", repr(config))
        with self.assertRaises(AttributeError):
            config.base_url = "https://changed.test"

    def test_configuration_rejects_unsafe_or_unbounded_values(self):
        cases = (
            ("https://user:secret@oie.test", 1, 1),
            ("https://oie.test?token=secret", 1, 1),
            ("https://oie.test", 0, 1),
            ("https://oie.test", 1, float("inf")),
        )
        for url, connect, read in cases:
            with self.subTest(url=url, connect=connect, read=read), self.assertRaises(
                OieManagementError
            ) as raised:
                OieManagementConfig(url, "admin", "secret", connect_timeout=connect, read_timeout=read)
            self.assertEqual(OieErrorCategory.VALIDATION, raised.exception.category)
            self.assertNotIn("secret", str(raised.exception))

        for invalid_mode in ("verified", "local-self-signed", "unknown", None):
            with self.subTest(tls_mode=invalid_mode), self.assertRaises(OieManagementError) as raised:
                OieManagementConfig(
                    "https://oie.test", "admin", "secret", tls_mode=invalid_mode
                )
            self.assertEqual(OieErrorCategory.VALIDATION, raised.exception.category)

    def test_version_support_is_exact(self):
        self.assertTrue(classify_oie_version(" 4.5.2\n").supported)
        self.assertFalse(classify_oie_version("4.5.3").supported)
        with self.assertRaises(OieManagementError) as raised:
            classify_oie_version(" ")
        self.assertEqual(OieErrorCategory.UNEXPECTED_RESPONSE, raised.exception.category)

    def test_error_has_stable_secret_safe_shape(self):
        error = OieManagementError(OieErrorCategory.PERMISSION, "Access denied.", http_status=403)
        self.assertEqual("permission", error.category.value)
        self.assertEqual(403, error.http_status)
        self.assertIn("Access denied", str(error))


if __name__ == "__main__":
    unittest.main()
