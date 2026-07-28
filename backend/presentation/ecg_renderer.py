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

    width_px: int = 1200
    height_px: int = 1600
    paper_speed_mm_s: float = 25.0
    voltage_gain_mm_mv: float = 10.0
    center_baseline: bool = False


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
    _RENDER_LOCK.acquire()
    try:
        figure = Figure(
            figsize=(config.width_px / FIGURE_DPI, config.height_px / FIGURE_DPI),
            dpi=FIGURE_DPI,
            facecolor="white",
        )
        canvas = FigureCanvasSVG(figure)
        axes = figure.subplots(6, 2, squeeze=False)
        channels = {channel.lead: channel for channel in waveform.channels}

        for index, lead in enumerate(CANONICAL_LEADS):
            axis = axes[index % 6][index // 6]
            samples = channels[lead].samples_mv
            display_samples = _display_samples(samples, config.center_baseline)
            sample_count = len(display_samples)
            times = tuple(
                sample_index / waveform.sampling_frequency_hz
                for sample_index in range(sample_count)
            )
            duration = max(sample_count / waveform.sampling_frequency_hz, 1e-9)

            axis.plot(times, display_samples, color="#111111", linewidth=0.7)
            axis.set_xlim(0.0, duration)
            _set_voltage_limits(axis, display_samples, config.voltage_gain_mm_mv)
            _configure_grid(
                axis,
                duration,
                config.paper_speed_mm_s,
                config.voltage_gain_mm_mv,
            )
            axis.text(
                0.01,
                0.94,
                lead,
                transform=axis.transAxes,
                ha="left",
                va="top",
                fontsize=10,
                fontweight="bold",
                color="#111111",
            )
            axis.tick_params(labelbottom=False, labelleft=False, length=0)
            for spine in axis.spines.values():
                spine.set_visible(False)

        figure.subplots_adjust(
            left=0.035, right=0.985, top=0.975, bottom=0.055, wspace=0.08, hspace=0.18
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
        canvas.print_svg(buffer, metadata={"Description": DISCLAIMER})
        return RenderedEcg(buffer.getvalue())
    except EcgRenderConfigError:
        raise
    except Exception as exc:
        raise EcgRenderError("Unable to render ECG waveform") from exc
    finally:
        if figure is not None:
            figure.clear()
        buffer.close()
        _RENDER_LOCK.release()


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


def _set_voltage_limits(axis: object, samples: tuple[float, ...], gain: float) -> None:
    # Five nominal millimetres per major division. At the conventional default
    # gain this is 0.5 mV per division.
    major_mv = 5.0 / gain
    lower = min(samples)
    upper = max(samples)
    padding = major_mv
    low_limit = major_mv * (int((lower - padding) // major_mv))
    high_limit = major_mv * ceil((upper + padding) / major_mv)
    if low_limit == high_limit:
        high_limit += major_mv
    axis.set_ylim(low_limit, high_limit)


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
