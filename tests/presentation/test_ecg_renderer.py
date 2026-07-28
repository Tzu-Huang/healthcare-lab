import inspect
import math
import os
import re
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from io import BytesIO
from pathlib import Path
from types import MappingProxyType
from unittest.mock import Mock, patch

from matplotlib.axes import Axes
from matplotlib.backends.backend_svg import FigureCanvasSVG

from backend.domain.ecg_waveform import CANONICAL_LEADS, EcgChannel, EcgWaveform
from backend.presentation.ecg_renderer import (
    AMPLITUDE_WARNING,
    DISPLAY_ROW_PITCH_MV,
    EcgRenderConfig,
    EcgRenderConfigError,
    EcgRenderError,
    RenderedEcg,
    render_ecg,
)


SOURCE_CODES = (
    "5.6.3-9-1",
    "5.6.3-9-2",
    "5.6.3-9-61",
    "5.6.3-9-62",
    "5.6.3-9-63",
    "5.6.3-9-64",
    "5.6.3-9-3",
    "5.6.3-9-4",
    "5.6.3-9-5",
    "5.6.3-9-6",
    "5.6.3-9-7",
    "5.6.3-9-8",
)
DISCLAIMER = "For demonstration only - not for diagnostic use"


def make_waveform(*, sampling_frequency_hz=500.0, offset=0.0, sample_count=100):
    samples = tuple(
        math.sin(index / 7.0) + offset for index in range(sample_count)
    )
    channels = tuple(
        EcgChannel(lead, code, samples)
        for lead, code in zip(CANONICAL_LEADS, SOURCE_CODES)
    )
    return EcgWaveform(
        channels=channels,
        sampling_frequency_hz=sampling_frequency_hz,
        duration_seconds=len(samples) / sampling_frequency_hz,
        sop_class_uid="1.2.840.10008.5.1.4.1.1.9.1.1",
        unit="mV",
        display_metadata=MappingProxyType({"Modality": "ECG"}),
    )


def svg_text(result):
    return result.svg_bytes.decode("utf-8")


def retained_figure_ids():
    """Inspect Matplotlib's registry without importing pyplot in production."""
    from matplotlib._pylab_helpers import Gcf

    return set(Gcf.figs)


class EcgRendererContractTest(unittest.TestCase):
    def test_defaults_are_immutable_and_documented(self):
        config = EcgRenderConfig()

        self.assertEqual(config.width_px, 1600)
        self.assertEqual(config.height_px, 800)
        self.assertEqual(config.paper_speed_mm_s, 25.0)
        self.assertEqual(config.voltage_gain_mm_mv, 10.0)
        self.assertTrue(config.center_baseline)
        with self.assertRaises(FrozenInstanceError):
            config.width_px = 800

    def test_returns_nonempty_svg_with_media_type_labels_and_disclaimer(self):
        result = render_ecg(make_waveform())

        self.assertIsInstance(result, RenderedEcg)
        self.assertEqual(result.media_type, "image/svg+xml")
        self.assertTrue(result.svg_bytes.lstrip().startswith(b"<?xml"))
        text = svg_text(result)
        for lead in CANONICAL_LEADS:
            # Matplotlib's default SVG font mode stores text as exact comments.
            self.assertRegex(text, rf"<!--\s*{re.escape(lead)}\s*-->")
        self.assertIn(DISCLAIMER, text)

    def test_default_and_centered_rendering_do_not_mutate_input(self):
        waveform = make_waveform(offset=4.5)
        before = (
            waveform.channels,
            tuple(channel.samples_mv for channel in waveform.channels),
            waveform.sampling_frequency_hz,
            waveform.duration_seconds,
            dict(waveform.display_metadata),
        )

        render_ecg(waveform)
        render_ecg(waveform, EcgRenderConfig(center_baseline=True))

        self.assertEqual(
            before,
            (
                waveform.channels,
                tuple(channel.samples_mv for channel in waveform.channels),
                waveform.sampling_frequency_hz,
                waveform.duration_seconds,
                dict(waveform.display_metadata),
            ),
        )

    def test_sampling_frequency_controls_elapsed_time_passed_to_axes(self):
        original_plot = Axes.plot
        observed_x = []

        def recording_plot(axis, x_values, y_values, *args, **kwargs):
            observed_x.append(tuple(x_values))
            return original_plot(axis, x_values, y_values, *args, **kwargs)

        with patch.object(Axes, "plot", new=recording_plot):
            render_ecg(make_waveform(sampling_frequency_hz=250.0))

        trace_axes = [values for values in observed_x if len(values) == 100]
        self.assertEqual(len(trace_axes), 12)
        self.assertAlmostEqual(trace_axes[0][1] - trace_axes[0][0], 1 / 250.0)
        self.assertAlmostEqual(trace_axes[0][-1], 99 / 250.0)

    def test_all_twelve_leads_share_one_integrated_plot_axis(self):
        observed_axes = []
        original_plot = Axes.plot

        def recording_plot(axis, *args, **kwargs):
            observed_axes.append(axis)
            return original_plot(axis, *args, **kwargs)

        with patch.object(Axes, "plot", new=recording_plot):
            render_ecg(make_waveform())

        self.assertEqual(len(observed_axes), 12)
        self.assertEqual(len({id(axis) for axis in observed_axes}), 1)

    def test_vertical_display_scale_is_fixed_across_waveform_amplitudes(self):
        observed_limits = []
        original_set_ylim = Axes.set_ylim

        def recording_set_ylim(axis, bottom=None, top=None, *args, **kwargs):
            observed_limits.append((bottom, top))
            return original_set_ylim(axis, bottom, top, *args, **kwargs)

        with patch.object(Axes, "set_ylim", new=recording_set_ylim):
            render_ecg(make_waveform(offset=0.0))
            render_ecg(make_waveform(offset=50.0))

        expected = (
            -DISPLAY_ROW_PITCH_MV * 0.55,
            (5 * DISPLAY_ROW_PITCH_MV) + (DISPLAY_ROW_PITCH_MV * 0.55),
        )
        self.assertEqual(observed_limits, [expected, expected])

    def test_out_of_range_amplitude_is_not_auto_scaled_and_emits_warning(self):
        waveform = make_waveform(offset=0.0)
        oversized_samples = tuple(value * 5 for value in waveform.channels[0].samples_mv)
        oversized = EcgWaveform(
            channels=(
                EcgChannel(
                    waveform.channels[0].lead,
                    waveform.channels[0].source_code,
                    oversized_samples,
                ),
                *waveform.channels[1:],
            ),
            sampling_frequency_hz=waveform.sampling_frequency_hz,
            duration_seconds=waveform.duration_seconds,
            sop_class_uid=waveform.sop_class_uid,
            unit=waveform.unit,
            display_metadata=waveform.display_metadata,
        )

        text = svg_text(render_ecg(oversized))

        self.assertIn(AMPLITUDE_WARNING, text)

    def test_renderer_source_excludes_prototype_and_process_global_apis(self):
        import backend.presentation.ecg_renderer as renderer

        source = inspect.getsource(renderer).lower()
        self.assertNotIn("streamlit", source)
        self.assertNotIn("ecg_plot", source)
        self.assertNotIn("matplotlib.pyplot", source)
        self.assertNotIn("os.chdir", source)


