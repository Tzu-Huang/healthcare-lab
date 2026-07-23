import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
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

    def test_profile_reload_does_not_replace_a_scan_that_cannot_quiesce(self):
        scan_started = Event()
        release_scan = Event()
        calls = []

        def blocked_importer(*_args, **_kwargs):
            calls.append("scan")
            scan_started.set()
            release_scan.wait(5)
            return {
                "imported": [],
                "skipped": [],
                "failures": [],
                "processedCount": 0,
            }

        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "inbox").mkdir()
            (root / "outbox").mkdir()
            watcher = GdtBridgeInboundWatcher(
                object(), root, blocked_importer, poll_seconds=0.25
            )
            watcher.start()
            self.assertTrue(scan_started.wait(1))

            outcome = watcher.apply_profile(
                SimpleNamespace(
                    enabled=True,
                    bridge_path=str(root),
                    success_mode="archive",
                    filename_profile="permissive",
                    receiver_id="",
                    sender_id="",
                    poll_seconds=0.25,
                    stable_seconds=1.0,
                )
            )

            self.assertEqual("restart-required", outcome["state"])
            self.assertEqual("application-restart", outcome["activation"])
            self.assertEqual(
                {
                    "state": "restart-required",
                    "activation": "application-restart",
                },
                watcher.activation_status(),
            )
            self.assertTrue(outcome["watcher"]["running"])
            self.assertEqual(["scan"], calls)

            release_scan.set()
            watcher.stop()


if __name__ == "__main__":
    unittest.main()
