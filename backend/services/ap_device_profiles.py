"""Application services for AP/external-device profiles and safe diagnostics."""

from __future__ import annotations

import socket
from typing import Any, Callable, Mapping
from uuid import uuid4

from backend.domain.ap_device_profile import (
    APDeviceProfile,
    validate_ap_device_observation,
    validate_ap_device_profile,
)


def project_ap_profile(profile: APDeviceProfile) -> dict[str, Any]:
    return {
        "id": profile.profile_id,
        "name": profile.name,
        "environment": profile.environment,
        "enabled": profile.enabled,
        "isDefault": profile.is_default,
        "metadata": dict(profile.metadata),
        "hl7": {
            "enabled": profile.hl7.enabled,
            "host": profile.hl7.host,
            "port": profile.hl7.port,
            "sendingApplication": profile.hl7.sending_application,
            "sendingFacility": profile.hl7.sending_facility,
            "receivingApplication": profile.hl7.receiving_application,
            "receivingFacility": profile.hl7.receiving_facility,
        },
        "gdt": {
            "enabled": profile.gdt.enabled,
            "senderId": profile.gdt.sender_id,
            "receiverId": profile.gdt.receiver_id,
            "bridgeProfile": profile.gdt.bridge_profile,
        },
        "dicom": {
            "enabled": profile.dicom.enabled,
            "aeTitle": profile.dicom.ae_title,
            "host": profile.dicom.host,
            "port": profile.dicom.port,
            "mwlCallingAETitle": profile.dicom.mwl_calling_ae_title,
            "scheduledStationAETitle": profile.dicom.scheduled_station_ae_title,
            "resultDeliveryRole": profile.dicom.result_delivery_role,
        },
    }


class APDeviceProfileService:
    def __init__(
        self,
        repository,
        *,
        environment: str = "lab",
        tcp_probe: Callable[[str, int, float], bool] | None = None,
        timeout_seconds: float = 2.0,
    ) -> None:
        self.repository = repository
        self.environment = environment
        self.timeout_seconds = max(0.1, min(float(timeout_seconds), 10.0))
        self._tcp_probe = tcp_probe or self._probe_tcp

    @staticmethod
    def _probe_tcp(host: str, port: int, timeout: float) -> bool:
        with socket.create_connection((host, port), timeout=timeout):
            return True

    def list(self, environment: str | None = None) -> list[dict[str, Any]]:
        return self.repository.list(environment=environment)

    def get(self, profile_id: str) -> dict[str, Any]:
        return self.repository.get(profile_id)

    def create(self, payload: Mapping[str, Any], *, actor: str = "local-operator"):
        profile = validate_ap_device_profile(
            {**dict(payload), "id": str(payload.get("id") or uuid4())}
        )
        return self.repository.create(profile, actor=actor)

    def update(
        self, profile_id: str, payload: Mapping[str, Any], *, actor: str = "local-operator"
    ):
        candidate = {**self.repository.get(profile_id), **dict(payload), "id": profile_id}
        profile = validate_ap_device_profile(candidate)
        return self.repository.update(profile_id, profile, actor=actor)

    def select_default(self, profile_id: str, *, actor: str = "local-operator"):
        return self.repository.select_default(profile_id, actor=actor)

    def effective(self, environment: str | None = None) -> dict[str, Any] | None:
        return self.repository.get_effective(environment or self.environment)

    def protocol_projection(
        self, protocol: str, environment: str | None = None
    ) -> dict[str, Any]:
        profile = self.effective(environment)
        section = (profile or {}).get(protocol, {})
        if not profile or not profile.get("enabled") or not section.get("enabled"):
            return {"enabled": False}
        return {"profileId": profile["id"], **dict(section)}

    def diagnose(self, profile_id: str) -> dict[str, Any]:
        profile = self.get(profile_id)
        checks = []
        for protocol in ("hl7", "dicom"):
            section = profile.get(protocol, {})
            if not section.get("enabled"):
                continue
            try:
                reachable = self._tcp_probe(
                    str(section["host"]), int(section["port"]), self.timeout_seconds
                )
                state = "transport-reachable" if reachable else "unreachable"
            except (OSError, TimeoutError, ValueError):
                state = "unreachable"
            checks.append(
                {
                    "id": f"{protocol}-transport",
                    "protocol": protocol,
                    "state": state,
                    "code": state,
                }
            )
        if profile.get("gdt", {}).get("enabled"):
            checks.append(
                {
                    "id": "gdt-association",
                    "protocol": "gdt",
                    "state": "configured",
                    "code": "bridge-associated",
                }
            )
        observations = self.repository.list_observations(profile_id)
        return {
            "state": (
                "healthy"
                if checks and all(item["state"] in {"transport-reachable", "configured"} for item in checks)
                else "degraded"
            ),
            "checks": checks,
            "lastInteraction": observations[0] if observations else None,
        }

    def record_observation(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        observation = validate_ap_device_observation(payload)
        return self.repository.record_observation(observation)

    def bootstrap(self, configuration: Mapping[str, Any]) -> bool:
        if self.repository.list():
            return False
        candidate = {
            "id": "legacy-ap",
            "name": "Legacy AP",
            "environment": self.environment,
            "enabled": False,
            "isDefault": False,
            "metadata": {"description": "Imported compatibility values"},
            "hl7": {
                "enabled": False,
                "host": str(configuration.get("OIE_MANAGED_AP_HOST", "hl7tester")),
                "port": 6671,
                "sendingApplication": "",
                "sendingFacility": "",
                "receivingApplication": "",
                "receivingFacility": "",
            },
            "gdt": {
                "enabled": False,
                "senderId": str(configuration.get("GDT_BRIDGE_SENDER_ID", "")),
                "receiverId": str(configuration.get("GDT_BRIDGE_RECEIVER_ID", "")),
                "bridgeProfile": "local-gdt-bridge",
            },
            "dicom": {
                "enabled": False,
                "aeTitle": str(
                    configuration.get(
                        "DCM4CHEE_DEFAULT_SCHEDULED_STATION_AE_TITLE", "ECG_AP"
                    )
                ),
                "host": "",
                "port": None,
                "mwlCallingAETitle": str(
                    configuration.get(
                        "DCM4CHEE_DEFAULT_SCHEDULED_STATION_AE_TITLE", "ECG_AP"
                    )
                ),
                "scheduledStationAETitle": str(
                    configuration.get(
                        "DCM4CHEE_DEFAULT_SCHEDULED_STATION_AE_TITLE", "ECG_AP"
                    )
                ),
                "resultDeliveryRole": "none",
            },
        }
        self.repository.create(
            validate_ap_device_profile(candidate),
            operation="bootstrap",
        )
        return True
