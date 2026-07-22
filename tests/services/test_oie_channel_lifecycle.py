import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from xml.etree import ElementTree as ET

from backend.services.oie_channel_lifecycle import LifecycleGuardError, OieManagedChannelLifecycleService, PreviewTokenCodec, merge_owned_xml
from backend.templates.oie_channels import compile_orm_to_ap


def value(channel_id="c1", revision=7, payload=None, status="STARTED"):
    payload = payload or compile_orm_to_ap("ap.internal")
    root = ET.fromstring(payload); root.find("id").text = channel_id; root.find("revision").text = str(revision)
    payload = ET.tostring(root, encoding="unicode")
    return {"id": channel_id, "name": "HLAB_ORM_TO_AP", "revision": revision, "payload": payload, "status": status}


class FakeRepository:
    def __init__(self, mapped=True, fail_audit_after=None):
        self.mapping = {"logicalType": "hlab-orm-to-ap", "channelId": "c1" if mapped else "", "channelName": "HLAB_ORM_TO_AP", "templateVersion": "1", "lastKnownRevision": "7" if mapped else ""}
        self.audits, self.fail_audit_after = [], fail_audit_after
    def get(self): return {"managedChannels": [self.mapping]}
    def compare_and_update_managed_channel_mapping(self, **kwargs):
        self.mapping.update(channelId=kwargs["channel_id"], lastKnownRevision=kwargs["revision"]); self.audits.append(kwargs["audit_event"]); return self.mapping
    def compare_and_clear_managed_channel_mapping(self, **kwargs):
        self.mapping.update(channelId="", lastKnownRevision=""); self.audits.append(kwargs["audit_event"]); return self.mapping
    def append_managed_channel_lifecycle_audit(self, event):
        if self.fail_audit_after is not None and len(self.audits) >= self.fail_audit_after: raise RuntimeError("audit unavailable")
        self.audits.append(event)
    def list_managed_channel_lifecycle_audits(self): return list(reversed(self.audits))


class FakeClient:
    def __init__(self, channels=(), fail_delete=False, fail_deploy=False): self.channels, self.calls, self.fail_delete, self.fail_deploy, self.closed = list(channels), [], fail_delete, fail_deploy, False
    def close(self): self.closed = True
    def list_channels(self): return SimpleNamespace(values={"items": tuple(self.channels)})
    def get_channel(self, channel_id): self.calls.append(("get", channel_id)); return SimpleNamespace(values=next(v for v in self.channels if v["id"] == channel_id))
    def get_channel_complete(self, channel_id):
        self.calls.append(("get-complete", channel_id)); item = next(v for v in self.channels if v["id"] == channel_id)
        return SimpleNamespace(identifier=item["id"], name=item["name"], revision=item["revision"], payload=item["payload"], status=item["status"])
    def create_channel(self, payload): self.calls.append(("create", payload)); self.channels.append(value())
    def update_channel(self, channel_id, payload, *, override=False): self.calls.append(("update", channel_id, payload, override)); self.channels[0] = value(revision=8, payload=payload)
    def deploy(self, channel_id):
        self.calls.append(("deploy", channel_id))
        if self.fail_deploy:
            from backend.domain.oie_management import OieErrorCategory, OieManagementError
            raise OieManagementError(OieErrorCategory.SERVER, "deploy failed")
    def undeploy(self, channel_id): self.calls.append(("undeploy", channel_id))
    def channel_status(self, channel_id): self.calls.append(("status", channel_id)); return SimpleNamespace(status="STARTED")
    def delete_channel(self, channel_id):
        self.calls.append(("delete", channel_id))
        if self.fail_delete:
            from backend.domain.oie_management import OieErrorCategory, OieManagementError
            raise OieManagementError(OieErrorCategory.SERVER, "delete failed")
        self.channels = []


