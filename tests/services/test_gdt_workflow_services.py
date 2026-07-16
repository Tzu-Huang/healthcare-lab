import tempfile
import unittest
from pathlib import Path

from backend.services.gdt_workflow import (
    GdtBridgeService,
    GdtOrderService,
    GdtResultService,
    GdtWorkflowService,
)


class RepositoryDouble:
    def __init__(self):
        self.order = {"id": 7, "localGdtOrderNumber": "GDT-ORD-000007", "rawGdtText": "6302"}

    def list_gdt_order_records(self): return [self.order]
    def get_gdt_order_record(self, order_id):
        if order_id != 7: raise KeyError(order_id)
        return self.order
    def create_gdt_order_record(self, payload): return {"id": 8, **payload}
    def list_gdt_workbench(self, *, bridge_inbox): return {"bridgeInbox": bridge_inbox}
    def record_gdt_order_export(self, order_id, **values): return {"id": order_id, **values}
    def create_gdt_demo_result(self, order_id): return {"orderRecordId": order_id}
    def list_gdt_messages(self): return [{"id": 1}]
    def list_gdt_events(self, order_id): return [{"orderRecordId": order_id}]
    def record_gdt_result(self, payload): return payload


class WatcherDouble:
    def status(self): return {"running": False}
    def configure(self, **values): return values
    def start(self): return {"running": True}
    def stop(self): return {"running": False}


class GdtFocusedWorkflowServicesTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.repository = RepositoryDouble()
        self.config = {
            "GDT_BRIDGE_PATH": self.directory.name,
            "GDT_BRIDGE_IMPORT_SUCCESS_MODE": "archive",
            "GDT_BRIDGE_FILENAME_PROFILE": "permissive",
            "GDT_BRIDGE_RECEIVER_ID": "",
            "GDT_BRIDGE_SENDER_ID": "",
        }
        self.service = GdtWorkflowService(
            self.repository, self.config, WatcherDouble(),
            is_internal_file=lambda path: False,
            has_supported_extension=lambda path, **kwargs: path.suffix == ".gdt",
            filename_binding_matches=lambda path, **kwargs: True,
            bridge_importer=lambda *args, **kwargs: {"imported": [], "failures": [], "skipped": []},
        )

    def tearDown(self):
        self.directory.cleanup()

    def test_facade_composes_independently_meaningful_services(self):
        self.assertIsInstance(self.service.order_service, GdtOrderService)
        self.assertIsInstance(self.service.bridge_service, GdtBridgeService)
        self.assertIsInstance(self.service.result_service, GdtResultService)
        self.assertEqual(self.service.list_orders(), [self.repository.order])
        self.assertEqual(self.service.create_demo_result(7), {"orderRecordId": 7})
        self.assertEqual(self.service.watcher_status(), {"running": False})

    def test_focused_services_expose_only_owned_use_cases(self):
        public = lambda owner: {
            name for name, value in owner.__class__.__dict__.items()
            if not name.startswith("_") and callable(value)
        }
        self.assertEqual(public(self.service.order_service), {"list", "get", "create"})
        self.assertEqual(public(self.service.bridge_service), {
            "inbox_items", "bridge_config", "update_bridge_config", "write_6302",
            "import_bridge_file", "watcher_status", "start_watcher", "stop_watcher",
        })
        self.assertEqual(public(self.service.result_service), {
            "workbench", "create_demo_result", "messages", "events", "import_result",
        })
        self.assertFalse(hasattr(self.service.order_service, "start_watcher"))
        self.assertFalse(hasattr(self.service.result_service, "write_6302"))


if __name__ == "__main__":
    unittest.main()
