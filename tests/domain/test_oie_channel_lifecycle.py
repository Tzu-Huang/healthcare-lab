import unittest
from xml.etree import ElementTree as ET

from backend.domain.oie_channel_lifecycle import (
    ChannelClassification,
    LiveChannel,
    PersistedChannelMapping,
    reconcile_inventory,
)
from backend.domain.oie_channels import ManagedChannelType
from backend.templates.oie_channels import compile_orm_to_ap, normalized_state, normalized_state_from_payload, orm_to_ap_config


TYPE = ManagedChannelType.ORM_TO_AP


def live(channel_id="oie-1", payload=None, name="HLAB_ORM_TO_AP"):
    payload = payload if payload is not None else compile_orm_to_ap("ap.internal")
    root = ET.fromstring(payload)
    root.find("id").text = channel_id
    root.find("revision").text = "7"
    root.find("name").text = name
    return LiveChannel(channel_id, name, 7, ET.tostring(root, encoding="unicode"), "STARTED")


def mapping(channel_id="oie-1"):
    return PersistedChannelMapping(TYPE, channel_id, "HLAB_ORM_TO_AP", 1, 7)


class ReconcileManagedChannelTests(unittest.TestCase):
    def setUp(self):
        self.desired = orm_to_ap_config("ap.internal")

    def managed(self, channels=(), mappings=()):
        return reconcile_inventory([self.desired], mappings, channels, normalize_desired=normalized_state, normalize_payload=normalized_state_from_payload)[0]

    def test_missing(self):
        self.assertEqual(ChannelClassification.MISSING, self.managed().classification)

    def test_unchanged_requires_marker_and_persisted_id(self):
        result = self.managed([live()], [mapping()])
        self.assertEqual(ChannelClassification.UNCHANGED, result.classification)
        self.assertTrue(result.identity.owned)

    def test_owned_field_drift_is_path_level_and_deterministic(self):
        changed = live(payload=compile_orm_to_ap("ap.internal", destination_port=6672))
        result = self.managed([changed], [mapping()])
        self.assertEqual(ChannelClassification.DRIFTED, result.classification)
        self.assertEqual(["destination.port"], [item.path for item in result.differences])

    def test_same_name_foreign_channel_conflicts_and_is_never_adopted(self):
        root = ET.fromstring(compile_orm_to_ap("ap.internal"))
        root.find("description").text = "Operator owned"
        result = self.managed([live(payload=ET.tostring(root, encoding="unicode"))])
        self.assertEqual(ChannelClassification.CONFLICT, result.classification)
        self.assertIn("same-name-channel-is-not-owned", result.blocking_reasons)

    def test_mapping_and_marker_id_contradiction_conflicts(self):
        result = self.managed([live(channel_id="other")], [mapping("mapped")])
        self.assertEqual(ChannelClassification.CONFLICT, result.classification)
        self.assertIn("mapped-id-marker-contradiction", result.blocking_reasons)

    def test_mapped_id_with_wrong_marker_conflicts(self):
        root = ET.fromstring(compile_orm_to_ap("ap.internal"))
        root.find("description").text = "Operator owned"
        result = self.managed([live(payload=ET.tostring(root, encoding="unicode"))], [mapping()])
        self.assertEqual(ChannelClassification.CONFLICT, result.classification)

    def test_duplicate_markers_conflict(self):
        result = self.managed([live("one"), live("two")], [mapping("one")])
        self.assertEqual(ChannelClassification.CONFLICT, result.classification)
        self.assertTrue(result.identity.duplicate_marker)

    def test_malformed_managed_payload_conflicts(self):
        malformed = '<channel><name>HLAB_ORM_TO_AP</name><description>Managed by Healthcare Lab; logical_type=hlab-orm-to-ap; template_version=1</description></channel>'
        result = self.managed([LiveChannel("oie-1", "HLAB_ORM_TO_AP", 7, malformed)], [mapping()])
        self.assertEqual(ChannelClassification.CONFLICT, result.classification)
        self.assertIn("malformed-managed-candidate", result.blocking_reasons)

    def test_unrelated_inventory_is_external_and_read_only(self):
        root = ET.fromstring(compile_orm_to_ap("ap.internal"))
        root.find("description").text = "Operator owned"
        inventory = live("external", ET.tostring(root, encoding="unicode"), "OTHER")
        results = reconcile_inventory([self.desired], [], [inventory], normalize_desired=normalized_state, normalize_payload=normalized_state_from_payload)
        self.assertEqual([ChannelClassification.MISSING, ChannelClassification.EXTERNAL], [r.classification for r in results])
        self.assertEqual(("external-channel-read-only",), results[1].blocking_reasons)


if __name__ == "__main__":
    unittest.main()
