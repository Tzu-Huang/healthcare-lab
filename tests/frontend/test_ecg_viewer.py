from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class EcgViewerFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.template = (ROOT / "frontend/templates/ecg_viewer.html").read_text(
            encoding="utf-8"
        )
        cls.api = (
            ROOT / "frontend/static/js/api/ecg-viewer.js"
        ).read_text(encoding="utf-8")
        cls.view = (
            ROOT / "frontend/static/js/views/ecg-viewer.js"
        ).read_text(encoding="utf-8")
        cls.styles = (
            ROOT / "frontend/static/css/views/ecg-viewer.css"
        ).read_text(encoding="utf-8")

    def test_template_exposes_accessible_loading_content_and_error_states(self):
        for element_id in (
            "ecg-viewer-status",
            "ecg-viewer-loading",
            "ecg-viewer-error",
            "ecg-viewer-content",
            "ecg-viewer-graph",
            "ecg-viewer-graph-error",
        ):
            self.assertIn(f'id="{element_id}"', self.template)
        self.assertIn('role="status"', self.template)
        self.assertIn('aria-live="polite"', self.template)
        self.assertIn("css/views/ecg-viewer.css", self.template)
        self.assertIn("js/views/ecg-viewer.js", self.template)
        self.assertNotIn("WADO", self.template)

    def test_api_adapter_owns_result_scoped_metadata_and_svg_urls(self):
        self.assertIn(
            "`/api/dcm4chee/results/${normalizeResultId(resultId)}/ecg`",
            self.api,
        )
        self.assertIn(
            "`/api/dcm4chee/results/${normalizeResultId(resultId)}/ecg/render.svg`",
            self.api,
        )
        self.assertIn('/^[1-9]\\d*$/.test(value)', self.api)
        self.assertNotIn("wado", self.api.lower())

    def test_view_reconstructs_route_and_renders_summary(self):
        self.assertIn(
            r'pathname.match(/^\/viewer\/ecg\/([1-9]\d*)\/?$/)',
            self.view,
        )
        for field in (
            "waveform.leads",
            "waveform.samplingFrequencyHz",
            "waveform.unit",
            "waveform.durationSeconds",
        ):
            self.assertIn(field, self.view)
        self.assertIn("fetchEcgMetadata(resultId)", self.view)
        self.assertIn("ecgRenderSvgUrl(resultId)", self.view)

    def test_view_handles_metadata_and_graph_failures_independently(self):
        self.assertIn("function controlledError(error)", self.view)
        self.assertIn('"dcm4chee_ecg_result_not_found"', self.view)
        self.assertIn('"dcm4chee_ecg_instance_incomplete"', self.view)
        self.assertIn('"dcm4chee_ecg_unsupported"', self.view)
        self.assertIn('"dcm4chee_ecg_invalid"', self.view)
        self.assertIn("elements.graph.onerror", self.view)
        self.assertIn("elements.graphError.hidden = false", self.view)
        self.assertIn('setStatus("ECG graph loaded.", "success")', self.view)

    def test_viewer_styles_are_scoped_and_respect_reduced_motion(self):
        self.assertIn(".ecg-viewer", self.styles)
        self.assertIn(".ecg-viewer-graph", self.styles)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.styles)


if __name__ == "__main__":
    unittest.main()