class EcgRenderValidationTest(unittest.TestCase):
    def test_rejects_invalid_dimensions(self):
        invalid_values = (
            None,
            True,
            "1200",
            float("nan"),
            float("inf"),
            -1,
            0,
            319,
            4097,
        )
        for field in ("width_px", "height_px"):
            for value in invalid_values:
                with self.subTest(field=field, value=value):
                    with self.assertRaises(EcgRenderConfigError):
                        render_ecg(
                            make_waveform(),
                            EcgRenderConfig(**{field: value}),
                        )

    def test_rejects_invalid_scales(self):
        invalid_values = (
            None,
            True,
            "25",
            float("nan"),
            float("inf"),
            -1,
            0,
        )
        for field in ("paper_speed_mm_s", "voltage_gain_mm_mv"):
            for value in invalid_values:
                with self.subTest(field=field, value=value):
                    with self.assertRaises(EcgRenderConfigError):
                        render_ecg(
                            make_waveform(),
                            EcgRenderConfig(**{field: value}),
                        )

    def test_rejects_oversized_workloads_before_lock_or_figure_allocation(self):
        import backend.presentation.ecg_renderer as renderer

        workloads = (
            make_waveform(sampling_frequency_hz=1_000.0, sample_count=10_001),
            make_waveform(sampling_frequency_hz=500.0, sample_count=5_001),
        )
        fake_lock = Mock()

        with (
            patch.object(renderer, "_RENDER_LOCK", fake_lock),
            patch.object(renderer, "Figure") as figure,
        ):
            for waveform in workloads:
                with self.subTest(
                    samples=len(waveform.channels[0].samples_mv),
                    frequency=waveform.sampling_frequency_hz,
                ):
                    with self.assertRaises(EcgRenderError):
                        render_ecg(waveform)

        fake_lock.acquire.assert_not_called()
        figure.assert_not_called()


class EcgRenderResourceSafetyTest(unittest.TestCase):
    def test_repeated_rendering_retains_no_figures(self):
        before = retained_figure_ids()

        results = [render_ecg(make_waveform(offset=index)) for index in range(5)]

        self.assertTrue(all(result.svg_bytes for result in results))
        self.assertEqual(retained_figure_ids(), before)
        self.assertEqual(len({id(result.svg_bytes) for result in results}), 5)

    def test_concurrent_rendering_isolated_and_preserves_cwd(self):
        cwd = Path.cwd()
        inputs = tuple(make_waveform(offset=index) for index in range(4))

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = tuple(executor.map(render_ecg, inputs))

        self.assertEqual(Path.cwd(), cwd)
        self.assertTrue(all(result.svg_bytes for result in results))
        self.assertTrue(all(DISCLAIMER in svg_text(result) for result in results))
        self.assertEqual(len({id(result.svg_bytes) for result in results}), 4)

    def test_serialization_failure_raises_typed_error_and_cleans_up(self):
        before = retained_figure_ids()

        with patch.object(
            FigureCanvasSVG,
            "print_svg",
            side_effect=OSError("simulated serialization failure"),
        ):
            with self.assertRaises(EcgRenderError) as caught:
                render_ecg(make_waveform())

        self.assertIsInstance(caught.exception.__cause__, OSError)
        self.assertEqual(retained_figure_ids(), before)
        self.assertEqual(Path.cwd(), Path(os.getcwd()))

    def test_figure_cleanup_failure_still_closes_buffer_and_releases_lock(self):
        import backend.presentation.ecg_renderer as renderer

        buffer = BytesIO()
        fake_lock = Mock()
        with (
            patch.object(renderer, "BytesIO", return_value=buffer),
            patch.object(renderer, "_RENDER_LOCK", fake_lock),
            patch.object(
                renderer.Figure,
                "clear",
                side_effect=OSError("simulated figure cleanup failure"),
            ),
        ):
            with self.assertRaises(EcgRenderError) as caught:
                render_ecg(make_waveform())

        self.assertIsInstance(caught.exception.__cause__, OSError)
        self.assertTrue(buffer.closed)
        fake_lock.acquire.assert_called_once_with()
        fake_lock.release.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
