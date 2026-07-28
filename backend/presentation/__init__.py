"""Presentation-layer adapters for browser-facing application output."""

from .ecg_renderer import (
    EcgRenderConfig,
    EcgRenderConfigError,
    EcgRenderError,
    RenderedEcg,
    render_ecg,
)

__all__ = (
    "EcgRenderConfig",
    "EcgRenderConfigError",
    "EcgRenderError",
    "RenderedEcg",
    "render_ecg",
)
