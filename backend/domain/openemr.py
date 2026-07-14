"""Framework-independent OpenEMR configuration defaults and parsing."""

from __future__ import annotations

from typing import Any


OPENEMR_DEFAULT_ALLOWED_PROCEDURE_CODES = ("1001",)


def parse_openemr_allowed_procedure_codes(value: Any) -> tuple[str, ...]:
    if value is None:
        return OPENEMR_DEFAULT_ALLOWED_PROCEDURE_CODES
    if isinstance(value, str):
        codes = [item.strip() for item in value.replace(";", ",").split(",")]
    else:
        codes = [str(item).strip() for item in value]
    return tuple(code for code in codes if code)
