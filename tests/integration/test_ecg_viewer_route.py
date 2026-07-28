from __future__ import annotations

from tests.integration._case_support import ApiCaseSupport


class EcgViewerRouteTests(ApiCaseSupport):
    def test_direct_result_navigation_serves_focused_viewer(self):
        response = self.client.get("/viewer/ecg/42")

        self.assertEqual(200, response.status_code)
        self.assertIn(b"<title>ECG Graph | Healthcare Lab</title>", response.data)
        self.assertIn(b'id="ecg-viewer-status"', response.data)
        self.assertIn(b"css/views/ecg-viewer.css", response.data)
        self.assertIn(b"js/views/ecg-viewer.js", response.data)
        self.assertNotIn(b"WADO", response.data)

    def test_viewer_route_rejects_non_numeric_result_identity(self):
        response = self.client.get("/viewer/ecg/not-a-result")

        self.assertEqual(404, response.status_code)

    def test_viewer_route_is_registered(self):
        routes = {rule.rule for rule in self.app.url_map.iter_rules()}

        self.assertIn("/viewer/ecg/<int:result_id>", routes)
