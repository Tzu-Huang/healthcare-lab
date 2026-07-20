"""Guarded orchestration for Healthcare Lab-managed OIE Channels."""
from __future__ import annotations

import base64, hashlib, hmac, json, secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping
from xml.etree import ElementTree as ET

from backend.domain.oie_channel_lifecycle import ChannelClassification, LifecycleOperation, LiveChannel, ManagedChannelType, OieMappingConflictError, PersistedChannelMapping, reconcile_inventory
from backend.domain.oie_management import OieManagementError
from backend.templates.oie_channels import compile_orm_to_ap, compile_oru_to_hlab, normalized_state, normalized_state_from_payload, orm_to_ap_config, oru_to_hlab_config


class LifecycleGuardError(RuntimeError):
    def __init__(self, category: str, detail: str, *, fresh: bool = False):
        self.category, self.detail, self.requires_fresh_preview = category, detail, fresh
        super().__init__(detail)


class PreviewTokenCodec:
    def __init__(self, secret: bytes, *, ttl_seconds: int = 300, now=None):
        if len(secret) < 32: raise ValueError("Preview secret must contain at least 32 bytes.")
        self.secret, self.ttl, self.now = secret, ttl_seconds, now or (lambda: datetime.now(timezone.utc))

    def issue(self, claims: Mapping[str, Any]):
        expires = self.now() + timedelta(seconds=self.ttl)
        raw = json.dumps({**claims, "exp": int(expires.timestamp()), "nonce": secrets.token_hex(12)}, sort_keys=True, separators=(",", ":")).encode()
        body = base64.urlsafe_b64encode(raw).rstrip(b"=")
        sig = base64.urlsafe_b64encode(hmac.new(self.secret, body, hashlib.sha256).digest()).rstrip(b"=")
        return f"{body.decode()}.{sig.decode()}", expires.isoformat()

    def verify(self, token: str):
        try:
            encoded, supplied = token.split(".", 1); body = encoded.encode()
            signature = base64.urlsafe_b64decode(supplied + "=" * (-len(supplied) % 4))
            if not hmac.compare_digest(hmac.new(self.secret, body, hashlib.sha256).digest(), signature): raise ValueError
            claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            if int(claims["exp"]) < int(self.now().timestamp()): raise ValueError
            return claims
        except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise LifecycleGuardError("stale-preview", "Preview token is invalid or expired.", fresh=True) from exc


