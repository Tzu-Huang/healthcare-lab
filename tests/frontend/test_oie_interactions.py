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
        app = create_app(str(Path(cls.temp_dir.name) / "oie-browser.db"))
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


if __name__ == "__main__":
    unittest.main()
