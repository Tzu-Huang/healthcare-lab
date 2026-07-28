"""Request-local, demonstration-only SVG rendering for normalized ECG data."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from math import ceil, isfinite
from statistics import median
from threading import RLock
from typing import Final

from matplotlib.backends.backend_svg import FigureCanvasSVG
from matplotlib.figure import Figure

from backend.domain.ecg_waveform import CANONICAL_LEADS, EcgWaveform


DISCLAIMER: Final = "For demonstration only - not for diagnostic use"
SVG_MEDIA_TYPE: Final = "image/svg+xml"

# These browser-oriented limits prevent unreasonable figure allocation. They
# are output bounds, not claims about physical screen or paper dimensions.
MIN_WIDTH_PX: Final = 320
MAX_WIDTH_PX: Final = 4096
MIN_HEIGHT_PX: Final = 480
MAX_HEIGHT_PX: Final = 4096
MIN_PAPER_SPEED_MM_S: Final = 1.0
MAX_PAPER_SPEED_MM_S: Final = 100.0
MIN_VOLTAGE_GAIN_MM_MV: Final = 1.0
MAX_VOLTAGE_GAIN_MM_MV: Final = 100.0
# The MVP is a 10-second resting ECG display. Bound both point count and
# duration before acquiring the Matplotlib lock so malformed or unexpectedly
# long normalized inputs cannot monopolize every threaded request.
MAX_SAMPLES_PER_LEAD: Final = 10_000
MAX_RENDER_DURATION_SECONDS: Final = 10.0
FIGURE_DPI: Final = 100.0
DISPLAY_HALF_RANGE_MV: Final = 2.0
DISPLAY_ROW_PITCH_MV: Final = DISPLAY_HALF_RANGE_MV * 2
AMPLITUDE_WARNING: Final = "Amplitude exceeds fixed display range (+/- 2 mV)"

# Matplotlib documents that it is not thread-safe. Gunicorn may invoke this
# module from multiple threads, so the complete Figure lifecycle is serialized
# while all output objects themselves remain request-local.
_RENDER_LOCK: Final = RLock()


class EcgRenderError(RuntimeError):
    """A normalized ECG could not be rendered."""


class EcgRenderConfigError(EcgRenderError, ValueError):
    """The requested rendering configuration is invalid."""


@dataclass(frozen=True, slots=True)
class EcgRenderConfig:
    """Validated nominal ECG display settings.

    Paper speed and voltage gain affect graph scale, but do not guarantee
    physical millimetre dimensions in a browser or on a printer.
    """

    # At the default calibration, these dimensions preserve equal nominal
    # millimetres on both axes for two 10-second columns and six 4 mV lanes.
    width_px: int = 1600
    height_px: int = 800
    paper_speed_mm_s: float = 25.0
    voltage_gain_mm_mv: float = 10.0
    center_baseline: bool = True


@dataclass(frozen=True, slots=True)
class RenderedEcg:
    """An in-memory SVG response suitable for a later HTTP adapter."""

    svg_bytes: bytes
    media_type: str = SVG_MEDIA_TYPE


def render_ecg(
    waveform: EcgWaveform,
    config: EcgRenderConfig = EcgRenderConfig(),
) -> RenderedEcg:
    """Render a canonical 12-lead waveform using request-local resources."""
    _validate_config(config)
    _validate_waveform(waveform)

    figure: Figure | None = None
    buffer = BytesIO()
    rendered: RenderedEcg | None = None
    render_error: EcgRenderError | None = None
    render_cause: Exception | None = None
    cleanup_error: Exception | None = None
    _RENDER_LOCK.acquire()
    try:
        figure = Figure(
            figsize=(config.width_px / FIGURE_DPI, config.height_px / FIGURE_DPI),
            dpi=FIGURE_DPI,
            facecolor="white",
        )
        canvas = FigureCanvasSVG(figure)
        axis = figure.subplots(1, 1)
        channels = {channel.lead: channel for channel in waveform.channels}
        columns = 2
        rows = len(CANONICAL_LEADS) // columns
        column_gap_seconds = 0.25
        prepared: list[tuple[str, tuple[float, ...]]] = []
        for index, lead in enumerate(CANONICAL_LEADS):
            samples = channels[lead].samples_mv
            display_samples = _display_samples(samples, config.center_baseline)
            prepared.append((lead, display_samples))

        duration = max(
            len(prepared[0][1]) / waveform.sampling_frequency_hz,
            1e-9,
        )
        row_pitch_mv = DISPLAY_ROW_PITCH_MV
        total_width = (duration * columns) + column_gap_seconds
        top_offset = (rows - 1) * row_pitch_mv
        amplitude_clipped = any(
            abs(value) > DISPLAY_HALF_RANGE_MV
            for _, samples in prepared
            for value in samples
        )
        axis.set_autoscale_on(False)
        axis.set_xlim(0.0, total_width)
        axis.set_ylim(-row_pitch_mv * 0.55, top_offset + row_pitch_mv * 0.55)
        _configure_grid(
            axis,
            total_width,
            config.paper_speed_mm_s,
            config.voltage_gain_mm_mv,
        )

        for index, (lead, display_samples) in enumerate(prepared):
            column = index // rows
            row = index % rows
            x_offset = column * (duration + column_gap_seconds)
            y_offset = top_offset - (row * row_pitch_mv)
            times = tuple(
                x_offset + (sample_index / waveform.sampling_frequency_hz)
                for sample_index in range(len(display_samples))
            )
            shifted_samples = tuple(value + y_offset for value in display_samples)
            axis.plot(times, shifted_samples, color="#111111", linewidth=0.7)
            axis.text(
                x_offset + (duration * 0.01),
                y_offset + (row_pitch_mv * 0.38),
                lead,
                ha="left",
                va="top",
                fontsize=10,
                fontweight="bold",
                color="#111111",
            )

        axis.axvline(
            duration + (column_gap_seconds / 2),
            color="#c98989",
            linewidth=0.8,
        )
        axis.tick_params(labelbottom=False, labelleft=False, length=0)
        for spine in axis.spines.values():
            spine.set_visible(False)

        figure.subplots_adjust(
            left=0.025, right=0.99, top=0.98, bottom=0.065
        )
        figure.text(
            0.5,
            0.018,
            DISCLAIMER,
            ha="center",
            va="bottom",
            fontsize=10,
            color="#7a1f1f",
        )
        if amplitude_clipped:
            figure.text(
                0.99,
                0.018,
                AMPLITUDE_WARNING,
                ha="right",
                va="bottom",
                fontsize=9,
                color="#b42318",
                fontweight="bold",
            )
        canvas.print_svg(buffer, metadata={"Description": DISCLAIMER})
        rendered = RenderedEcg(buffer.getvalue())
    except EcgRenderError as exc:
        render_error = exc
    except Exception as exc:
        render_error = EcgRenderError("Unable to render ECG waveform")
        render_cause = exc
    finally:
        try:
            if figure is not None:
                figure.clear()
        except Exception as exc:
            cleanup_error = exc
        finally:
            try:
                buffer.close()
            except Exception as exc:
                if cleanup_error is None:
                    cleanup_error = exc
            finally:
                _RENDER_LOCK.release()

    if render_error is not None:
        if render_cause is not None:
            raise render_error from render_cause
        raise render_error
    if cleanup_error is not None:
        raise EcgRenderError("Unable to clean up ECG rendering resources") from cleanup_error
    if rendered is None:  # pragma: no cover - defensive invariant
        raise EcgRenderError("ECG rendering completed without output")
    return rendered


def _validate_config(config: EcgRenderConfig) -> None:
    if not isinstance(config, EcgRenderConfig):
        raise EcgRenderConfigError("config must be an EcgRenderConfig")
    if isinstance(config.width_px, bool) or not isinstance(config.width_px, int):
        raise EcgRenderConfigError("width_px must be an integer")
    if not MIN_WIDTH_PX <= config.width_px <= MAX_WIDTH_PX:
        raise EcgRenderConfigError(
            f"width_px must be between {MIN_WIDTH_PX} and {MAX_WIDTH_PX}"
        )
    if isinstance(config.height_px, bool) or not isinstance(config.height_px, int):
        raise EcgRenderConfigError("height_px must be an integer")
    if not MIN_HEIGHT_PX <= config.height_px <= MAX_HEIGHT_PX:
        raise EcgRenderConfigError(
            f"height_px must be between {MIN_HEIGHT_PX} and {MAX_HEIGHT_PX}"
        )
    _validate_bounded_number(
        "paper_speed_mm_s",
        config.paper_speed_mm_s,
        MIN_PAPER_SPEED_MM_S,
        MAX_PAPER_SPEED_MM_S,
    )
    _validate_bounded_number(
        "voltage_gain_mm_mv",
        config.voltage_gain_mm_mv,
        MIN_VOLTAGE_GAIN_MM_MV,
        MAX_VOLTAGE_GAIN_MM_MV,
    )
    if not isinstance(config.center_baseline, bool):
        raise EcgRenderConfigError("center_baseline must be a boolean")


def _validate_bounded_number(name: str, value: object, lower: float, upper: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EcgRenderConfigError(f"{name} must be numeric")
    numeric = float(value)
    if not isfinite(numeric) or not lower <= numeric <= upper:
        raise EcgRenderConfigError(f"{name} must be finite and between {lower} and {upper}")


def _validate_waveform(waveform: EcgWaveform) -> None:
    if not isinstance(waveform, EcgWaveform):
        raise EcgRenderError("waveform must be an EcgWaveform")
    frequency = waveform.sampling_frequency_hz
    if (
        isinstance(frequency, bool)
        or not isinstance(frequency, (int, float))
        or not isfinite(float(frequency))
        or frequency <= 0
    ):
        raise EcgRenderError("waveform sampling frequency must be finite and positive")
    leads = tuple(channel.lead for channel in waveform.channels)
    if leads != CANONICAL_LEADS:
        raise EcgRenderError("waveform channels must use canonical 12-lead order")
    for channel in waveform.channels:
        if not channel.samples_mv:
            raise EcgRenderError(f"lead {channel.lead} has no samples")
        if len(channel.samples_mv) > MAX_SAMPLES_PER_LEAD:
            raise EcgRenderError(
                f"lead {channel.lead} exceeds the {MAX_SAMPLES_PER_LEAD} sample limit"
            )
        duration = len(channel.samples_mv) / float(frequency)
        if duration > MAX_RENDER_DURATION_SECONDS:
            raise EcgRenderError(
                f"lead {channel.lead} exceeds the "
                f"{MAX_RENDER_DURATION_SECONDS:g}-second render limit"
            )
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(float(value))
            for value in channel.samples_mv
        ):
            raise EcgRenderError(f"lead {channel.lead} contains a non-finite sample")


def _display_samples(samples: tuple[float, ...], center: bool) -> tuple[float, ...]:
    if not center:
        return samples
    baseline = median(samples)
    return tuple(value - baseline for value in samples)


def _configure_grid(axis: object, duration: float, speed: float, gain: float) -> None:
    # Major lines represent five nominal millimetres and minor lines one.
    x_major = 5.0 / speed
    x_minor = 1.0 / speed
    y_major = 5.0 / gain
    y_minor = 1.0 / gain
    axis.set_xticks(_ticks(0.0, duration, x_major))
    axis.set_xticks(_ticks(0.0, duration, x_minor), minor=True)
    low, high = axis.get_ylim()
    axis.set_yticks(_ticks(low, high, y_major))
    axis.set_yticks(_ticks(low, high, y_minor), minor=True)
    axis.grid(which="major", color="#e8a2a2", linewidth=0.6)
    axis.grid(which="minor", color="#f5d0d0", linewidth=0.3)


def _ticks(start: float, stop: float, interval: float) -> tuple[float, ...]:
    count = int(ceil((stop - start) / interval))
    return tuple(start + index * interval for index in range(count + 1))