class OieManagedChannelLifecycleService:
    def __init__(self, client, repository, *, ap_host: str, token_codec: PreviewTokenCodec, operation_id=None):
        self.client, self.repository, self.ap_host, self.tokens = client, repository, ap_host, token_codec
        self.operation_id = operation_id or (lambda: secrets.token_hex(12))

    def inspect(self): return [self._project(item) for item in self._snapshots()]

    def preview(self, logical_type: str, operation: str):
        kind, action = self._types(logical_type, operation); snapshot = self._snapshot(kind)
        permitted = self._permitted(snapshot, action)
        result = {"operation": action.value, "logicalType": kind.value, "snapshot": self._project(snapshot), "permitted": permitted}
        if permitted:
            token, expiry = self.tokens.issue(self._claims(snapshot, kind, action)); result.update(previewToken=token, expiresAt=expiry)
        return result

    def execute(self, logical_type: str, operation: str, token: str, *, confirmation: str = ""):
        kind, action = self._types(logical_type, operation)
        if action is LifecycleOperation.DELETE and confirmation != kind.value:
            raise LifecycleGuardError("confirmation-mismatch", "Delete confirmation must match logical type.")
        claims, snapshot = self.tokens.verify(token), self._snapshot(kind)
        expected = self._claims(snapshot, kind, action)
        if any(claims.get(key) != value for key, value in expected.items()) or not self._permitted(snapshot, action):
            raise LifecycleGuardError("stale-preview", "Managed Channel state changed after preview.", fresh=True)
        operation_id, steps = self.operation_id(), [{"name": "revalidate", "status": "succeeded"}]
        try:
            if action is LifecycleOperation.CREATE: return self._create(kind, snapshot, operation_id, steps)
            if action is LifecycleOperation.UPDATE: return self._update(kind, snapshot, operation_id, steps)
            if action in {LifecycleOperation.DEPLOY, LifecycleOperation.UNDEPLOY}:
                getattr(self.client, action.value)(snapshot.channel_id); steps.append({"name": action.value, "status": "succeeded"})
                self.client.channel_status(snapshot.channel_id); steps.append({"name": "status-readback", "status": "succeeded"})
                self._audit(self._event(operation_id, action, kind, snapshot, "success"))
                return self._success(kind, action, operation_id, steps)
            return self._delete(kind, snapshot, operation_id, steps)
        except (OieManagementError, LifecycleGuardError, OieMappingConflictError) as exc:
            category = getattr(getattr(exc, "category", None), "value", None) or getattr(exc, "category", "failure")
            steps.append({"name": action.value, "status": "failed", "errorCategory": category})
            partial = any(s["status"] == "succeeded" and s["name"] != "revalidate" for s in steps)
            outcome = "partial-failure" if partial else "failure"
            self._audit(self._event(operation_id, action, kind, snapshot, outcome, category))
            return {"outcome": outcome, "operationId": operation_id, "operation": action.value, "logicalType": kind.value, "steps": steps, "requiresRefresh": True}

    def _create(self, kind, before, operation_id, steps):
        self.client.create_channel(self._payload(kind)); steps.append({"name": "create", "status": "succeeded"})
        created = self._created(kind); steps.append({"name": "readback", "status": "succeeded"})
        self.repository.compare_and_update_managed_channel_mapping(logical_type=kind.value, expected_channel_id="", expected_revision="", channel_id=created.channel_id or "", channel_name=created.name, template_version="1", revision=str(created.revision or ""), audit_event=self._event(operation_id, LifecycleOperation.CREATE, kind, created, "success"))
        steps.append({"name": "persist", "status": "succeeded"}); return self._success(kind, LifecycleOperation.CREATE, operation_id, steps)

    def _update(self, kind, before, operation_id, steps):
        current = self._live(self.client.get_channel(before.channel_id).values)
        self.client.update_channel(before.channel_id, merge_owned_xml(current.payload, self._payload(kind)), override=False)
        steps.append({"name": "update", "status": "succeeded"}); refreshed = self._live(self.client.get_channel(before.channel_id).values)
        self.repository.compare_and_update_managed_channel_mapping(logical_type=kind.value, expected_channel_id=before.channel_id or "", expected_revision=str(before.revision or ""), channel_id=refreshed.channel_id, channel_name=refreshed.name, template_version="1", revision=str(refreshed.revision or ""), audit_event=self._event(operation_id, LifecycleOperation.UPDATE, kind, refreshed, "success", before=before))
        steps.extend(({"name": "readback", "status": "succeeded"}, {"name": "persist", "status": "succeeded"})); return self._success(kind, LifecycleOperation.UPDATE, operation_id, steps)

    def _delete(self, kind, before, operation_id, steps):
        if before.status.upper() not in {"", "STOPPED", "UNDEPLOYED"}:
            self.client.undeploy(before.channel_id); steps.append({"name": "undeploy", "status": "succeeded"})
        self.client.delete_channel(before.channel_id); steps.append({"name": "delete", "status": "succeeded"})
        self.repository.compare_and_clear_managed_channel_mapping(logical_type=kind.value, expected_channel_id=before.channel_id or "", expected_revision=str(before.revision or ""), audit_event=self._event(operation_id, LifecycleOperation.DELETE, kind, before, "success"))
        steps.append({"name": "persist", "status": "succeeded"}); return self._success(kind, LifecycleOperation.DELETE, operation_id, steps)

    def _snapshots(self):
        if not getattr(self.client, "_authenticated", True):
            self.client.login()
        items = self.client.list_channels().values.get("items", ())
        live = [self._live(item) for item in items]
        allowed = {kind.value for kind in ManagedChannelType}; mappings = []
        for item in self.repository.get()["managedChannels"]:
            if item["logicalType"] in allowed:
                mappings.append(PersistedChannelMapping(ManagedChannelType(item["logicalType"]), item["channelId"], item["channelName"], int(item["templateVersion"] or 1), int(item["lastKnownRevision"]) if item["lastKnownRevision"] else None))
        return reconcile_inventory((orm_to_ap_config(self.ap_host), oru_to_hlab_config()), mappings, live,
                                   normalize_desired=normalized_state,
                                   normalize_payload=normalized_state_from_payload)

    def _snapshot(self, kind): return next(item for item in self._snapshots() if item.logical_type is kind)
    def _created(self, kind):
        snapshot = self._snapshot(kind)
        if snapshot.classification is ChannelClassification.CONFLICT and snapshot.channel_id and snapshot.blocking_reasons == ("unmapped-managed-marker",): return snapshot
        raise LifecycleGuardError("create-readback", "Created Channel identity could not be rediscovered.")

    @staticmethod
    def _live(value):
        payload = value.get("payload") or value.get("xml") or value.get("channelXml")
        if not isinstance(payload, str): raise LifecycleGuardError("unexpected-response", "OIE Channel payload was not complete XML.")
        return LiveChannel(str(value["id"]), str(value.get("name", "")), int(value["revision"]), payload, str(value.get("status", "")))
    def _payload(self, kind): return compile_orm_to_ap(self.ap_host) if kind is ManagedChannelType.ORM_TO_AP else compile_oru_to_hlab()
    @staticmethod
    def _types(logical_type, operation):
        try: return ManagedChannelType(logical_type), LifecycleOperation(operation)
        except ValueError as exc: raise LifecycleGuardError("validation", "Unsupported logical type or lifecycle operation.") from exc
    @staticmethod
    def _permitted(snapshot, action):
        return (action is LifecycleOperation.CREATE and snapshot.classification is ChannelClassification.MISSING) or (action is LifecycleOperation.UPDATE and snapshot.classification is ChannelClassification.DRIFTED) or (action in {LifecycleOperation.DEPLOY, LifecycleOperation.UNDEPLOY, LifecycleOperation.DELETE} and snapshot.classification in {ChannelClassification.UNCHANGED, ChannelClassification.DRIFTED})
    def _claims(self, snapshot, kind, action): return {"operation": action.value, "logicalType": kind.value, "desiredDigest": hashlib.sha256(self._payload(kind).encode()).hexdigest(), "channelId": snapshot.channel_id or "", "revision": snapshot.revision, "classification": snapshot.classification.value}
    @staticmethod
    def _project(item): return {"logicalType": item.logical_type.value if item.logical_type else None, "classification": item.classification.value, "name": item.name, "channelId": item.channel_id, "revision": item.revision, "status": item.status, "differences": [{"path": d.path, "desired": d.desired, "observed": d.observed} for d in item.differences], "blockingReasons": list(item.blocking_reasons), "permittedActions": [a.value for a in LifecycleOperation if OieManagedChannelLifecycleService._permitted(item, a)]}
    @staticmethod
    def _success(kind, action, operation_id, steps): return {"outcome": "success", "operationId": operation_id, "operation": action.value, "logicalType": kind.value, "steps": steps, "requiresRefresh": True}
    def _event(self, operation_id, action, kind, snapshot, outcome, category="", before=None):
        classification = getattr(snapshot, "classification", None) or getattr(before, "classification", ChannelClassification.UNCHANGED)
        return {"operation_id": operation_id, "actor": "local-operator", "operation": action.value, "logical_type": kind.value, "channel_id": snapshot.channel_id or "", "before_revision": str(before.revision or "") if before else "", "after_revision": str(snapshot.revision or ""), "classification": classification.value, "outcome": outcome, "error_category": category, "changed_owned_fields": [d.path for d in (before.differences if before else ())]}
    def _audit(self, event):
        try: self.repository.append_managed_channel_lifecycle_audit(event)
        except Exception: pass


OWNED_PATHS = ("name", "description", "sourceConnector/properties/listenerConnectorProperties/host", "sourceConnector/properties/listenerConnectorProperties/port", "destinationConnectors/connector/properties/remoteAddress", "destinationConnectors/connector/properties/remotePort", "destinationConnectors/connector/properties/sendTimeout", "destinationConnectors/connector/properties/responseTimeout", "destinationConnectors/connector/properties/queueOnResponseTimeout", "destinationConnectors/connector/properties/destinationConnectorProperties/queueEnabled", "destinationConnectors/connector/properties/destinationConnectorProperties/retryIntervalMillis", "destinationConnectors/connector/properties/destinationConnectorProperties/retryCount", "destinationConnectors/connector/properties/destinationConnectorProperties/queueBufferSize", "properties/initialState", "exportData/metadata/enabled")

def merge_owned_xml(current: str, desired: str) -> str:
    live, target = ET.fromstring(current), ET.fromstring(desired)
    for path in OWNED_PATHS:
        source, destination = target.find(path), live.find(path)
        if source is None or destination is None: raise LifecycleGuardError("unexpected-response", f"Channel owned field {path} is missing.")
        destination.text = source.text
    return ET.tostring(live, encoding="unicode", short_empty_elements=True)
