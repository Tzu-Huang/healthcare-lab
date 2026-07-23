from __future__ import annotations

import json
import unittest

from backend.domain.settings_readiness import (
    ActivationImpact,
    ReadinessAssessment,
    ReadinessRegistration,
    ReadinessState,
)
from backend.services.settings_readiness import (
    SettingsReadinessRegistry,
    SettingsReadinessService,
)


class _Provider:
    def __init__(self, state, impact=ActivationImpact.IMMEDIATE):
        self._assessment = ReadinessAssessment(state, impact)

    def assess(self):
        return self._assessment


class _FailingProvider:
    def assess(self):
        raise RuntimeError("secret-canary patient-canary")


class SettingsReadinessServiceTests(unittest.TestCase):
    def test_optional_disabled_does_not_block_completion(self):
        registry = SettingsReadinessRegistry(
            (
                ReadinessRegistration(
                    "oie", "OIE", True, _Provider(ReadinessState.READY)
                ),
                ReadinessRegistration(
                    "gdt", "GDT Bridge", False, _Provider(ReadinessState.DISABLED)
                ),
            )
        )
        result = SettingsReadinessService(registry).get_readiness()
        self.assertTrue(result["complete"])
        self.assertIsNone(result["nextAction"])

    def test_every_non_ready_required_state_blocks_completion(self):
        for state in (
            ReadinessState.NEEDS_SETUP,
            ReadinessState.DEGRADED,
            ReadinessState.DISABLED,
            ReadinessState.RESTART_REQUIRED,
        ):
            with self.subTest(state=state):
                service = SettingsReadinessService(
                    SettingsReadinessRegistry(
                        (
                            ReadinessRegistration(
                                "foundation", "Deployment", True, _Provider(state)
                            ),
                        )
                    )
                )
                result = service.get_readiness()
                self.assertFalse(result["complete"])
                self.assertEqual("foundation", result["nextAction"]["sectionId"])

    def test_provider_failure_is_partial_and_value_free(self):
        service = SettingsReadinessService(
            SettingsReadinessRegistry(
                (
                    ReadinessRegistration(
                        "medplum",
                        "Medplum",
                        True,
                        _Provider(ReadinessState.READY),
                    ),
                    ReadinessRegistration("oie", "OIE", True, _FailingProvider()),
                )
            )
        )
        result = service.get_readiness()
        self.assertEqual("ready", result["sections"][0]["state"])
        self.assertEqual("degraded", result["sections"][1]["state"])
        serialized = json.dumps(result)
        self.assertNotIn("secret-canary", serialized)
        self.assertNotIn("patient-canary", serialized)

    def test_registry_rejects_duplicate_ids(self):
        registration = ReadinessRegistration(
            "oie", "OIE", True, _Provider(ReadinessState.READY)
        )
        with self.assertRaises(ValueError):
            SettingsReadinessRegistry((registration, registration))

