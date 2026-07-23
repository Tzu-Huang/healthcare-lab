"""Secret-safe SQLite persistence for OIE bootstrap operational evidence."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from sqlite3 import Connection
from threading import RLock
from typing import Any

from backend.domain.oie_channel_lifecycle import ManagedChannelType

ConnectionFactory = Callable[[], AbstractContextManager[Connection]]

BOOTSTRAP_TRIGGERS = frozenset({"startup", "retry"})
BOOTSTRAP_MODES = frozenset({"create-missing", "off"})
BOOTSTRAP_OUTCOMES = frozenset(
    {"success", "partial-failure", "timeout", "failure", "disabled", "interrupted"}
)
CHANNEL_CLASSIFICATIONS = frozenset(
    {"missing", "recoverable", "unchanged", "drifted", "conflict", "external", "unavailable"}
)
CHANNEL_OUTCOMES = frozenset(
    {"success", "no-op", "blocked", "failure", "partial-failure", "timeout"}
)
CHANNEL_STATUSES = frozenset({"", "STARTED", "DEPLOYED", "STOPPED", "UNDEPLOYED", "UNKNOWN"})
ERROR_CATEGORIES = frozenset(
    {
        "",
        "authentication",
        "permission",
        "tls",
        "connection",
        "timeout",
        "revision-conflict",
        "validation",
        "unsupported-version",
        "server",
        "unexpected-response",
        "unauthenticated",
        "failure",
        "recovery-readback",
        "recovery-blocked",
        "stale-recovery",
        "stale-preview",
        "deploy-not-permitted",
        "status-verification",
        "audit-unavailable",
        "audit-failure",
        "ownership",
        "disabled",
        "interrupted",
        "status-unavailable",
        "policy-blocked",
        "database",
    }
)
GUIDANCE_CODES = frozenset(
    {
        "",
        "enable-bootstrap",
        "wait-for-bootstrap",
        "verify-oie-readiness",
        "retry-when-oie-ready",
        "verify-oie-version",
        "verify-oie-credentials",
        "resolve-ownership-conflict",
        "review-managed-channel-drift",
        "review-external-channel",
        "retry-bootstrap",
        "verify-local-database",
        "inspect-bootstrap-diagnostics",
    }
)
LOGICAL_TYPES = frozenset(kind.value for kind in ManagedChannelType)


class OieBootstrapStatusRepository:
    """Persist and project the latest bounded bootstrap run."""

    def __init__(self, connection_factory: ConnectionFactory, lock: RLock) -> None:
        self._connect = connection_factory
        self._lock = lock

    def start_run(
        self, *, run_id: str, trigger: str, mode: str, started_at: str
    ) -> None:
        values = {
            "run_id": self._required_text(run_id, "run_id", 128),
            "trigger": self._choice(trigger, "trigger", BOOTSTRAP_TRIGGERS),
            "mode": self._choice(mode, "mode", BOOTSTRAP_MODES),
            "started_at": self._required_text(started_at, "started_at", 40),
        }
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO oie_bootstrap_runs (
                    run_id, trigger, mode, state, started_at, completed_at,
                    attempts, outcome, error_category, guidance_code
                ) VALUES (?, ?, ?, 'running', ?, '', 0, '', '', '')""",
                (
                    values["run_id"],
                    values["trigger"],
                    values["mode"],
                    values["started_at"],
                ),
            )

    def update_attempts(self, run_id: str, attempts: int) -> None:
        run_id = self._required_text(run_id, "run_id", 128)
        attempts = self._attempts(attempts)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """UPDATE oie_bootstrap_runs SET attempts = ?
                WHERE run_id = ? AND state = 'running'""",
                (attempts, run_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(run_id)

    def complete_run(
        self,
        run_id: str,
        *,
        completed_at: str,
        attempts: int,
        outcome: str,
        error_category: str,
        guidance_code: str,
        channels: Sequence[Mapping[str, Any]],
    ) -> None:
        run_id = self._required_text(run_id, "run_id", 128)
        completed_at = self._required_text(completed_at, "completed_at", 40)
        attempts = self._attempts(attempts)
        outcome = self._choice(outcome, "outcome", BOOTSTRAP_OUTCOMES - {"interrupted"})
        error_category = self._choice(
            error_category, "error_category", ERROR_CATEGORIES
        )
        guidance_code = self._choice(
            guidance_code, "guidance_code", GUIDANCE_CODES
        )
        safe_channels = self._channels(channels)

        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """UPDATE oie_bootstrap_runs
                SET state = 'completed', completed_at = ?, attempts = ?,
                    outcome = ?, error_category = ?, guidance_code = ?
                WHERE run_id = ? AND state = 'running'""",
                (
                    completed_at,
                    attempts,
                    outcome,
                    error_category,
                    guidance_code,
                    run_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(run_id)
            for item in safe_channels:
                connection.execute(
                    """INSERT INTO oie_bootstrap_channel_outcomes (
                        run_id, logical_type, classification, outcome, status,
                        error_category, guidance_code
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        run_id,
                        item["logical_type"],
                        item["classification"],
                        item["outcome"],
                        item["status"],
                        item["error_category"],
                        item["guidance_code"],
                    ),
                )

    def latest_status(self, *, current_run_id: str = "") -> dict[str, Any] | None:
        current_run_id = self._bounded_text(
            current_run_id, "current_run_id", 128
        )
        with self._connect() as connection:
            row = connection.execute(
                """SELECT run_id, trigger, mode, state, started_at, completed_at,
                    attempts, outcome, error_category, guidance_code
                FROM oie_bootstrap_runs
                ORDER BY started_at DESC, run_id DESC LIMIT 1"""
            ).fetchone()
            if row is None:
                return None
            channels = connection.execute(
                """SELECT logical_type, classification, outcome, status,
                    error_category, guidance_code
                FROM oie_bootstrap_channel_outcomes
                WHERE run_id = ? ORDER BY logical_type COLLATE NOCASE""",
                (row["run_id"],),
            ).fetchall()

        stale = row["state"] == "running" and row["run_id"] != current_run_id
        return {
            "runId": row["run_id"],
            "trigger": row["trigger"],
            "mode": row["mode"],
            "state": "interrupted" if stale else row["state"],
            "startedAt": row["started_at"],
            "completedAt": row["completed_at"],
            "attempts": int(row["attempts"]),
            "outcome": "interrupted" if stale else row["outcome"],
            "errorCategory": row["error_category"],
            "guidanceCode": "retry-bootstrap" if stale else row["guidance_code"],
            "channels": [
                {
                    "logicalType": item["logical_type"],
                    "classification": item["classification"],
                    "outcome": item["outcome"],
                    "status": item["status"],
                    "errorCategory": item["error_category"],
                    "guidanceCode": item["guidance_code"],
                }
                for item in channels
            ],
        }

    @classmethod
    def _channels(
        cls, channels: Sequence[Mapping[str, Any]]
    ) -> list[dict[str, str]]:
        if not isinstance(channels, (list, tuple)):
            raise ValueError("channels must be a bounded sequence.")
        safe: list[dict[str, str]] = []
        for item in channels:
            if not isinstance(item, Mapping):
                raise ValueError("Each channel outcome must be a mapping.")
            unknown = set(item) - {
                "logicalType",
                "classification",
                "outcome",
                "status",
                "errorCategory",
                "guidanceCode",
            }
            if unknown:
                raise ValueError(
                    f"Channel outcome contains unsupported fields: {sorted(unknown)!r}."
                )
            safe.append(
                {
                    "logical_type": cls._choice(
                        item.get("logicalType"), "logicalType", LOGICAL_TYPES
                    ),
                    "classification": cls._choice(
                        item.get("classification"),
                        "classification",
                        CHANNEL_CLASSIFICATIONS,
                    ),
                    "outcome": cls._choice(
                        item.get("outcome"), "channel outcome", CHANNEL_OUTCOMES
                    ),
                    "status": cls._choice(
                        str(item.get("status") or "").upper(),
                        "status",
                        CHANNEL_STATUSES,
                    ),
                    "error_category": cls._choice(
                        item.get("errorCategory", ""),
                        "errorCategory",
                        ERROR_CATEGORIES,
                    ),
                    "guidance_code": cls._choice(
                        item.get("guidanceCode", ""),
                        "guidanceCode",
                        GUIDANCE_CODES,
                    ),
                }
            )
        logical_types = [item["logical_type"] for item in safe]
        if len(safe) != len(LOGICAL_TYPES) or set(logical_types) != LOGICAL_TYPES:
            raise ValueError(
                "channels must contain exactly one outcome for each canonical logical type."
            )
        return safe

    @staticmethod
    def _attempts(value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("attempts must be an integer.")
        if value < 0 or value > 10_000:
            raise ValueError("attempts must be between 0 and 10000.")
        return value

    @staticmethod
    def _bounded_text(value: Any, field: str, limit: int) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string.")
        value = value.strip()
        if len(value) > limit:
            raise ValueError(f"{field} exceeds its {limit}-character limit.")
        return value

    @classmethod
    def _required_text(cls, value: Any, field: str, limit: int) -> str:
        value = cls._bounded_text(value, field, limit)
        if not value:
            raise ValueError(f"{field} must not be empty.")
        return value

    @classmethod
    def _choice(cls, value: Any, field: str, allowed: frozenset[str]) -> str:
        value = cls._bounded_text(value, field, 80)
        if value not in allowed:
            raise ValueError(f"{field} is not an allowlisted value.")
        return value
