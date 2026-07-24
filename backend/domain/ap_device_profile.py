"""Immutable, value-safe contracts for AP and external-device profiles."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping

from backend.domain.integration_settings import (
    SettingsValidationIssue,
    TypedSettingsValidationError,
)

AP_PROFILE_FIELDS = frozenset(
    {"id", "name", "environment", "enabled", "isDefault", "metadata", "hl7", "gdt", "dicom"}
)
AP_METADATA_FIELDS = frozenset({"description", "manufacturer", "model", "location"})
AP_RESULT_DELIVERY_ROLES = frozenset({"none", "scu", "scp"})
AP_OBSERVATION_PROTOCOLS = frozenset({"hl7", "gdt", "dicom"})
AP_OBSERVATION_DIRECTIONS = frozenset({"inbound", "outbound"})
AP_OBSERVATION_OUTCOMES = frozenset({"succeeded", "failed", "rejected", "timed-out"})
AP_OBSERVATION_CORRELATION_FIELDS = frozenset({"traceId", "messageId", "operationId"})

_PROFILE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_ENVIRONMENT = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}$")
_HL7_IDENTITY = re.compile(r"^[^\x00-\x1f|^~\\&]{1,64}$")
_GDT_IDENTITY = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_AE_TITLE = re.compile(r"^[\x20-\x7e]{1,16}$")
_SAFE_TEXT = re.compile(r"^[^\x00-\x1f]{0,128}$")


@dataclass(frozen=True)
class APHL7Section:
    enabled: bool
    host: str
    port: int | None
    sending_application: str
    sending_facility: str
    receiving_application: str
    receiving_facility: str


@dataclass(frozen=True)
class APGDTSection:
    enabled: bool
    sender_id: str
    receiver_id: str
    bridge_profile: str


@dataclass(frozen=True)
class APDICOMSection:
    enabled: bool
    ae_title: str
    host: str
    port: int | None
    mwl_calling_ae_title: str
    scheduled_station_ae_title: str
    result_delivery_role: str


@dataclass(frozen=True)
class APDeviceProfile:
    profile_id: str
    name: str
    normalized_name: str
    environment: str
    enabled: bool
    is_default: bool
    metadata: Mapping[str, str]
    hl7: APHL7Section
    gdt: APGDTSection
    dicom: APDICOMSection


@dataclass(frozen=True)
class APDeviceObservation:
    profile_id: str
    protocol: str
    direction: str
    observed_at: datetime
    outcome_code: str
    correlation: Mapping[str, str]


def _issue(field: str, code: str, reason: str) -> SettingsValidationIssue:
    return SettingsValidationIssue(field, code, reason)


def _closed(payload: Any, field: str, allowed: frozenset[str], issues: list[SettingsValidationIssue]) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        issues.append(_issue(field, "invalid_object", f"{field} must be an object."))
        return {}
    for key in sorted(set(payload) - allowed):
        issues.append(_issue(f"{field}.{key}" if field else key, "unknown_field", "The field is not supported."))
    return payload


def _text(payload: Mapping[str, Any], key: str, field: str, issues: list[SettingsValidationIssue], *, required: bool, maximum: int = 253) -> str:
    value = payload.get(key)
    normalized = value.strip() if isinstance(value, str) else ""
    if (required and not normalized) or len(normalized) > maximum or any(ord(c) < 32 for c in normalized):
        issues.append(_issue(field, "invalid_text", f"{field} must be valid text of at most {maximum} characters."))
    return normalized


def _boolean(payload: Mapping[str, Any], key: str, field: str, issues: list[SettingsValidationIssue]) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        issues.append(_issue(field, "invalid_boolean", f"{field} must be a boolean."))
        return False
    return value


def _port(payload: Mapping[str, Any], key: str, field: str, issues: list[SettingsValidationIssue], *, required: bool) -> int | None:
    value = payload.get(key)
    if value in (None, "") and not required:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 65535:
        issues.append(_issue(field, "invalid_port", f"{field} must be an integer between 1 and 65535."))
        return None
    return value


def validate_ap_device_profile(payload: Mapping[str, Any]) -> APDeviceProfile:
    """Validate a complete profile mutation and return a normalized snapshot."""
    issues: list[SettingsValidationIssue] = []
    root = _closed(payload, "", AP_PROFILE_FIELDS, issues)
    for field in AP_PROFILE_FIELDS - set(root):
        issues.append(_issue(field, "required", f"{field} is required."))

    profile_id = _text(root, "id", "id", issues, required=True, maximum=64)
    if profile_id and not _PROFILE_ID.fullmatch(profile_id):
        issues.append(_issue("id", "invalid_profile_id", "id must use letters, digits, dots, hyphens, or underscores."))
    name = _text(root, "name", "name", issues, required=True, maximum=80)
    normalized_name = " ".join(name.split()).casefold()
    environment = _text(root, "environment", "environment", issues, required=True, maximum=32).lower()
    if environment and not _ENVIRONMENT.fullmatch(environment):
        issues.append(_issue("environment", "invalid_environment", "environment must be a normalized environment key."))
    enabled = _boolean(root, "enabled", "enabled", issues)
    is_default = _boolean(root, "isDefault", "isDefault", issues)

    metadata_raw = _closed(root.get("metadata"), "metadata", AP_METADATA_FIELDS, issues)
    metadata: dict[str, str] = {}
    for key in AP_METADATA_FIELDS:
        if key in metadata_raw:
            value = _text(metadata_raw, key, f"metadata.{key}", issues, required=False, maximum=128)
            if not _SAFE_TEXT.fullmatch(value):
                issues.append(_issue(f"metadata.{key}", "invalid_metadata", "Metadata must contain bounded non-clinical text."))
            metadata[key] = value

    hl7_raw = _closed(root.get("hl7"), "hl7", frozenset({"enabled", "host", "port", "sendingApplication", "sendingFacility", "receivingApplication", "receivingFacility"}), issues)
    hl7_enabled = _boolean(hl7_raw, "enabled", "hl7.enabled", issues)
    hl7_values = {
        key: _text(hl7_raw, key, f"hl7.{key}", issues, required=hl7_enabled, maximum=253 if key == "host" else 64)
        for key in ("host", "sendingApplication", "sendingFacility", "receivingApplication", "receivingFacility")
    }
    for key in ("sendingApplication", "sendingFacility", "receivingApplication", "receivingFacility"):
        if hl7_values[key] and not _HL7_IDENTITY.fullmatch(hl7_values[key]):
            issues.append(_issue(f"hl7.{key}", "invalid_hl7_identity", "HL7 identities must not contain encoding separators."))
    hl7 = APHL7Section(hl7_enabled, hl7_values["host"], _port(hl7_raw, "port", "hl7.port", issues, required=hl7_enabled), hl7_values["sendingApplication"], hl7_values["sendingFacility"], hl7_values["receivingApplication"], hl7_values["receivingFacility"])

    gdt_raw = _closed(root.get("gdt"), "gdt", frozenset({"enabled", "senderId", "receiverId", "bridgeProfile"}), issues)
    gdt_enabled = _boolean(gdt_raw, "enabled", "gdt.enabled", issues)
    gdt_values = {key: _text(gdt_raw, key, f"gdt.{key}", issues, required=gdt_enabled, maximum=64) for key in ("senderId", "receiverId", "bridgeProfile")}
    for key in ("senderId", "receiverId"):
        if gdt_values[key] and not _GDT_IDENTITY.fullmatch(gdt_values[key]):
            issues.append(_issue(f"gdt.{key}", "invalid_gdt_identity", "GDT identities may contain letters, digits, hyphens, or underscores."))
    gdt = APGDTSection(gdt_enabled, gdt_values["senderId"], gdt_values["receiverId"], gdt_values["bridgeProfile"])

    dicom_raw = _closed(root.get("dicom"), "dicom", frozenset({"enabled", "aeTitle", "host", "port", "mwlCallingAETitle", "scheduledStationAETitle", "resultDeliveryRole"}), issues)
    dicom_enabled = _boolean(dicom_raw, "enabled", "dicom.enabled", issues)
    role = _text(dicom_raw, "resultDeliveryRole", "dicom.resultDeliveryRole", issues, required=dicom_enabled, maximum=16).lower()
    dicom_values = {key: _text(dicom_raw, key, f"dicom.{key}", issues, required=dicom_enabled, maximum=253 if key == "host" else 16) for key in ("aeTitle", "host", "mwlCallingAETitle", "scheduledStationAETitle")}
    for key in ("aeTitle", "mwlCallingAETitle", "scheduledStationAETitle"):
        value = dicom_values[key]
        if value and (not _AE_TITLE.fullmatch(value) or "\\" in value):
            issues.append(_issue(f"dicom.{key}", "invalid_ae_title", "DICOM AE titles must be printable and at most 16 characters."))
    if role and role not in AP_RESULT_DELIVERY_ROLES:
        issues.append(_issue("dicom.resultDeliveryRole", "invalid_role", "The DICOM result-delivery role is not supported."))
    dicom = APDICOMSection(dicom_enabled, dicom_values["aeTitle"], dicom_values["host"], _port(dicom_raw, "port", "dicom.port", issues, required=dicom_enabled), dicom_values["mwlCallingAETitle"], dicom_values["scheduledStationAETitle"], role)

    if issues:
        raise TypedSettingsValidationError(issues)
    return APDeviceProfile(profile_id, " ".join(name.split()), normalized_name, environment, enabled, is_default, MappingProxyType(metadata), hl7, gdt, dicom)


def validate_ap_device_observation(payload: Mapping[str, Any]) -> APDeviceObservation:
    """Validate the deliberately small, PHI-safe last-interaction contract."""
    allowed = frozenset({"profileId", "protocol", "direction", "observedAt", "outcomeCode", "correlation"})
    issues: list[SettingsValidationIssue] = []
    root = _closed(payload, "", allowed, issues)
    for field in allowed - set(root):
        issues.append(_issue(field, "required", f"{field} is required."))
    profile_id = _text(root, "profileId", "profileId", issues, required=True, maximum=64)
    protocol = _text(root, "protocol", "protocol", issues, required=True, maximum=8).lower()
    direction = _text(root, "direction", "direction", issues, required=True, maximum=8).lower()
    outcome = _text(root, "outcomeCode", "outcomeCode", issues, required=True, maximum=32).lower()
    if protocol not in AP_OBSERVATION_PROTOCOLS:
        issues.append(_issue("protocol", "invalid_choice", "protocol is not supported."))
    if direction not in AP_OBSERVATION_DIRECTIONS:
        issues.append(_issue("direction", "invalid_choice", "direction is not supported."))
    if outcome not in AP_OBSERVATION_OUTCOMES:
        issues.append(_issue("outcomeCode", "invalid_choice", "outcomeCode is not supported."))
    raw_time = root.get("observedAt")
    try:
        observed_at = raw_time if isinstance(raw_time, datetime) else datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
        if observed_at.tzinfo is None:
            raise ValueError
        observed_at = observed_at.astimezone(timezone.utc)
    except (TypeError, ValueError):
        observed_at = datetime.min.replace(tzinfo=timezone.utc)
        issues.append(_issue("observedAt", "invalid_timestamp", "observedAt must be an offset-aware ISO timestamp."))
    correlation_raw = _closed(root.get("correlation"), "correlation", AP_OBSERVATION_CORRELATION_FIELDS, issues)
    correlation = {key: _text(correlation_raw, key, f"correlation.{key}", issues, required=False, maximum=64) for key in correlation_raw if key in AP_OBSERVATION_CORRELATION_FIELDS}
    if issues:
        raise TypedSettingsValidationError(issues)
    return APDeviceObservation(profile_id, protocol, direction, observed_at, outcome, MappingProxyType(correlation))
