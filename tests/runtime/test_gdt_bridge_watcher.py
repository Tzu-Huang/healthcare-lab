import unittest

from backend.runtime.gdt_bridge_watcher import GdtBridgeInboundWatcher


class GdtBridgeInboundWatcherTest(unittest.TestCase):
    def test_configuration_updates_only_while_stopped(self):
        watcher = GdtBridgeInboundWatcher(
            object(),
            "bridge",
            lambda *_args, **_kwargs: {"imported": [], "skipped": [], "failures": [], "processedCount": 0},
        )

        status = watcher.configure(
            bridge_root="updated",
            success_mode="delete",
            filename_profile="gdt21",
            receiver_id="RECV",
            sender_id="SEND",
        )

        self.assertEqual("updated", status["bridgeRoot"])
        self.assertEqual("delete", status["successMode"])
        self.assertEqual("gdt21", status["filenameProfile"])
        self.assertEqual("RECV", status["receiverId"])
        self.assertEqual("SEND", status["senderId"])


if __name__ == "__main__":
    unittest.main()
