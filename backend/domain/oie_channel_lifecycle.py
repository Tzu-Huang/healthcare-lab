"""Pure lifecycle contracts and conservative managed-Channel reconciliation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Callable, Iterable, Mapping
from xml.etree import ElementTree as ET

from backend.domain.oie_channels import ManagedChannelConfig, ManagedChannelType


class OieMappingConflictError(RuntimeError):
    """The managed mapping changed since lifecycle state was inspected."""


class ChannelClassification(StrEnum):
    MISSING = "missing"
    UNCHANGED = "unchanged"
    DRIFTED = "drifted"
    CONFLICT = "conflict"
    EXTERNAL = "external"


class LifecycleOperation(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DEPLOY = "deploy"
    UNDEPLOY = "undeploy"
    DELETE = "delete"


class OperationOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL_FAILURE = "partial-failure"


class StepStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NO_OP = "no-op"
    UNATTEMPTED = "unattempted"


@dataclass(frozen=True)
class PersistedChannelMapping:
    logical_type: ManagedChannelType
    channel_id: str = ""
    channel_name: str = ""
    template_version: int | None = None
    last_known_revision: int | None = None


@dataclass(frozen=True)
class LiveChannel:
    channel_id: str
    name: str
    revision: int | None
    payload: str
    status: str = ""


@dataclass(frozen=True)
class IdentityEvidence:
    expected_marker: str | None
    observed_marker: str | None
    mapped_channel_id: str | None
    observed_channel_id: str | None
    marker_matches: bool = False
    id_matches: bool = False
    duplicate_marker: bool = False
    name_collision: bool = False
    payload_valid: bool = True

    @property
    def owned(self) -> bool:
        return self.marker_matches and self.id_matches and self.payload_valid


@dataclass(frozen=True)
class OwnedFieldDiff:
    path: str
    desired: Any
    observed: Any


@dataclass(frozen=True)
class ChannelSnapshot:
    logical_type: ManagedChannelType | None
    classification: ChannelClassification
    name: str
    channel_id: str | None
    revision: int | None
    status: str
    identity: IdentityEvidence
    differences: tuple[OwnedFieldDiff, ...] = ()
    blocking_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreviewTokenClaims:
    operation: LifecycleOperation
    logical_type: ManagedChannelType
    desired_digest: str
    channel_id: str | None
    observed_revision: int | None
    expires_at: datetime
    nonce: str


@dataclass(frozen=True)
class LifecyclePreview:
    operation: LifecycleOperation
    snapshot: ChannelSnapshot
    token: str
    expires_at: datetime
    permitted: bool
    blocking_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class LifecycleStepResult:
    step: str
    status: StepStatus
    error_category: str | None = None


@dataclass(frozen=True)
class LifecycleResult:
    operation_id: str
    operation: LifecycleOperation
    logical_type: ManagedChannelType
    outcome: OperationOutcome
    steps: tuple[LifecycleStepResult, ...]
    final_classification: ChannelClassification | None = None


@dataclass(frozen=True)
class LifecycleAuditEvent:
    operation_id: str
    occurred_at: datetime
    actor: str
    operation: LifecycleOperation
    logical_type: ManagedChannelType
    channel_id: str | None
    before_revision: int | None
    after_revision: int | None
    classification: ChannelClassification
    outcome: OperationOutcome
    error_category: str | None = None
    changed_paths: tuple[str, ...] = field(default_factory=tuple)


def reconcile_inventory(
    desired: Iterable[ManagedChannelConfig],
    persisted: Iterable[PersistedChannelMapping],
    live_channels: Iterable[LiveChannel],
    *,
    normalize_desired: Callable[[ManagedChannelConfig], Mapping[str, Any]],
    normalize_payload: Callable[[str], Mapping[str, Any]],
) -> tuple[ChannelSnapshot, ...]:
    """Reconcile three sources of truth without adopting ambiguous Channels."""
    configs = sorted(desired, key=lambda item: item.logical_type.value)
    mappings = {item.logical_type: item for item in persisted}
    live = sorted(live_channels, key=lambda item: (item.channel_id, item.name))
    parsed = {item.channel_id: _parse_identity(item, normalize_payload) for item in live}
    associated_ids: set[str] = set()
    snapshots: list[ChannelSnapshot] = []

    for config in configs:
        mapping = mappings.get(config.logical_type)
        mapped_id = mapping.channel_id if mapping and mapping.channel_id else None
        marker_matches = [item for item in live if parsed[item.channel_id][1] == config.marker]
        name_matches = [item for item in live if item.name == config.display_name]
        mapped = next((item for item in live if item.channel_id == mapped_id), None)
        candidates = {item.channel_id: item for item in marker_matches + name_matches + ([mapped] if mapped else [])}
        associated_ids.update(candidates)

        reasons: list[str] = []
        if len(marker_matches) > 1:
            reasons.append("duplicate-managed-marker")
        if mapped_id and marker_matches and any(item.channel_id != mapped_id for item in marker_matches):
            reasons.append("mapped-id-marker-contradiction")
        if mapped is not None and parsed[mapped.channel_id][1] != config.marker:
            reasons.append("mapped-id-marker-contradiction")
        if not mapped_id and marker_matches:
            reasons.append("unmapped-managed-marker")
        if any(parsed[item.channel_id][1] != config.marker for item in name_matches):
            reasons.append("same-name-channel-is-not-owned")
        malformed = [item for item in candidates.values() if parsed[item.channel_id][0] is not None]
        if malformed:
            reasons.append("malformed-managed-candidate")

        observed = mapped or (marker_matches[0] if len(marker_matches) == 1 else None)
        evidence = IdentityEvidence(
            expected_marker=config.marker,
            observed_marker=parsed[observed.channel_id][1] if observed else None,
            mapped_channel_id=mapped_id,
            observed_channel_id=observed.channel_id if observed else None,
            marker_matches=bool(observed and parsed[observed.channel_id][1] == config.marker),
            id_matches=bool(observed and mapped_id and observed.channel_id == mapped_id),
            duplicate_marker=len(marker_matches) > 1,
            name_collision=any(parsed[item.channel_id][1] != config.marker for item in name_matches),
            payload_valid=not malformed,
        )
        if reasons:
            classification = ChannelClassification.CONFLICT
            diffs: tuple[OwnedFieldDiff, ...] = ()
        elif observed is None:
            classification = ChannelClassification.MISSING
            diffs = ()
        else:
            actual = normalize_payload(observed.payload)
            diffs = owned_field_differences(normalize_desired(config), actual)
            classification = ChannelClassification.DRIFTED if diffs else ChannelClassification.UNCHANGED
        snapshots.append(ChannelSnapshot(
            logical_type=config.logical_type,
            classification=classification,
            name=config.display_name,
            channel_id=observed.channel_id if observed else mapped_id,
            revision=observed.revision if observed else None,
            status=observed.status if observed else "",
            identity=evidence,
            differences=diffs,
            blocking_reasons=tuple(dict.fromkeys(reasons)),
        ))

    for item in live:
        if item.channel_id in associated_ids:
            continue
        error, marker = parsed[item.channel_id]
        snapshots.append(ChannelSnapshot(
            logical_type=None,
            classification=ChannelClassification.EXTERNAL,
            name=item.name,
            channel_id=item.channel_id,
            revision=item.revision,
            status=item.status,
            identity=IdentityEvidence(None, marker, None, item.channel_id, payload_valid=error is None),
            blocking_reasons=("external-channel-read-only",),
        ))
    return tuple(snapshots)


def owned_field_differences(
    desired: Mapping[str, Any], observed: Mapping[str, Any]
) -> tuple[OwnedFieldDiff, ...]:
    differences: list[OwnedFieldDiff] = []
    _diff("", desired, observed, differences)
    return tuple(differences)


def _diff(path: str, desired: Any, observed: Any, output: list[OwnedFieldDiff]) -> None:
    if isinstance(desired, Mapping) and isinstance(observed, Mapping):
        for key in sorted(set(desired) | set(observed)):
            child = f"{path}.{key}" if path else str(key)
            _diff(child, desired.get(key), observed.get(key), output)
    elif desired != observed:
        output.append(OwnedFieldDiff(path, desired, observed))


def _parse_identity(channel: LiveChannel, normalize_payload) -> tuple[str | None, str | None]:
    try:
        root = ET.fromstring(channel.payload)
        marker = root.findtext("description")
        if marker is None:
            raise ValueError("description is required")
        # Validate the complete normalized owned surface only for marker-looking payloads.
        if marker.startswith("Managed by Healthcare Lab"):
            normalize_payload(channel.payload)
        return None, marker
    except (ET.ParseError, ValueError, TypeError) as exc:
        return type(exc).__name__, None
