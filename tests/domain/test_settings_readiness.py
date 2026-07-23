from __future__ import annotations

import unittest

from backend.domain.settings_readiness import (
    ActivationImpact,
    ReadinessAssessment,
    ReadinessRegistration,
    ReadinessState,
    project_section,
)


class _Provider:
    def assess(self):
        return ReadinessAssessment(ReadinessState.READY)


class SettingsReadinessDomainTests(unittest.TestCase):
    def test_closed_values_and_projection(self):
        self.assertEqual(
            {"ready", "needs-setup", "degraded", "disabled", "restart-required"},
            {state.value for state in ReadinessState},
        )
        self.assertEqual(
            {"immediate", "application-restart", "container-recreation"},
            {impact.value for impact in ActivationImpact},
        )
        registration = ReadinessRegistration("oie", "OIE", True, _Provider())
        item = project_section(
            registration,
            ReadinessAssessment(
                ReadinessState.RESTART_REQUIRED,
                ActivationImpact.APPLICATION_RESTART,
            ),
        )
        self.assertEqual("restart-required", item["state"])
        self.assertEqual("application-restart", item["activationImpact"])
        self.assertEqual("review-activation", item["action"])

    def test_openemr_registration_is_rejected(self):
        with self.assertRaises(ValueError):
            ReadinessRegistration("openemr", "OpenEMR", False, _Provider())

