import unittest
from types import SimpleNamespace

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

    def test_complete_disabled_profile_is_applied_without_starting(self):
        watcher = GdtBridgeInboundWatcher(
            object(),
            "bridge",
            lambda *_args, **_kwargs: {
                "imported": [],
                "skipped": [],
                "failures": [],
                "processedCount": 0,
            },
        )

        outcome = watcher.apply_profile(
            SimpleNamespace(
                enabled=False,
                bridge_path="/data/gdt-bridge",
                success_mode="delete",
                filename_profile="gdt35",
                receiver_id="RECV",
                sender_id="SEND",
                poll_seconds=3.0,
                stable_seconds=2.0,
            )
        )

        self.assertEqual("effective", outcome["state"])
        self.assertEqual("immediate", outcome["activation"])
        self.assertFalse(outcome["watcher"]["running"])
        self.assertEqual(2.0, outcome["watcher"]["stableSeconds"])


if __name__ == "__main__":
    unittest.main()
