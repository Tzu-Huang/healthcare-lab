"""Framework-independent boundary validation helpers."""

from __future__ import annotations

from typing import Any

from .errors import ValidationError


def require_http_url(value: Any, field: str) -> str:
    url = str(value or "").strip()
    if not url:
        raise ValidationError(f"{field} is required.")
    if not url.startswith(("http://", "https://")):
        raise ValidationError(f"{field} must start with http:// or https://.")
    return url.rstrip("/")
