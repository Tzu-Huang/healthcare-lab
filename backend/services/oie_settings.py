"""OIE settings use cases independent of Flask request state."""

from __future__ import annotations

from typing import Any, Protocol


class OieSettingsRepositoryPort(Protocol):
    def get(self) -> dict[str, Any]: ...

    def update(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class OieSettingsService:
    def __init__(self, repository: OieSettingsRepositoryPort) -> None:
        self._repository = repository

    def get_profile(self) -> dict[str, Any]:
        return self._repository.get()

    def update_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._repository.update(payload)