class LifecycleServiceTests(unittest.TestCase):
    def service(self, client, repository):
        now = lambda: datetime(2026, 7, 20, tzinfo=timezone.utc)
        return OieManagedChannelLifecycleService(client, repository, ap_host="ap.internal", token_codec=PreviewTokenCodec(b"x" * 32, now=now), operation_id=lambda: "op-1")

    def test_create_requires_preview_and_persists_readback(self):
        client, repository = FakeClient(), FakeRepository(mapped=False); service = self.service(client, repository)
        preview = service.preview("hlab-orm-to-ap", "create")
        result = service.execute("hlab-orm-to-ap", "create", preview["previewToken"])
        self.assertEqual("success", result["outcome"]); self.assertEqual("c1", repository.mapping["channelId"])
        self.assertEqual("create", client.calls[0][0])
        self.assertEqual("preview-create", repository.audits[0]["operation"])

    def test_bootstrap_actor_is_applied_to_preview_and_mutation_audits(self):
        client, repository = FakeClient(), FakeRepository(mapped=False)
        service = self.service(client, repository)
        preview = service.preview("hlab-orm-to-ap", "create", actor="startup-bootstrap")

        service.execute(
            "hlab-orm-to-ap", "create", preview["previewToken"], actor="startup-bootstrap"
        )

        self.assertEqual(["startup-bootstrap", "startup-bootstrap"], [
            audit["actor"] for audit in repository.audits
        ])

    def test_actor_must_be_bounded_and_non_empty(self):
        service = self.service(FakeClient(), FakeRepository(mapped=False))
        for actor in ("", "x" * 81):
            with self.subTest(actor=actor), self.assertRaises(LifecycleGuardError):
                service.preview("hlab-orm-to-ap", "create", actor=actor)

    def test_each_operation_uses_latest_client_configuration_and_closes_session(self):
        repository = FakeRepository()
        repository.connection_marker = "old"
        clients = []

        def provide_client():
            client = FakeClient([value(channel_id=repository.connection_marker)])
            clients.append((repository.connection_marker, client))
            return client

        now = lambda: datetime(2026, 7, 20, tzinfo=timezone.utc)
        service = OieManagedChannelLifecycleService(
            None, repository, ap_host="ap.internal",
            token_codec=PreviewTokenCodec(b"x" * 32, now=now),
            client_provider=provide_client,
        )

        service.inspect()
        repository.connection_marker = "new"
        service.inspect()

        self.assertEqual(["old", "new"], [marker for marker, _ in clients])
        self.assertTrue(all(client.closed for _, client in clients))

    def test_inventory_projects_latest_completed_operation_and_skips_previews(self):
        repository = FakeRepository()
        repository.audits.extend([
            {"logical_type": "hlab-orm-to-ap", "operation": "update", "outcome": "success", "created_at": "2026-07-20T10:00:00Z"},
            {"logical_type": "hlab-orm-to-ap", "operation": "preview-delete", "outcome": "previewed", "created_at": "2026-07-20T10:01:00Z"},
            {"logical_type": "hlab-orm-to-ap", "operation": "redeploy", "outcome": "partial-failure", "error_category": "server", "created_at": "2026-07-20T10:02:00Z"},
        ])

        inventory = self.service(FakeClient([value()]), repository).inspect()[0]

        self.assertEqual({
            "operation": "redeploy", "outcome": "partial-failure", "errorCategory": "server",
            "createdAt": "2026-07-20T10:02:00Z",
        }, inventory["lastOperation"])

    def test_retry_after_uncertain_create_never_creates_duplicate(self):
        client, repository = FakeClient([value()]), FakeRepository(mapped=False); service = self.service(client, repository)
        preview = service.preview("hlab-orm-to-ap", "create")
        self.assertFalse(preview["permitted"]); self.assertNotIn("previewToken", preview)
        self.assertFalse(any(call[0] == "create" for call in client.calls))

    def test_update_preserves_unowned_fields_and_never_overrides(self):
        drift = compile_orm_to_ap("ap.internal", destination_port=6672); root = ET.fromstring(drift)
        ET.SubElement(root, "operatorOwned").text = "keep"; client = FakeClient([value(payload=ET.tostring(root, encoding="unicode"))])
        service = self.service(client, FakeRepository()); preview = service.preview("hlab-orm-to-ap", "update")
        result = service.execute("hlab-orm-to-ap", "update", preview["previewToken"])
        update = next(call for call in client.calls if call[0] == "update")
        self.assertFalse(update[3]); self.assertEqual("keep", ET.fromstring(update[2]).findtext("operatorOwned")); self.assertEqual("success", result["outcome"])

    def test_persisted_desired_fields_drive_inventory_preview_and_apply_payload(self):
        client, repository = FakeClient([value()]), FakeRepository()
        repository.mapping.update(destinationPort=6672, timeoutSeconds=7, queueEnabled=False,
                                  retryCount=3, retryIntervalMs=12000)
        service = self.service(client, repository)

        inventory = service.inspect()[0]
        preview = service.preview("hlab-orm-to-ap", "update")
        result = service.execute("hlab-orm-to-ap", "update", preview["previewToken"])

        self.assertEqual("drifted", inventory["classification"])
        self.assertEqual("OIE:6600 -> ap.internal:6672", inventory["route"])
        self.assertEqual(6672, inventory["editableFields"]["destinationPort"])
        self.assertEqual("success", result["outcome"])
        updated = ET.fromstring(next(call[2] for call in client.calls if call[0] == "update"))
        self.assertEqual("6672", updated.findtext("destinationConnectors/connector/properties/remotePort"))
        self.assertEqual("7000", updated.findtext("destinationConnectors/connector/properties/sendTimeout"))

    def test_post_preview_revision_race_fails_before_update(self):
        drift = value(payload=compile_orm_to_ap("ap.internal", destination_port=6672))
        client, repository = FakeClient([drift]), FakeRepository(); service = self.service(client, repository)
        preview = service.preview("hlab-orm-to-ap", "update")
        client.channels[0] = value(revision=8, payload=drift["payload"])
        with self.assertRaises(LifecycleGuardError):
            service.execute("hlab-orm-to-ap", "update", preview["previewToken"])
        self.assertFalse(any(call[0] == "update" for call in client.calls))

    def test_post_preview_identity_race_blocks_deploy_and_delete(self):
        for operation in ("deploy", "delete"):
            with self.subTest(operation=operation):
                client, repository = FakeClient([value()]), FakeRepository(); service = self.service(client, repository)
                preview = service.preview("hlab-orm-to-ap", operation)
                root = ET.fromstring(client.channels[0]["payload"]); root.find("description").text = "Operator owned"
                client.channels[0]["payload"] = ET.tostring(root, encoding="unicode")
                with self.assertRaises(LifecycleGuardError):
                    service.execute("hlab-orm-to-ap", operation, preview["previewToken"], confirmation="HLAB_ORM_TO_AP" if operation == "delete" else "")
                self.assertFalse(any(call[0] in {"deploy", "undeploy", "delete"} for call in client.calls))

    def test_stale_preview_and_target_substitution_fail_before_mutation(self):
        client = FakeClient(); service = self.service(client, FakeRepository(mapped=False)); preview = service.preview("hlab-orm-to-ap", "create")
        with self.assertRaises(LifecycleGuardError): service.execute("hlab-oru-to-hlab", "create", preview["previewToken"])
        self.assertEqual([], client.calls)

    def test_delete_requires_exact_confirmation_and_is_bounded(self):
        client, repository = FakeClient([value()]), FakeRepository(); service = self.service(client, repository); preview = service.preview("hlab-orm-to-ap", "delete")
        with self.assertRaises(LifecycleGuardError): service.execute("hlab-orm-to-ap", "delete", preview["previewToken"], confirmation="yes")
        result = service.execute("hlab-orm-to-ap", "delete", preview["previewToken"], confirmation="HLAB_ORM_TO_AP")
        self.assertEqual(["undeploy", "delete"], [call[0] for call in client.calls if call[0] in {"undeploy", "delete"}]); self.assertEqual("success", result["outcome"])

    def test_delete_requires_exact_previewed_display_name(self):
        client, repository = FakeClient([value()]), FakeRepository(); service = self.service(client, repository)
        preview = service.preview("hlab-orm-to-ap", "delete")
        for confirmation in ("hlab-orm-to-ap", "hlab_orm_to_ap", "HLAB_ORM_TO_AP "):
            with self.subTest(confirmation=confirmation), self.assertRaises(LifecycleGuardError):
                service.execute("hlab-orm-to-ap", "delete", preview["previewToken"], confirmation=confirmation)
        self.assertFalse(any(call[0] in {"undeploy", "delete"} for call in client.calls))

    def test_deploy_is_single_target_and_audited(self):
        client, repository = FakeClient([value(status="STOPPED")]), FakeRepository(); service = self.service(client, repository); preview = service.preview("hlab-orm-to-ap", "deploy")
        result = service.execute("hlab-orm-to-ap", "deploy", preview["previewToken"])
        self.assertEqual([("deploy", "c1"), ("status", "c1")], [call for call in client.calls if call[0] in {"deploy", "status"}]); self.assertEqual("deploy", repository.audits[-1]["operation"])
        self.assertEqual("STARTED", result["status"]); self.assertEqual("unchanged", result["finalClassification"])

    def test_redeploy_is_single_target_ordered_and_audited(self):
        client, repository = FakeClient([value()]), FakeRepository(); service = self.service(client, repository)
        preview = service.preview("hlab-orm-to-ap", "redeploy")
        result = service.execute("hlab-orm-to-ap", "redeploy", preview["previewToken"])
        self.assertEqual([("undeploy", "c1"), ("deploy", "c1"), ("status", "c1")], [call for call in client.calls if call[0] in {"undeploy", "deploy", "status"}])
        self.assertEqual(["revalidate", "undeploy", "deploy", "status-readback", "audit"], [step["name"] for step in result["steps"]])
        self.assertEqual("success", result["outcome"]); self.assertEqual("redeploy", repository.audits[-1]["operation"])

    def test_redeploy_deploy_failure_is_partial_and_does_not_expand_target(self):
        client, repository = FakeClient([value()], fail_deploy=True), FakeRepository(); service = self.service(client, repository)
        preview = service.preview("hlab-orm-to-ap", "redeploy")
        result = service.execute("hlab-orm-to-ap", "redeploy", preview["previewToken"])
        self.assertEqual("partial-failure", result["outcome"]); self.assertTrue(result["requiresRefresh"])
        self.assertEqual(["revalidate", "undeploy", "deploy", "status-readback", "audit"], [step["name"] for step in result["steps"]])
        self.assertEqual(["succeeded", "succeeded", "failed", "unattempted", "succeeded"], [step["status"] for step in result["steps"]])

    def test_redeploy_requires_deployed_managed_channel(self):
        service = self.service(FakeClient([value(status="STOPPED")]), FakeRepository())
        preview = service.preview("hlab-orm-to-ap", "redeploy")
        self.assertFalse(preview["permitted"]); self.assertNotIn("previewToken", preview)

    def test_deploy_and_undeploy_return_noop_when_state_already_holds(self):
        for operation, status in (("deploy", "STARTED"), ("undeploy", "STOPPED")):
            with self.subTest(operation=operation):
                client, repository = FakeClient([value(status=status)]), FakeRepository(); service = self.service(client, repository)
                preview = service.preview("hlab-orm-to-ap", operation); result = service.execute("hlab-orm-to-ap", operation, preview["previewToken"])
                self.assertEqual("no-op", result["steps"][1]["status"])
                self.assertFalse(any(call[0] == operation for call in client.calls))

    def test_preview_audit_failure_withholds_token(self):
        service = self.service(FakeClient(), FakeRepository(mapped=False, fail_audit_after=0))
        with self.assertRaisesRegex(LifecycleGuardError, "could not be audited"):
            service.preview("hlab-orm-to-ap", "create")

    def test_deploy_audit_failure_is_partial_failure(self):
        client, repository = FakeClient([value(status="STOPPED")]), FakeRepository(fail_audit_after=1); service = self.service(client, repository)
        preview = service.preview("hlab-orm-to-ap", "deploy"); result = service.execute("hlab-orm-to-ap", "deploy", preview["previewToken"])
        self.assertEqual("partial-failure", result["outcome"])
        self.assertEqual("audit", result["steps"][-1]["name"]); self.assertEqual("failed", result["steps"][-1]["status"])

    def test_delete_reports_partial_failure_and_retry_refreshes(self):
        client, repository = FakeClient([value()], fail_delete=True), FakeRepository(); service = self.service(client, repository)
        preview = service.preview("hlab-orm-to-ap", "delete")
        result = service.execute("hlab-orm-to-ap", "delete", preview["previewToken"], confirmation="HLAB_ORM_TO_AP")
        self.assertEqual("partial-failure", result["outcome"]); self.assertTrue(result["requiresRefresh"])
        self.assertEqual(["undeploy", "delete"], [call[0] for call in client.calls if call[0] in {"undeploy", "delete"}])

    def test_force_bulk_and_redeploy_are_not_operations(self):
        service = self.service(FakeClient(), FakeRepository(mapped=False))
        for operation in ("force", "bulk", "redeploy-all"):
            with self.assertRaises(LifecycleGuardError): service.preview("hlab-orm-to-ap", operation)

    def test_merge_rejects_incomplete_current_payload(self):
        with self.assertRaises(LifecycleGuardError): merge_owned_xml("<channel><name>x</name></channel>", compile_orm_to_ap("ap.internal"))


if __name__ == "__main__": unittest.main()
