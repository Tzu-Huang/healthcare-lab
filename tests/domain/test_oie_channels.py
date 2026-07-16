import unittest

from backend.domain.errors import ValidationError
from backend.domain.oie_channels import (
    Endpoint,
    InitialState,
    ManagedChannelConfig,
    ManagedChannelType,
    QueuePolicy,
    is_managed_description,
    validate_route_set,
)
class ManagedOieChannelDomainTests(unittest.TestCase):
    def test_accepts_private_ipv4_and_internal_dns(self):
        for host in ("192.168.30.15", "10.0.0.8", "ap-host", "ap.internal", "ap.local"):
            with self.subTest(host=host):
                self.assertEqual(host, _orm_config(host).destination.host)

    def test_rejects_unsafe_or_public_hosts_with_field_specific_error(self):
        for host in ("", " https://ap.internal", "https://ap.internal", "user@ap", "ap:6671", "ap/path", "8.8.8.8", "example.com"):
            with self.subTest(host=host):
                with self.assertRaisesRegex(ValidationError, "destination.host"):
                    _orm_config(host)

    def test_rejects_invalid_scalar_types_and_states(self):
        invalid = (
            {"listener_port": 0},
            {"destination_port": 65536},
            {"send_timeout_ms": True},
            {"response_timeout_ms": 0},
            {"enabled": "true"},
            {"initial_state": "STARTED"},
        )
        for overrides in invalid:
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                _orm_config("ap.internal", **overrides)

    def test_route_set_rejects_duplicate_listener_ports(self):
        with self.assertRaisesRegex(ValidationError, "listener.port conflict"):
            validate_route_set(
                _orm_config("ap.internal", listener_port=6661),
                _oru_config(),
            )

    def test_marker_is_independent_of_display_name_and_oie_identity(self):
        config = _orm_config("ap.internal")
        self.assertTrue(is_managed_description(config.marker, config.logical_type))
        self.assertFalse(is_managed_description("HLAB_ORM_TO_AP", config.logical_type))
        renamed = ManagedChannelConfig(
            logical_type=config.logical_type,
            display_name="operator-renamed",
            listener=config.listener,
            destination=config.destination,
        )
        self.assertEqual(config.marker, renamed.marker)

    def test_contract_repr_has_no_credentials(self):
        values = [
            Endpoint("lab-app", 6665),
            QueuePolicy(enabled=True),
            _orm_config("ap.internal"),
            ManagedChannelType.ORM_TO_AP,
            InitialState.STARTED,
        ]
        rendered = repr(values).lower()
        for secret_word in ("password", "authorization", "cookie", "username"):
            self.assertNotIn(secret_word, rendered)


def _orm_config(host, **overrides):
    values = {
        "listener_port": 6600,
        "destination_port": 6671,
        "send_timeout_ms": 5000,
        "response_timeout_ms": 5000,
        "enabled": True,
        "initial_state": InitialState.STARTED,
    }
    values.update(overrides)
    return ManagedChannelConfig(
        logical_type=ManagedChannelType.ORM_TO_AP,
        display_name="HLAB_ORM_TO_AP",
        listener=Endpoint("0.0.0.0", values["listener_port"]),
        destination=Endpoint(host, values["destination_port"]),
        send_timeout_ms=values["send_timeout_ms"],
        response_timeout_ms=values["response_timeout_ms"],
        enabled=values["enabled"],
        initial_state=values["initial_state"],
    )


def _oru_config():
    return ManagedChannelConfig(
        logical_type=ManagedChannelType.ORU_TO_HLAB,
        display_name="HLAB_ORU_TO_HLAB",
        listener=Endpoint("0.0.0.0", 6661),
        destination=Endpoint("lab-app", 6665),
        queue=QueuePolicy(enabled=True),
    )


if __name__ == "__main__":
    unittest.main()
