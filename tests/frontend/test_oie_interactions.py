from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlparse

from backend.app_factory import create_app

try:
    from playwright.sync_api import Route, sync_playwright
except ImportError:  # pragma: no cover - explicit focused verification reports the missing dependency
    Route = object
    sync_playwright = None

from werkzeug.serving import make_server


PATIENT = {
    "id": 1,
    "payload": "MSH|^~\\&|LAB||OIE||ADT^A04|ADT1|P|2.5.1\\rPID|1||MRN-001",
    "createdAt": "2026-07-19T10:00:00+08:00",
    "summary": {"mrn": "MRN-001", "name": "Ada Lovelace"},
    "orderCount": 1,
    "resultCount": 1,
    "orders": [
        {
            "id": 11,
            "localOrderNumber": "ORD-001",
            "payload": "MSH|^~\\&|LAB||OIE||ORM^O01|ORM1|P|2.5.1",
            "createdAt": "2026-07-19T10:05:00+08:00",
            "priority": "R",
            "status": "Ready to send",
            "summary": {
                "mrn": "MRN-001",
                "visitNumber": "VISIT-001",
                "orderCode": "ECG12",
            },
        }
    ],
    "results": [
        {
            "id": 21,
            "payload": "MSH|^~\\&|OIE||LAB||ORU^R01|ORU1|P|2.5.1",
            "messageType": "ORU",
            "patientMrn": "MRN-001",
            "placerOrderNumber": "ORD-001",
            "matchStatus": "matched",
            "receivedAt": "2026-07-19T10:10:00+08:00",
        }
    ],
}


