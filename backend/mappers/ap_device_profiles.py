"""Pure persistence mappings for AP/external-device profiles."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from backend.domain.ap_device_profile import APDeviceProfile


def profile_to_mapping(profile: Mapping[str, Any] | APDeviceProfile) -> dict[str, Any]:
    if isinstance(profile, Mapping):
        return dict(profile)
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


def profile_row(row: Any) -> dict[str, Any]:
    return {
        "id": row["profile_key"],
        "name": row["profile_name"],
        "environment": row["environment"],
        "enabled": bool(row["enabled"]),
        "isDefault": bool(row["is_default"]),
        "schemaVersion": int(row["schema_version"]),
        **json.loads(row["payload_json"]),
        "bootstrapSource": row["bootstrap_source"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }
