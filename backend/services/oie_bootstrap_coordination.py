"""Observable, single-run coordination for managed OIE Channel bootstrap."""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable, Mapping
from typing import Any

from backend.domain.timestamps import now_iso


LOGGER = logging.getLogger(__name__)
RECOVERABLE_CATEGORIES = frozenset({
    "connection",
    "server",
    "timeout",
    "unexpected-response",
})
POLICY_CLASSIFICATIONS = frozenset({"conflict", "drifted", "external"})
GUIDANCE = {
    "disabled": "enable-bootstrap",
    "running": "wait-for-bootstrap",
    "connection": "verify-oie-readiness",
    "server": "verify-oie-readiness",
    "timeout": "retry-when-oie-ready",
    "unexpected-response": "verify-oie-version",
    "authentication": "verify-oie-credentials",
    "unsupported-version": "verify-oie-version",
    "conflict": "resolve-ownership-conflict",
    "drifted": "review-managed-channel-drift",
    "external": "review-external-channel",
    "interrupted": "retry-bootstrap",
    "status-unavailable": "verify-local-database",
    "failure": "inspect-bootstrap-diagnostics",
}


class BootstrapCommandError(RuntimeError):
    """Stable command failure returned by the HTTP adapter."""

    def __init__(self, category: str, detail: str, *, status_code: int = 409):
        self.category = category
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class OieBootstrapCoordinator:
    """Own bootstrap execution state without coupling status reads to OIE."""

    def __init__(
        self,
        bootstrap: Any,
        repository: Any,
        *,
        mode: str,
        thread_factory: Callable[..., object],
        run_lock: Any,
        state_lock: Any,
        timestamp_factory: Callable[[], str] = now_iso,
        run_id_factory: Callable[[], str] | None = None,
        logger: logging.Logger = LOGGER,
    ) -> None:
        self.bootstrap = bootstrap
        self.repository = repository
        self.mode = str(mode)
        self.thread_factory = thread_factory
        self.timestamp_factory = timestamp_factory
        self.run_id_factory = run_id_factory or (lambda: secrets.token_hex(12))
        self.logger = logger
        self._run_lock = run_lock
        self._active_run_id = ""
        self._state_lock = state_lock

    def status(self) -> dict[str, Any]:
        try:
            with self._state_lock:
                active_run_id = self._active_run_id
            value = self.repository.latest_status(current_run_id=active_run_id)
        except Exception:
            return self._unavailable_status()
        if value is None:
            return {
                "mode": self.mode,
                "state": "disabled" if self.mode == "off" else "idle",
                "trigger": "",
                "startedAt": "",
                "completedAt": "",
                "attempts": 0,
                "outcome": "disabled" if self.mode == "off" else "not-run",
                "errorCategory": "",
                "guidanceCode": "enable-bootstrap" if self.mode == "off" else "",
                "retryEligible": False,
                "channels": [],
            }
        projected = dict(value)
        projected["mode"] = self.mode
        projected["retryEligible"] = self._retry_eligible(projected)
        if not projected.get("guidanceCode"):
            projected["guidanceCode"] = self._guidance(projected)
        return projected

    def start_startup(self) -> object:
        return self._start("startup", require_eligible=False)

    def retry(self) -> dict[str, Any]:
        thread = self._start("retry", require_eligible=True)
        status = self.status()
        status["accepted"] = True
        status["workerStarted"] = bool(getattr(thread, "started", True))
        return status

    def _start(self, trigger: str, *, require_eligible: bool) -> object:
        if self.mode == "off":
            raise BootstrapCommandError("disabled", "OIE bootstrap mode is off.", status_code=409)
        if not self._run_lock.acquire(blocking=False):
            raise BootstrapCommandError("already-running", "OIE bootstrap is already running.", status_code=409)
        run_id = self.run_id_factory()
        try:
            if require_eligible:
                latest = self.status()
                if not latest.get("retryEligible"):
                    raise BootstrapCommandError(
                        "retry-not-eligible",
                        "The latest bootstrap outcome is not eligible for Retry.",
                        status_code=409,
                    )
            self.repository.start_run(
                run_id=run_id,
                trigger=trigger,
                mode=self.mode,
                started_at=self.timestamp_factory(),
            )
            with self._state_lock:
                self._active_run_id = run_id
            self.bootstrap.attempt_observer = lambda attempts: self.repository.update_attempts(
                run_id, attempts
            )
            thread = self.thread_factory(
                target=lambda: self._execute(run_id),
                name="oie-managed-channel-bootstrap",
                daemon=True,
            )
            thread.start()
            return thread
        except BaseException:
            with self._state_lock:
                if self._active_run_id == run_id:
                    self._active_run_id = ""
            self._run_lock.release()
            raise

    def _execute(self, run_id: str) -> None:
        try:
            result = self.bootstrap.run()
            category = str(result.get("errorCategory") or "")
            self.repository.complete_run(
                run_id,
                completed_at=self.timestamp_factory(),
                attempts=int(result.get("attempts") or 0),
                outcome=str(result.get("outcome") or "failure"),
                error_category=category,
                guidance_code=self._guidance(result),
                channels=[
                    {
                        **dict(channel),
                        "guidanceCode": self._channel_guidance(channel),
                    }
                    for channel in result.get("channels", [])
                    if isinstance(channel, Mapping)
                ],
            )
        except Exception:
            self.logger.exception("OIE bootstrap coordination failed with bounded status.")
            try:
                self.repository.complete_run(
                    run_id,
                    completed_at=self.timestamp_factory(),
                    attempts=0,
                    outcome="failure",
                    error_category="failure",
                    guidance_code=GUIDANCE["failure"],
                    channels=[
                        {
                            "logicalType": logical_type,
                            "classification": "unavailable",
                            "outcome": "failure",
                            "status": "",
                            "errorCategory": "failure",
                            "guidanceCode": GUIDANCE["failure"],
                        }
                        for logical_type in ("hlab-orm-to-ap", "hlab-oru-to-hlab")
                    ],
                )
            except Exception:
                self.logger.error("OIE bootstrap failure evidence could not be persisted.")
        finally:
            with self._state_lock:
                if self._active_run_id == run_id:
                    self._active_run_id = ""
            self._run_lock.release()

    def _retry_eligible(self, status: Mapping[str, Any]) -> bool:
        if self.mode == "off" or status.get("state") == "running":
            return False
        if status.get("state") == "interrupted":
            return True
        if str(status.get("errorCategory") or "") in RECOVERABLE_CATEGORIES:
            return True
        return any(
            str(item.get("errorCategory") or "") in RECOVERABLE_CATEGORIES
            for item in status.get("channels", [])
            if isinstance(item, Mapping)
        )

    @staticmethod
    def _guidance(result: Mapping[str, Any]) -> str:
        category = str(result.get("errorCategory") or "")
        if category:
            return GUIDANCE.get(category, GUIDANCE["failure"])
        if result.get("state") == "interrupted":
            return GUIDANCE["interrupted"]
        for item in result.get("channels", []):
            if not isinstance(item, Mapping):
                continue
            classification = str(item.get("classification") or "")
            if classification in POLICY_CLASSIFICATIONS:
                return GUIDANCE[classification]
        return ""

    @staticmethod
    def _channel_guidance(channel: Mapping[str, Any]) -> str:
        category = str(channel.get("errorCategory") or "")
        classification = str(channel.get("classification") or "")
        if category:
            return GUIDANCE.get(category, GUIDANCE["failure"])
        return GUIDANCE.get(classification, "")

    def _unavailable_status(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "state": "unavailable",
            "trigger": "",
            "startedAt": "",
            "completedAt": "",
            "attempts": 0,
            "outcome": "status-unavailable",
            "errorCategory": "status-unavailable",
            "guidanceCode": GUIDANCE["status-unavailable"],
            "retryEligible": False,
            "channels": [],
        }
