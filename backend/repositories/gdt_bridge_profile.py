"""GDT-owned adapter over the shared typed-profile repository."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.domain.gdt_bridge_profile import (
    GDT_BRIDGE_PROFILE_TYPE,
    gdt_bridge_bootstrap_candidate,
    validate_gdt_bridge_profile,
)
from backend.domain.integration_settings import TypedProfile


class GdtBridgeProfileRepository:
    """Keep GDT callers independent of generic repository string identifiers."""

    def __init__(self, typed_profiles: Any) -> None:
        self._typed_profiles = typed_profiles

    def exists(self) -> bool:
        return self._typed_profiles.exists(GDT_BRIDGE_PROFILE_TYPE)

    def bootstrap_if_missing(self, configuration: Mapping[str, Any]) -> bool:
        return self._typed_profiles.create_if_missing(
            gdt_bridge_bootstrap_candidate(configuration),
            secrets={},
            bootstrap_source="legacy-environment",
        )

    def get_private(self) -> dict[str, Any]:
        return self._typed_profiles.get_private(GDT_BRIDGE_PROFILE_TYPE)

    def replace(
        self, fields: Mapping[str, Any], *, actor: str = "local-operator"
    ) -> dict[str, Any]:
        profile = validate_gdt_bridge_profile(fields)
        return self._typed_profiles.replace(
            profile, secret_mutations={}, actor=actor
        )

    @staticmethod
    def validate(fields: Mapping[str, Any]) -> TypedProfile:
        return validate_gdt_bridge_profile(fields)
