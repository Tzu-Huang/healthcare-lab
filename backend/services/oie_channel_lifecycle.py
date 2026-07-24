"""Guarded orchestration for Healthcare Lab-managed OIE Channels."""
from __future__ import annotations

import base64, hashlib, hmac, json, secrets
from contextlib import contextmanager
from contextvars import ContextVar
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
    def __init__(self, client, repository, *, ap_host: str, token_codec: PreviewTokenCodec, operation_id=None, client_provider=None, ap_endpoint_provider=None):
        self._fixed_client, self._client_provider = client, client_provider
        self._active_client = ContextVar("oie_lifecycle_client", default=None)
        self._active_actor = ContextVar("oie_lifecycle_actor", default="local-operator")
        self.repository, self.ap_host, self.tokens = repository, ap_host, token_codec
        self._ap_endpoint_provider = ap_endpoint_provider
        self.operation_id = operation_id or (lambda: secrets.token_hex(12))

    @property
    def client(self):
        client = self._active_client.get() or self._fixed_client
        if client is None: raise RuntimeError("An OIE Management API client is required.")
        return client

    @contextmanager
    def _client_scope(self):
        if self._client_provider is None:
            yield self.client
            return
        client = self._client_provider()
        token = self._active_client.set(client)
        try:
            yield client
        finally:
            self._active_client.reset(token)
            client.close()

    @contextmanager
    def _actor_scope(self, actor):
        actor = self._actor(actor)
        token = self._active_actor.set(actor)
        try:
            yield
        finally:
            self._active_actor.reset(token)

    def inspect(self):
        with self._client_scope():
            latest = self._latest_operations()
            return [self._project_with_config(item, latest.get(item.logical_type.value) if item.logical_type else None) for item in self._snapshots()]

    def record_bootstrap_outcome(self, logical_type: str, classification: str, outcome: str, *, error_category: str = ""):
        kind = ManagedChannelType(logical_type)
        event = {
            "operation_id": self.operation_id(), "actor": "startup-bootstrap",
            "operation": "startup-bootstrap", "logical_type": kind.value,
            "channel_id": "", "before_revision": "", "after_revision": "",
            "classification": str(classification or "")[:80],
            "outcome": str(outcome or "")[:80],
            "error_category": str(error_category or "")[:80],
            "changed_owned_fields": [],
        }
        self.repository.append_managed_channel_lifecycle_audit(event)
        return event

    def recover_mapping(self, logical_type: str, *, actor: str = "startup-bootstrap"):
        """Revalidate and atomically bind one recoverable identity without OIE mutation."""
        kind = ManagedChannelType(logical_type)
        with self._actor_scope(actor), self._client_scope():
            observed = self._snapshot(kind)
            if observed.classification is not ChannelClassification.RECOVERABLE:
                raise LifecycleGuardError("recovery-blocked", "Managed Channel identity is not uniquely recoverable.", fresh=True)
            expected_mapping = next(
                item for item in self.repository.get()["managedChannels"]
                if item["logicalType"] == kind.value
            )
            refreshed = self._snapshot(kind)
            if (refreshed.classification is not ChannelClassification.RECOVERABLE
                    or refreshed.channel_id != observed.channel_id
                    or refreshed.revision != observed.revision):
                raise LifecycleGuardError("stale-recovery", "Managed Channel recovery evidence changed before binding.", fresh=True)
            operation_id = self.operation_id()
            event = {
                "operation_id": operation_id, "actor": self._active_actor.get(),
                "operation": "recover-mapping", "logical_type": kind.value,
                "channel_id": refreshed.channel_id or "", "before_revision": "",
                "after_revision": str(refreshed.revision or ""),
                "classification": ChannelClassification.RECOVERABLE.value,
                "outcome": "success", "error_category": "",
                "changed_owned_fields": [],
            }
            mapping = self.repository.compare_and_bind_recovered_managed_channel_mapping(
                logical_type=kind.value, channel_id=refreshed.channel_id or "",
                channel_name=refreshed.name, template_version="1",
                revision=str(refreshed.revision or ""),
                expected_channel_name=expected_mapping["channelName"],
                expected_template_version=expected_mapping["templateVersion"],
                expected_desired_config=expected_mapping,
                audit_event=event,
            )
            return {
                "outcome": "success", "operationId": operation_id,
                "logicalType": kind.value, "channelId": mapping["channelId"],
                "revision": mapping["lastKnownRevision"], "status": refreshed.status,
            }

    def preview(self, logical_type: str, operation: str, *, actor: str = "local-operator"):
        with self._actor_scope(actor), self._client_scope(): return self._preview(logical_type, operation)

    def _preview(self, logical_type: str, operation: str):
        kind, action = self._types(logical_type, operation); snapshot = self._snapshot(kind)
        permitted = self._permitted(snapshot, action)
        projected = self._project_with_config(snapshot)
        result = {"operation": action.value, "logicalType": kind.value, "snapshot": projected,
                  "channelName": projected["name"], "route": projected.get("route", ""),
                  "expectedSteps": list(self._expected_steps(action)), "permitted": permitted}
        if permitted:
            preview_id = self.operation_id()
            if not self._try_audit(self._preview_event(preview_id, action, kind, snapshot)):
                raise LifecycleGuardError("audit-failure", "Lifecycle preview could not be audited.")
            token, expiry = self.tokens.issue(self._claims(snapshot, kind, action)); result.update(previewToken=token, expiresAt=expiry)
        return result

    def execute(self, logical_type: str, operation: str, token: str, *, confirmation: str = "", actor: str = "local-operator"):
        with self._actor_scope(actor), self._client_scope(): return self._execute(logical_type, operation, token, confirmation=confirmation)

    def _execute(self, logical_type: str, operation: str, token: str, *, confirmation: str = ""):
        kind, action = self._types(logical_type, operation)
        claims, snapshot = self.tokens.verify(token), self._snapshot(kind)
        expected = self._claims(snapshot, kind, action)
        if any(claims.get(key) != value for key, value in expected.items()) or not self._permitted(snapshot, action):
            raise LifecycleGuardError("stale-preview", "Managed Channel state changed after preview.", fresh=True)
        if action is LifecycleOperation.DELETE and confirmation != claims["channelName"]:
            raise LifecycleGuardError("confirmation-mismatch", "Delete confirmation must match the previewed Channel name.")
        operation_id, steps = self.operation_id(), [{"name": "revalidate", "status": "succeeded"}]
        try:
            if action is LifecycleOperation.CREATE: return self._create(kind, snapshot, operation_id, steps)
            if action is LifecycleOperation.UPDATE: return self._update(kind, snapshot, operation_id, steps)
            if action is LifecycleOperation.REDEPLOY:
                return self._redeploy(kind, snapshot, operation_id, steps)
            if action in {LifecycleOperation.DEPLOY, LifecycleOperation.UNDEPLOY}:
                current = self._guard_current(snapshot, kind)
                if self._deployment_noop(current.status, action):
                    steps.append({"name": action.value, "status": "no-op"})
                    if not self._try_audit(self._event(operation_id, action, kind, snapshot, "success")):
                        steps.append({"name": "audit", "status": "failed", "errorCategory": "audit-failure"})
                        return self._result(kind, action, operation_id, "partial-failure", steps, snapshot.classification, current.status)
                    steps.append({"name": "audit", "status": "succeeded"})
                    return self._result(kind, action, operation_id, "success", steps, snapshot.classification, current.status)
                getattr(self.client, action.value)(snapshot.channel_id); steps.append({"name": action.value, "status": "succeeded"})
                status = self.client.channel_status(snapshot.channel_id).status; steps.append({"name": "status-readback", "status": "succeeded"})
                if not self._try_audit(self._event(operation_id, action, kind, snapshot, "success")):
                    steps.append({"name": "audit", "status": "failed", "errorCategory": "audit-failure"})
                    return self._result(kind, action, operation_id, "partial-failure", steps, snapshot.classification, status)
                steps.append({"name": "audit", "status": "succeeded"})
                return self._result(kind, action, operation_id, "success", steps, snapshot.classification, status)
            return self._delete(kind, snapshot, operation_id, steps)
        except (OieManagementError, LifecycleGuardError, OieMappingConflictError) as exc:
            category = getattr(getattr(exc, "category", None), "value", None) or getattr(exc, "category", "failure")
            steps.append({"name": action.value, "status": "failed", "errorCategory": category})
            partial = any(s["status"] == "succeeded" and s["name"] != "revalidate" for s in steps)
            outcome = "partial-failure" if partial else "failure"
            if not self._try_audit(self._event(operation_id, action, kind, snapshot, outcome, category)):
                steps.append({"name": "audit", "status": "failed", "errorCategory": "audit-failure"})
            self._append_unattempted(action, steps)
            return self._result(kind, action, operation_id, outcome, steps, snapshot.classification, snapshot.status)

    def _create(self, kind, before, operation_id, steps):
        self.client.create_channel(self._payload(kind)); steps.append({"name": "create", "status": "succeeded"})
        created = self._created(kind); steps.append({"name": "readback", "status": "succeeded"})
        self.repository.compare_and_update_managed_channel_mapping(logical_type=kind.value, expected_channel_id="", expected_revision="", channel_id=created.channel_id or "", channel_name=created.name, template_version="1", revision=str(created.revision or ""), audit_event=self._event(operation_id, LifecycleOperation.CREATE, kind, created, "success"))
        steps.append({"name": "persist", "status": "succeeded"}); return self._result(kind, LifecycleOperation.CREATE, operation_id, "success", steps, ChannelClassification.UNCHANGED, created.status)

    def _update(self, kind, before, operation_id, steps):
        current = self._guard_current(before, kind)
        self.client.update_channel(before.channel_id, merge_owned_xml(current.payload, self._payload(kind)), override=False)
        steps.append({"name": "update", "status": "succeeded"}); refreshed = self._live(self.client.get_channel(before.channel_id).values)
        self.repository.compare_and_update_managed_channel_mapping(logical_type=kind.value, expected_channel_id=before.channel_id or "", expected_revision=str(before.revision or ""), channel_id=refreshed.channel_id, channel_name=refreshed.name, template_version="1", revision=str(refreshed.revision or ""), audit_event=self._event(operation_id, LifecycleOperation.UPDATE, kind, refreshed, "success", before=before))
        steps.extend(({"name": "readback", "status": "succeeded"}, {"name": "persist", "status": "succeeded"})); return self._result(kind, LifecycleOperation.UPDATE, operation_id, "success", steps, ChannelClassification.UNCHANGED, refreshed.status)

    def _delete(self, kind, before, operation_id, steps):
        self._guard_current(before, kind)
        if before.status.upper() not in {"", "STOPPED", "UNDEPLOYED"}:
            self.client.undeploy(before.channel_id); steps.append({"name": "undeploy", "status": "succeeded"})
        self.client.delete_channel(before.channel_id); steps.append({"name": "delete", "status": "succeeded"})
        self.repository.compare_and_clear_managed_channel_mapping(logical_type=kind.value, expected_channel_id=before.channel_id or "", expected_revision=str(before.revision or ""), audit_event=self._event(operation_id, LifecycleOperation.DELETE, kind, before, "success"))
        steps.append({"name": "persist", "status": "succeeded"}); return self._result(kind, LifecycleOperation.DELETE, operation_id, "success", steps, ChannelClassification.MISSING, "")

    def _redeploy(self, kind, before, operation_id, steps):
        current = self._guard_current(before, kind)
        try:
            self.client.undeploy(before.channel_id)
            steps.append({"name": "undeploy", "status": "succeeded"})
            self.client.deploy(before.channel_id)
            steps.append({"name": "deploy", "status": "succeeded"})
            status = self.client.channel_status(before.channel_id).status
            steps.append({"name": "status-readback", "status": "succeeded"})
        except OieManagementError as exc:
            category = getattr(exc.category, "value", exc.category)
            failed_step = "undeploy" if not any(step["name"] == "undeploy" for step in steps) else (
                "deploy" if not any(step["name"] == "deploy" for step in steps) else "status-readback"
            )
            steps.append({"name": failed_step, "status": "failed", "errorCategory": category})
            outcome = "partial-failure" if any(step["status"] == "succeeded" and step["name"] != "revalidate" for step in steps) else "failure"
            self._append_unattempted(LifecycleOperation.REDEPLOY, steps)
            if not self._try_audit(self._event(operation_id, LifecycleOperation.REDEPLOY, kind, before, outcome, category)):
                steps.append({"name": "audit", "status": "failed", "errorCategory": "audit-failure"})
            else:
                steps.append({"name": "audit", "status": "succeeded"})
            return self._result(kind, LifecycleOperation.REDEPLOY, operation_id, outcome, steps, before.classification, current.status)
        if not self._try_audit(self._event(operation_id, LifecycleOperation.REDEPLOY, kind, before, "success")):
            steps.append({"name": "audit", "status": "failed", "errorCategory": "audit-failure"})
            return self._result(kind, LifecycleOperation.REDEPLOY, operation_id, "partial-failure", steps, before.classification, status)
        steps.append({"name": "audit", "status": "succeeded"})
        return self._result(kind, LifecycleOperation.REDEPLOY, operation_id, "success", steps, before.classification, status)

    def _snapshots(self):
        if not getattr(self.client, "_authenticated", True):
            self.client.login()
        if hasattr(self.client, "require_supported_version"):
            self.client.require_supported_version()
        items = self.client.list_channels().values.get("items", ())
        live = [self._complete(str(item["id"])) for item in items]
        allowed = {kind.value for kind in ManagedChannelType}; mappings = []
        profile_items = self.repository.get()["managedChannels"]
        for item in profile_items:
            if item["logicalType"] in allowed:
                mappings.append(PersistedChannelMapping(ManagedChannelType(item["logicalType"]), item["channelId"], item["channelName"], int(item["templateVersion"] or 1), int(item["lastKnownRevision"]) if item["lastKnownRevision"] else None))
        configs = tuple(self._config(kind, profile_items) for kind in ManagedChannelType)
        return reconcile_inventory(configs, mappings, live,
                                   normalize_desired=normalized_state,
                                   normalize_payload=normalized_state_from_payload)

    def _snapshot(self, kind): return next(item for item in self._snapshots() if item.logical_type is kind)
    def _created(self, kind):
        snapshot = self._snapshot(kind)
        if snapshot.classification is ChannelClassification.RECOVERABLE and snapshot.channel_id: return snapshot
        raise LifecycleGuardError("create-readback", "Created Channel identity could not be rediscovered.")

    @staticmethod
    def _live(value):
        payload = value.get("payload") or value.get("xml") or value.get("channelXml")
        if not isinstance(payload, str): raise LifecycleGuardError("unexpected-response", "OIE Channel payload was not complete XML.")
        return LiveChannel(str(value["id"]), str(value.get("name", "")), int(value["revision"]), payload, str(value.get("status", "")))
    def _complete(self, channel_id):
        if hasattr(self.client, "get_channel_complete"):
            item = self.client.get_channel_complete(channel_id)
            return LiveChannel(item.identifier, item.name, item.revision, item.payload, item.status)
        return self._live(self.client.get_channel(channel_id).values)
    def _guard_current(self, expected, kind):
        current = self._complete(expected.channel_id)
        try:
            state = normalized_state_from_payload(current.payload)
        except (ValueError, TypeError, ET.ParseError) as exc:
            raise LifecycleGuardError("stale-preview", "Managed Channel identity is no longer valid.", fresh=True) from exc
        desired = normalized_state(self._config(kind))
        if (current.channel_id != expected.channel_id or current.revision != expected.revision
                or state["logical_type"] != kind.value or state["marker"] != desired["marker"]):
            raise LifecycleGuardError("stale-preview", "Managed Channel identity or revision changed after preview.", fresh=True)
        return current
    def _payload(self, kind):
        config = self._config(kind)
        values = {
            "listener_host": config.listener.host,
            "listener_port": config.listener.port,
            "destination_host": config.destination.host,
            "destination_port": config.destination.port,
            "send_timeout_ms": config.send_timeout_ms,
            "response_timeout_ms": config.response_timeout_ms,
            "queue_enabled": config.queue.enabled,
            "retry_count": config.queue.retry_count,
            "retry_interval_ms": config.queue.retry_interval_ms,
        }
        if kind is ManagedChannelType.ORM_TO_AP:
            values.update(
                sending_application=config.hl7_sending_application,
                sending_facility=config.hl7_sending_facility,
                receiving_application=config.hl7_receiving_application,
                receiving_facility=config.hl7_receiving_facility,
            )
        return compile_orm_to_ap(self.ap_host, **values) if kind is ManagedChannelType.ORM_TO_AP else compile_oru_to_hlab(**values)

    def _config(self, kind, items=None):
        items = items if items is not None else self.repository.get()["managedChannels"]
        item = next((value for value in items if value.get("logicalType") == kind.value), {})
        timeout_ms = int(float(item.get("timeoutSeconds", 5)) * 1000)
        common = {
            "listener_host": str(item.get("sourceHost") or "0.0.0.0"),
            "listener_port": int(item.get("sourcePort") or (6600 if kind is ManagedChannelType.ORM_TO_AP else 6661)),
            "destination_host": str(item.get("destinationHost") or (self.ap_host if kind is ManagedChannelType.ORM_TO_AP else "lab-app")),
            "destination_port": int(item.get("destinationPort") or (6671 if kind is ManagedChannelType.ORM_TO_AP else 6665)),
            "send_timeout_ms": timeout_ms,
            "response_timeout_ms": timeout_ms,
            "queue_enabled": bool(item.get("queueEnabled", kind is ManagedChannelType.ORU_TO_HLAB)),
            "retry_count": int(item.get("retryCount", 0)),
            "retry_interval_ms": int(item.get("retryIntervalMs", 10_000)),
        }
        if kind is ManagedChannelType.ORM_TO_AP and self._ap_endpoint_provider is not None:
            endpoint = self._ap_endpoint_provider() or {}
            if endpoint.get("enabled"):
                common["destination_host"] = str(endpoint["host"])
                common["destination_port"] = int(endpoint["port"])
                common["sending_application"] = str(endpoint["sendingApplication"])
                common["sending_facility"] = str(endpoint["sendingFacility"])
                common["receiving_application"] = str(endpoint["receivingApplication"])
                common["receiving_facility"] = str(endpoint["receivingFacility"])
        return orm_to_ap_config(self.ap_host, **common) if kind is ManagedChannelType.ORM_TO_AP else oru_to_hlab_config(**common)
    @staticmethod
    def _types(logical_type, operation):
        try: return ManagedChannelType(logical_type), LifecycleOperation(operation)
        except ValueError as exc: raise LifecycleGuardError("validation", "Unsupported logical type or lifecycle operation.") from exc
    @staticmethod
    def _permitted(snapshot, action):
        managed = snapshot.classification in {ChannelClassification.UNCHANGED, ChannelClassification.DRIFTED}
        deployed = str(snapshot.status or "").upper() in {"STARTED", "DEPLOYED"}
        return (action is LifecycleOperation.CREATE and snapshot.classification is ChannelClassification.MISSING) or (action is LifecycleOperation.UPDATE and snapshot.classification is ChannelClassification.DRIFTED) or (action is LifecycleOperation.REDEPLOY and managed and deployed) or (action in {LifecycleOperation.DEPLOY, LifecycleOperation.UNDEPLOY, LifecycleOperation.DELETE} and managed)
    def _claims(self, snapshot, kind, action): return {"operation": action.value, "logicalType": kind.value, "desiredDigest": hashlib.sha256(self._payload(kind).encode()).hexdigest(), "channelId": snapshot.channel_id or "", "channelName": snapshot.name, "revision": snapshot.revision, "classification": snapshot.classification.value}
    @staticmethod
    def _project(item):
        differences = [{"path": d.path, "desired": d.desired, "observed": d.observed} for d in item.differences]
        return {"logicalType": item.logical_type.value if item.logical_type else None, "classification": item.classification.value, "name": item.name, "channelName": item.name, "channelId": item.channel_id, "revision": item.revision, "status": item.status, "differences": differences, "blockingReasons": list(item.blocking_reasons), "permittedActions": [a.value for a in LifecycleOperation if OieManagedChannelLifecycleService._permitted(item, a)]}

    def _project_with_config(self, item, last_operation=None):
        result = self._project(item)
        if item.logical_type is None:
            return result
        config = self._config(item.logical_type)
        timeout_seconds = config.send_timeout_ms / 1000
        result.update({
            "source": f"{config.listener.host}:{config.listener.port}",
            "destination": f"{config.destination.host}:{config.destination.port}",
            "route": f"OIE:{config.listener.port} -> {config.destination.host}:{config.destination.port}",
            "editableFields": {
                "sourceHost": config.listener.host,
                "sourcePort": config.listener.port,
                "destinationHost": config.destination.host,
                "destinationPort": config.destination.port,
                "timeoutSeconds": int(timeout_seconds) if timeout_seconds.is_integer() else timeout_seconds,
                "queueEnabled": config.queue.enabled,
                "retryCount": config.queue.retry_count,
                "retryIntervalMs": config.queue.retry_interval_ms,
            },
        })
        if last_operation is not None:
            result["lastOperation"] = last_operation
        return result

    def _latest_operations(self):
        latest = {}
        for audit in self.repository.list_managed_channel_lifecycle_audits():
            logical_type, operation = audit.get("logical_type"), str(audit.get("operation", ""))
            if logical_type in latest or operation.startswith("preview-"):
                continue
            latest[logical_type] = {
                "operation": operation,
                "outcome": audit.get("outcome", ""),
                "errorCategory": audit.get("error_category", ""),
                "createdAt": audit.get("created_at", ""),
            }
        return latest

    @staticmethod
    def _expected_steps(action):
        return {
            LifecycleOperation.CREATE: ("create", "readback", "persist"),
            LifecycleOperation.UPDATE: ("update", "readback", "persist"),
            LifecycleOperation.DEPLOY: ("deploy", "status-readback", "audit"),
            LifecycleOperation.REDEPLOY: ("undeploy", "deploy", "status-readback", "audit"),
            LifecycleOperation.UNDEPLOY: ("undeploy", "status-readback", "audit"),
            LifecycleOperation.DELETE: ("undeploy-if-required", "delete", "persist"),
        }[action]
    @staticmethod
    def _result(kind, action, operation_id, outcome, steps, classification, status):
        return {"outcome": outcome, "operationId": operation_id, "operation": action.value,
                "logicalType": kind.value, "steps": steps, "finalClassification": classification.value,
                "status": status, "requiresRefresh": outcome != "success"}
    def _event(self, operation_id, action, kind, snapshot, outcome, category="", before=None):
        classification = getattr(snapshot, "classification", None) or getattr(before, "classification", ChannelClassification.UNCHANGED)
        return {"operation_id": operation_id, "actor": self._active_actor.get(), "operation": action.value, "logical_type": kind.value, "channel_id": snapshot.channel_id or "", "before_revision": str(before.revision or "") if before else "", "after_revision": str(snapshot.revision or ""), "classification": classification.value, "outcome": outcome, "error_category": category, "changed_owned_fields": [d.path for d in (before.differences if before else ())]}
    def _preview_event(self, operation_id, action, kind, snapshot):
        return {"operation_id": operation_id, "actor": self._active_actor.get(), "operation": f"preview-{action.value}",
                "logical_type": kind.value, "channel_id": snapshot.channel_id or "",
                "before_revision": str(snapshot.revision or ""), "after_revision": "",
                "classification": snapshot.classification.value, "outcome": "success",
                "error_category": "", "changed_owned_fields": [d.path for d in snapshot.differences]}
    def _try_audit(self, event):
        try:
            self.repository.append_managed_channel_lifecycle_audit(event); return True
        except Exception:
            return False
    @staticmethod
    def _actor(actor):
        if not isinstance(actor, str) or not actor.strip() or len(actor.strip()) > 80:
            raise LifecycleGuardError("validation", "Lifecycle actor must be a bounded non-empty string.")
        return actor.strip()
    @staticmethod
    def _deployment_noop(status, action):
        normalized = str(status or "").upper()
        return (action is LifecycleOperation.DEPLOY and normalized in {"STARTED", "DEPLOYED"}) or (action is LifecycleOperation.UNDEPLOY and normalized in {"STOPPED", "UNDEPLOYED"})
    @staticmethod
    def _append_unattempted(action, steps):
        plans = {
            LifecycleOperation.CREATE: ("create", "readback", "persist"),
            LifecycleOperation.UPDATE: ("update", "readback", "persist"),
            LifecycleOperation.DEPLOY: ("deploy", "status-readback", "audit"),
            LifecycleOperation.REDEPLOY: ("undeploy", "deploy", "status-readback"),
            LifecycleOperation.UNDEPLOY: ("undeploy", "status-readback", "audit"),
            LifecycleOperation.DELETE: ("undeploy", "delete", "persist"),
        }
        recorded = {step["name"] for step in steps}
        steps.extend({"name": name, "status": "unattempted"} for name in plans[action] if name not in recorded)


OWNED_PATHS = ("name", "description", "sourceConnector/properties/listenerConnectorProperties/host", "sourceConnector/properties/listenerConnectorProperties/port", "destinationConnectors/connector/properties/remoteAddress", "destinationConnectors/connector/properties/remotePort", "destinationConnectors/connector/properties/sendTimeout", "destinationConnectors/connector/properties/responseTimeout", "destinationConnectors/connector/properties/queueOnResponseTimeout", "destinationConnectors/connector/properties/destinationConnectorProperties/queueEnabled", "destinationConnectors/connector/properties/destinationConnectorProperties/retryIntervalMillis", "destinationConnectors/connector/properties/destinationConnectorProperties/retryCount", "destinationConnectors/connector/properties/destinationConnectorProperties/queueBufferSize", "preprocessingScript", "properties/initialState", "exportData/metadata/enabled")

def merge_owned_xml(current: str, desired: str) -> str:
    live, target = ET.fromstring(current), ET.fromstring(desired)
    for path in OWNED_PATHS:
        source, destination = target.find(path), live.find(path)
        if source is None or destination is None: raise LifecycleGuardError("unexpected-response", f"Channel owned field {path} is missing.")
        destination.text = source.text
    return ET.tostring(live, encoding="unicode", short_empty_elements=True)