@unittest.skipIf(sync_playwright is None, "Playwright is required for controlled browser verification")
class OieInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        app = create_app(str(Path(cls.temp_dir.name) / "oie-browser.db"), activate_runtime=False)
        app.config.update(TESTING=True)
        cls.server = make_server("127.0.0.1", 0, app)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server_thread.join(timeout=5)
        cls.temp_dir.cleanup()

    def test_inventory_selection_preview_send_and_listener_controls(self):
        calls: list[tuple[str, str]] = []
        browser_errors: list[str] = []
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.on("console", lambda message: browser_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: browser_errors.append(str(error)))

        def handle_api(route: Route) -> None:
            request = route.request
            request_path = urlparse(request.url).path
            if not request_path.startswith("/api/"):
                route.continue_()
                return
            path = request.url.split("?", 1)[0]
            calls.append((request.method, path))
            if path.endswith("/api/oie/workbench"):
                payload = {"patients": [PATIENT], "unmatchedResults": []}
            elif path.endswith("/api/oie/result-listener/status"):
                payload = {"item": {"running": False, "host": "127.0.0.1", "port": 6665}}
            elif path.endswith("/api/oie/result-listener/start"):
                payload = {"item": {"running": True, "host": "127.0.0.1", "port": 6665}}
            elif path.endswith("/api/oie/result-listener/stop"):
                payload = {"item": {"running": False, "host": "127.0.0.1", "port": 6665}}
            elif path.endswith("/api/oie/local-orders/11/send"):
                payload = {
                    "success": True,
                    "item": {**PATIENT["orders"][0], "status": "Sent", "ack": {"code": "AA", "payload": "MSA|AA|ORM1"}},
                }
            else:
                payload = {}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

        page.route("**/api/**", handle_api)
        page.goto(self.base_url, wait_until="networkidle")
        self.assertEqual([], browser_errors)
        page.locator('[data-nav-target="oie-view"]').click()
        page.locator("#oie-inventory-status").wait_for(state="visible")
        self.assertEqual(page.locator("#oie-inventory-status").inner_text(), "Updated")

        patient_row = page.locator("#oie-inventory-list tr.oie-patient-row")
        self.assertEqual(patient_row.count(), 1)
        patient_row.click()
        self.assertIn("ADT^A04", page.locator("#oie-payload-preview").inner_text())
        self.assertIn("Ada Lovelace", page.locator("#oie-selected-patient-title").inner_text())

        page.locator("#oie-inventory-list .oie-patient-toggle").click()
        page.get_by_role("button", name="Select", exact=True).click()
        self.assertIn("ORM^O01", page.locator("#oie-payload-preview").inner_text())
        self.assertFalse(page.locator("#send-selected-oie-order").is_disabled())

        page.locator("#send-selected-oie-order").click()
        page.locator("#oie-send-status").get_by_text("Sent", exact=True).wait_for()
        self.assertIn(("POST", f"{self.base_url}/api/oie/local-orders/11/send"), calls)

        page.locator("#start-oie-listener").click()
        page.locator("#oie-listener-status").get_by_text("Running 127.0.0.1:6665", exact=True).wait_for()
        page.locator("#stop-oie-listener").click()
        page.locator("#oie-listener-status").get_by_text("Stopped", exact=True).wait_for()

        page.get_by_role("button", name="Preview", exact=True).click()
        self.assertIn("ORU^R01", page.locator("#oie-payload-preview").inner_text())
        self.assertIn(("POST", f"{self.base_url}/api/oie/result-listener/start"), calls)
        self.assertIn(("POST", f"{self.base_url}/api/oie/result-listener/stop"), calls)
        self.assertEqual([], browser_errors)

    def test_settings_save_shows_reminder_until_retry_applies_listener(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        profile = {
            "profileName": "local-oie",
            "managementApi": {
                "baseUrl": "http://oie:8080", "username": "admin",
                "tlsVerify": False, "timeoutSeconds": 10,
                "passwordConfigured": True,
            },
            "resultListener": {
                "host": "127.0.0.1", "port": 6665,
                "mllpFraming": True, "autoStart": True,
            },
            "managedChannels": [],
        }
        listener_status = {
            "state": "running", "running": True,
            "host": "127.0.0.1", "port": 6665, "mllpFraming": True,
        }

        def handle_api(route: Route) -> None:
            request = route.request
            path = urlparse(request.url).path
            if path == "/api/oie/settings" and request.method == "GET":
                payload = {"success": True, "item": profile}
            elif path == "/api/oie/settings" and request.method == "PUT":
                saved = json.loads(request.post_data or "{}")
                profile["resultListener"] = saved["resultListener"]
                payload = {"success": True, "item": profile, "runtimeReloadRequired": True}
            elif path == "/api/oie/result-listener/status":
                payload = {"success": True, "item": listener_status}
            elif path == "/api/oie/result-listener/retry":
                listener_status.update({
                    "state": "running", "running": True,
                    "host": profile["resultListener"]["host"],
                    "port": profile["resultListener"]["port"],
                    "mllpFraming": profile["resultListener"]["mllpFraming"],
                })
                payload = {"success": True, "item": listener_status}
            else:
                route.continue_()
                return
            route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

        page.route("**/api/**", handle_api)
        page.goto(self.base_url, wait_until="networkidle")
        page.locator('#settings-view[data-module-owner="settings"]').wait_for(
            state="attached"
        )
        page.locator("#settings-view").evaluate("element => { element.hidden = false; }")
        page.evaluate(
            "() => import('/static/js/views/settings.js')"
            ".then(({ refreshSettings }) => refreshSettings())"
        )
        page.locator("#settings-tab-oie").click()
        page.locator("#settings-listener-host").fill("127.0.0.2")
        page.locator("#save-listener-settings").click()
        reminder = page.locator("#settings-listener-reload-reminder")
        reminder.wait_for(state="visible")
        self.assertIn("not active", reminder.inner_text())

        page.close()
        reloaded_page = self.browser.new_page()
        self.addCleanup(reloaded_page.close)
        reloaded_page.route("**/api/**", handle_api)
        reloaded_page.goto(self.base_url, wait_until="networkidle")
        reloaded_page.locator('#settings-view[data-module-owner="settings"]').wait_for(
            state="attached"
        )
        reloaded_page.evaluate(
            "() => import('/static/js/views/settings.js')"
            ".then(({ refreshSettings }) => refreshSettings())"
        )
        self.assertEqual(
            reloaded_page.locator("#settings-listener-host").input_value(),
            "127.0.0.2",
        )
        reminder = reloaded_page.locator("#settings-listener-reload-reminder")
        self.assertFalse(reminder.evaluate("element => element.hidden"))
        self.assertIn("not active", reminder.inner_text())

        reloaded_page.evaluate(
            "() => import('/static/js/views/settings.js')"
            ".then(({ retryListenerFromSettings }) => retryListenerFromSettings())"
        )
        self.assertTrue(reminder.evaluate("element => element.hidden"))

        reloaded_page.locator("#settings-listener-auto-start").evaluate(
            "element => { element.checked = false; }"
        )
        reloaded_page.evaluate(
            "() => import('/static/js/views/settings.js')"
            ".then(({ saveListenerSettings }) => saveListenerSettings())"
        )
        self.assertFalse(reminder.evaluate("element => element.hidden"))

        reloaded_page.close()
        disabled_page = self.browser.new_page()
        self.addCleanup(disabled_page.close)
        disabled_page.route("**/api/**", handle_api)
        disabled_page.goto(self.base_url, wait_until="networkidle")
        disabled_page.locator('#settings-view[data-module-owner="settings"]').wait_for(
            state="attached"
        )
        disabled_page.evaluate(
            "() => import('/static/js/views/settings.js')"
            ".then(({ refreshSettings }) => refreshSettings())"
        )
        reminder = disabled_page.locator("#settings-listener-reload-reminder")
        self.assertFalse(reminder.evaluate("element => element.hidden"))

        listener_status.update({"state": "stopped", "running": False})
        disabled_page.evaluate(
            "() => import('/static/js/views/settings.js')"
            ".then(({ refreshSettings }) => refreshSettings())"
        )
        self.assertTrue(reminder.evaluate("element => element.hidden"))

    def test_settings_channel_lifecycle_is_preview_bound_and_external_is_read_only(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        mutations: list[tuple[str, dict]] = []
        profile = {
            "managementApi": {"baseUrl": "http://oie:8080", "username": "admin", "tlsVerify": False,
                              "timeoutSeconds": 10, "passwordConfigured": True},
            "resultListener": {"host": "127.0.0.1", "port": 6665, "mllpFraming": True, "autoStart": True},
            "managedChannels": [],
        }
        inventory = [
            {"logicalType": "hlab-orm-to-ap", "classification": "unchanged", "name": "HLAB_ORM_TO_AP",
             "channelId": "c1", "revision": 7, "status": "STARTED", "route": "OIE:6600 -> AP:6671",
             "lastOperation": {"operation": "redeploy", "outcome": "success"},
             "permittedActions": ["redeploy", "delete"]},
            {"logicalType": "hlab-oru-to-hlab", "classification": "missing", "name": "HLAB_ORU_TO_HLAB",
             "route": "OIE:6661 -> lab-app:6665", "permittedActions": ["create"]},
            {"classification": "external", "name": "OPERATOR_CHANNEL", "channelId": "external-1", "status": "STARTED"},
        ]

        def handle_api(route: Route) -> None:
            request = route.request
            path = urlparse(request.url).path
            if path == "/api/oie/settings" and request.method == "PUT":
                saved = json.loads(request.post_data or "{}")
                profile["managedChannels"] = saved["managedChannels"]
                saved_type = saved["managedChannels"][-1]["logicalType"]
                item = next(value for value in inventory if value.get("logicalType") == saved_type)
                if item["classification"] == "unchanged":
                    item.update(classification="drifted", permittedActions=["update", "redeploy", "delete"])
                payload = {"success": True, "item": profile}
            elif path == "/api/oie/settings":
                payload = {"success": True, "item": profile}
            elif path == "/api/oie/result-listener/status":
                payload = {"success": True, "item": {"state": "running", "running": True, "host": "127.0.0.1", "port": 6665, "mllpFraming": True}}
            elif path == "/api/oie/managed-channels":
                payload = {"success": True, "items": inventory}
            elif "/previews/" in path:
                operation = path.rsplit("/", 1)[-1]
                logical_type = path.split("/")[-3]
                item = next(value for value in inventory if value.get("logicalType") == logical_type)
                payload = {"success": True, "item": {"previewToken": f"token-{operation}", "operation": operation,
                    "channelName": item["name"], "route": item["route"], "channelId": item.get("channelId"),
                    "snapshot": item, "expectedSteps": [operation]}}
            elif path.startswith("/api/oie/managed-channels/") and request.method == "POST":
                operation = path.rsplit("/", 1)[-1]
                body = json.loads(request.post_data or "{}")
                mutations.append((operation, body))
                if operation == "redeploy":
                    payload = {"success": False, "item": {"outcome": "partial-failure", "steps": [
                        {"name": "undeploy", "status": "succeeded"}, {"name": "deploy", "status": "failed"}]}}
                else:
                    payload = {"success": True, "item": {"outcome": "success", "steps": [{"name": operation, "status": "succeeded"}]}}
            else:
                route.continue_()
                return
            route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

        page.route("**/api/**", handle_api)
        page.goto(self.base_url, wait_until="networkidle")
        page.locator('[data-nav-target="settings-view"]').click()
        page.locator("#settings-tab-oie").click()
        page.get_by_text("OPERATOR_CHANNEL", exact=True).wait_for()
        external_card = page.get_by_text("OPERATOR_CHANNEL", exact=True).locator("..")
        self.assertEqual(0, external_card.locator("button[data-operation]").count())
        self.assertIn("redeploy: success", page.get_by_text("HLAB_ORM_TO_AP", exact=True).locator("..").inner_text())
        page.get_by_role("button", name="Preview recreate", exact=True).wait_for()

        missing_card = page.get_by_text("HLAB_ORU_TO_HLAB", exact=True).locator("..")
        missing_card.get_by_text("Edit approved fields", exact=True).click()
        missing_card.get_by_role("button", name="Save desired fields", exact=True).click()
        page.get_by_role("button", name="Preview recreate", exact=True).wait_for()
        missing_mapping = next(item for item in profile["managedChannels"] if item["logicalType"] == "hlab-oru-to-hlab")
        self.assertEqual("HLAB_ORU_TO_HLAB", missing_mapping["channelName"])

        unchanged_card = page.get_by_text("HLAB_ORM_TO_AP", exact=True).locator("..")
        unchanged_card.get_by_text("Edit approved fields", exact=True).click()
        unchanged_card.get_by_role("button", name="Save desired fields", exact=True).click()
        page.get_by_role("button", name="Preview apply", exact=True).wait_for()

        page.get_by_role("button", name="Preview redeploy", exact=True).click()
        page.locator("#settings-preview-execute").click()
        page.get_by_text("Operation did not fully complete", exact=False).wait_for()
        self.assertEqual("redeploy", mutations[-1][0])

        page.get_by_role("button", name="Preview delete", exact=True).click()
        execute = page.locator("#settings-preview-execute")
        self.assertTrue(execute.is_disabled())
        page.locator("#settings-delete-confirmation").fill("hlab-orm-to-ap")
        self.assertTrue(execute.is_disabled())
        page.locator("#settings-delete-confirmation").fill("HLAB_ORM_TO_AP")
        self.assertFalse(execute.is_disabled())
        execute.click()
        self.assertEqual(("delete", {"previewToken": "token-delete", "confirmation": "HLAB_ORM_TO_AP"}), mutations[-1])

if __name__ == "__main__":
    unittest.main()
