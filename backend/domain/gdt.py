"""Framework-independent GDT bridge path mapping."""

from pathlib import Path


def ensure_gdt_bridge_dirs(base_path: str | Path) -> dict[str, Path]:
    root = Path(base_path)
    return {
        "root": root,
        "inbox": root / "inbox",
        "outbox": root / "outbox",
        "processed": root / "processed",
        "processing": root / "processing",
        "error": root / "error",
        "reports": root / "reports",
        "archive": root / "archive",
    }
