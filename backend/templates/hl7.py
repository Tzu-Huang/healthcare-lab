"""Shared pure HL7 v2 rendering primitives."""

from __future__ import annotations

from typing import Any


HL7_V2_MSH_SUFFIX = "2.5.1||||||UNICODE UTF-8"


def escape(value: Any) -> str:
    text = str(value if value is not None else "")
    return (text.replace("\\", "\\E\\").replace("|", "\\F\\").replace("^", "\\S\\")
            .replace("&", "\\T\\").replace("~", "\\R\\").replace("\r\n", "\n")
            .replace("\r", "\n").replace("\n", "\\.br\\"))


def escape_composite(value: Any) -> str:
    return "^".join(escape(component) for component in str(value if value is not None else "").split("^"))
