"""OIE row and boundary presentation."""

from __future__ import annotations

from typing import Any

from backend.mappers.types import RowMapping


def project_settings_profile(profile: RowMapping, mappings: list[RowMapping]) -> dict[str, Any]:
    timeout = float(profile["management_api_timeout_seconds"])
    return {
        "profileName": profile["profile_name"],
        "managementApi": {"baseUrl": profile["management_api_base_url"], "username": profile["management_api_username"],
            "passwordConfigured": bool(profile["management_api_password"]),
            "tlsVerify": bool(profile["management_api_tls_verify"]),
            "timeoutSeconds": int(timeout) if timeout.is_integer() else timeout},
        "resultListener": {"host": profile["result_listener_host"], "port": profile["result_listener_port"],
            "mllpFraming": bool(profile["result_listener_mllp_framing"]),
            "autoStart": bool(profile["result_listener_auto_start"])},
        "managedChannels": [{"logicalType": item["logical_type"], "channelId": item["oie_channel_id"],
            "channelName": item["channel_name"], "templateVersion": item["template_version"],
            "lastKnownRevision": item["last_known_revision"]} for item in mappings],
        "createdAt": profile["created_at"], "updatedAt": profile["updated_at"],
    }


def project_result(row: RowMapping) -> dict[str, Any]:
    return {
        "id": row["id"], "messageControlId": row["message_control_id"], "messageType": row["message_type"],
        "patientMrn": row["patient_mrn"], "placerOrderNumber": row["placer_order_number"],
        "fillerOrderNumber": row["filler_order_number"], "matchedPatientRecordId": row["matched_patient_record_id"],
        "matchedOrderRecordId": row["matched_order_record_id"], "matchStatus": row["match_status"],
        "duplicateOfId": row["duplicate_of_id"], "parseStatus": row["parse_status"],
        "error": row["error_text"], "payload": row["payload_hl7"], "receivedAt": row["received_at"],
        "createdAt": row["created_at"], "updatedAt": row["updated_at"],
    }
