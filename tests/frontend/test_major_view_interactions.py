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
except ImportError:  # pragma: no cover - focused verification reports the missing dependency
    Route = object
    sync_playwright = None

from werkzeug.serving import make_server


@unittest.skipIf(sync_playwright is None, "Playwright is required for controlled browser verification")
class MajorViewInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        app = create_app(str(Path(cls.temp_dir.name) / "major-views.db"))
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

    def open_controlled_page(
        self,
        viewport: dict[str, int] | None = None,
        init_script: str | None = None,
    ):
        calls: list[tuple[str, str]] = []
        browser_errors: list[str] = []
        page = self.browser.new_page(viewport=viewport or {"width": 1440, "height": 1000})
        self.addCleanup(page.close)
        if init_script:
            page.add_init_script(init_script)
        page.on("console", lambda message: browser_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: browser_errors.append(str(error)))

        def handle_api(route: Route) -> None:
            request = route.request
            path = urlparse(request.url).path
            if not path.startswith("/api/"):
                route.continue_()
                return
            calls.append((request.method, path))
            if path == "/api/dashboard/services":
                payload = {"items": [], "events": [], "resources": [], "summary": {}}
            elif path == "/api/patients":
                payload = {"items": []}
            elif path in {"/api/orders", "/api/gdt/orders"}:
                payload = {"items": []}
            elif path == "/api/fhir/inventory":
                payload = {"items": [], "patients": [], "resourceTypes": []}
            elif path == "/api/dcm4chee/profile/diagnostics":
                payload = {"valid": True, "checks": [], "endpoints": {}}
            elif path == "/api/oie/workbench":
                payload = {"patients": [], "unmatchedResults": []}
            elif path == "/api/oie/result-listener/status":
                payload = {"item": {"running": False, "host": "127.0.0.1", "port": 6665}}
            elif path == "/api/gdt/bridge/config":
                payload = {"item": {"bridgePath": "", "watcher": {"running": False}}}
            elif path == "/api/gdt/workbench":
                payload = {"patients": [], "bridgeInbox": []}
            else:
                payload = {}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

        page.route("**/api/**", handle_api)
        page.goto(self.base_url, wait_until="networkidle")
        return page, calls, browser_errors

    def test_repeated_application_initialization_registers_actions_once(self):
        page, calls, browser_errors = self.open_controlled_page()
        page.evaluate("import('/static/js/views/application.js').then(module => module.initializeApplication())")

        page.locator('[data-nav-target="patient-view"]').click()
        page.locator("#refresh-patients").wait_for(state="visible")
        page.wait_for_timeout(50)
        calls.clear()
        page.locator("#refresh-patients").click()
        page.wait_for_timeout(50)
        self.assertEqual(1, [path for _method, path in calls].count("/api/patients"))

        page.locator('[data-nav-target="order-view"]').click()
        page.locator("#refresh-orders").wait_for(state="visible")
        page.wait_for_timeout(50)
        calls.clear()
        page.locator("#refresh-orders").click()
        page.wait_for_timeout(50)
        paths = [path for _method, path in calls]
        self.assertEqual(1, paths.count("/api/orders"))
        self.assertEqual(1, paths.count("/api/gdt/orders"))

        page.evaluate("""
          window.orderActivations = 0;
          document.addEventListener('healthcare-lab:view-activated', event => {
            if (event.detail.viewId === 'order-view') window.orderActivations += 1;
          });
        """)
        page.locator('[data-nav-target="gdt-view"]').click()
        page.locator("#create-gdt-ecg-order").click()
        self.assertEqual(1, page.evaluate("window.orderActivations"))
        self.assertEqual([], browser_errors)

    def test_feature_initialization_failure_is_diagnosed_and_isolated(self):
        init_script = """
          window.initializationErrors = [];
          document.addEventListener('healthcare-lab:view-error', event => {
            if (event.detail.phase === 'initialization') {
              window.initializationErrors.push(event.detail.viewId);
            }
          });
          document.addEventListener('DOMContentLoaded', () => {
            document.querySelector('#refresh-dashboard')?.remove();
          });
        """
        page, _calls, browser_errors = self.open_controlled_page(init_script=init_script)
        self.assertEqual(["lab-console-view"], page.evaluate("window.initializationErrors"))
        self.assertTrue(page.locator("#lab-console-view").get_attribute("data-initialization-error"))

        page.locator('[data-nav-target="patient-view"]').click()
        page.locator("#load-patient-demo").click()
        self.assertIn("MSH|", page.locator("#patient-payload-preview").inner_text())
        self.assertEqual([], browser_errors)

    def test_navigation_startup_and_representative_major_view_interactions(self):
        page, calls, browser_errors = self.open_controlled_page()
        self.assertEqual([], browser_errors)

        page.locator("#refresh-dashboard").click()
        page.locator("#dashboard-refresh-status").get_by_text("Dashboard updated", exact=True).wait_for()

        page.locator('[data-nav-target="patient-view"]').click()
        page.locator("#load-patient-demo").click()
        self.assertIn("MSH|", page.locator("#patient-payload-preview").inner_text())

        page.locator('[data-nav-target="order-view"]').click()
        page.locator("#load-order-demo").click()
        self.assertEqual("ECG12", page.locator("#order-code").input_value())

        page.locator('[data-nav-target="medplum-view"]').click()
        page.locator("#medplum-inventory-status").get_by_text("Inventory loaded", exact=True).wait_for()

        page.locator('[data-nav-target="dcm4chee-view"]').click()
        page.locator("#dcm4chee-console-status").get_by_text("dcm4chee ready", exact=True).wait_for()

        page.locator('[data-nav-target="gdt-view"]').click()
        page.locator("#gdt-console-status").get_by_text("Updated", exact=True).wait_for()

        expected_paths = {
            "/api/dashboard/services",
            "/api/patients",
            "/api/orders",
            "/api/gdt/orders",
            "/api/fhir/inventory",
            "/api/dcm4chee/profile/diagnostics",
            "/api/gdt/bridge/config",
            "/api/gdt/workbench",
        }
        self.assertTrue(expected_paths.issubset({path for _method, path in calls}))
        self.assertEqual([], browser_errors)

    def test_desktop_and_narrow_viewports_preserve_responsive_layout(self):
        page, _calls, browser_errors = self.open_controlled_page({"width": 1440, "height": 1000})
        desktop_columns = page.locator(".app-shell").evaluate("element => getComputedStyle(element).gridTemplateColumns")
        self.assertNotEqual("1440px", desktop_columns)
        self.assertEqual("sticky", page.locator(".app-sidebar").evaluate("element => getComputedStyle(element).position"))

        page.set_viewport_size({"width": 700, "height": 1000})
        page.wait_for_timeout(50)
        narrow_columns = page.locator(".app-shell").evaluate("element => getComputedStyle(element).gridTemplateColumns")
        self.assertEqual("700px", narrow_columns)
        self.assertEqual("static", page.locator(".app-sidebar").evaluate("element => getComputedStyle(element).position"))
        self.assertEqual("none", page.locator("#patient-view").evaluate("element => getComputedStyle(element).display"))
        self.assertEqual([], browser_errors)


if __name__ == "__main__":
    unittest.main()
