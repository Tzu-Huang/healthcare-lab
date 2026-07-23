"""Bounded startup convergence for Healthcare Lab-managed OIE Channels."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from backend.domain.oie_channel_lifecycle import ManagedChannelType


LOGGER = logging.getLogger(__name__)
BOOTSTRAP_ACTOR = "startup-bootstrap"
READY_STATES = {"STARTED", "DEPLOYED"}


class OieManagedChannelBootstrap:
    def __init__(
        self,
        lifecycle: Any,
        *,
        timeout_seconds: float,
        retry_interval_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        logger: logging.Logger = LOGGER,
        attempt_observer: Callable[[int], None] | None = None,
    ) -> None:
        self.lifecycle = lifecycle
        self.timeout_seconds = float(timeout_seconds)
        self.retry_interval_seconds = float(retry_interval_seconds)
        self.clock = clock
        self.sleeper = sleeper
        self.logger = logger
        self.attempt_observer = attempt_observer or (lambda _attempts: None)

    def run(self) -> dict[str, Any]:
        started = self.clock()
        attempts = 0
        while True:
            attempts += 1
            try:
                self.attempt_observer(attempts)
            except Exception:
                self.logger.error("OIE startup bootstrap attempt evidence is unavailable.")
            try:
                inventory = self.lifecycle.inspect()
                break
            except Exception as exc:
                category = self._category(exc)
                remaining = self.timeout_seconds - (self.clock() - started)
                if remaining <= 0:
                    channels = [
                        self._durable_outcome(kind.value, "unavailable", "timeout", category)
                        for kind in ManagedChannelType
                    ]
                    self.logger.warning(
                        "OIE startup bootstrap timed out attempts=%s category=%s",
                        attempts, category,
                    )
                    return {"outcome": "timeout", "attempts": attempts, "errorCategory": category, "channels": channels}
                self.sleeper(min(self.retry_interval_seconds, remaining))

        indexed = {
            item.get("logicalType"): item
            for item in inventory
            if item.get("logicalType")
        }
        outcomes = [self._reconcile(kind.value, indexed.get(kind.value)) for kind in ManagedChannelType]
        overall = "success" if all(item["outcome"] in {"success", "no-op", "blocked"} for item in outcomes) else "partial-failure"
        self.logger.info("OIE startup bootstrap completed attempts=%s outcome=%s", attempts, overall)
        return {"outcome": overall, "attempts": attempts, "errorCategory": "", "channels": outcomes}

    def _reconcile(self, logical_type: str, snapshot: dict[str, Any] | None) -> dict[str, Any]:
        classification = str((snapshot or {}).get("classification") or "conflict").lower()
        if classification == "recoverable":
            try:
                recovered = self.lifecycle.recover_mapping(logical_type, actor=BOOTSTRAP_ACTOR)
                refreshed = next(
                    (item for item in self.lifecycle.inspect() if item.get("logicalType") == logical_type),
                    None,
                )
                refreshed_classification = str((refreshed or {}).get("classification") or "conflict").lower()
                if refreshed_classification not in {"unchanged", "drifted"}:
                    return self._durable_outcome(
                        logical_type, refreshed_classification, "failure", "recovery-readback"
                    )
                return self._outcome(
                    logical_type, classification, "success",
                    status=str(recovered.get("status") or (refreshed or {}).get("status") or ""),
                )
            except Exception as exc:
                category = self._category(exc)
                outcome = "blocked" if category in {"recovery-blocked", "stale-recovery"} else "failure"
                return self._durable_outcome(logical_type, classification, outcome, category)
        if classification == "unchanged":
            return self._durable_outcome(logical_type, classification, "no-op")
        if classification != "missing":
            return self._durable_outcome(logical_type, classification, "blocked")
        try:
            create_preview = self.lifecycle.preview(logical_type, "create", actor=BOOTSTRAP_ACTOR)
            if not create_preview.get("permitted") or not create_preview.get("previewToken"):
                return self._outcome(logical_type, classification, "blocked", "stale-preview")
            created = self.lifecycle.execute(
                logical_type, "create", create_preview["previewToken"], actor=BOOTSTRAP_ACTOR
            )
            if created.get("outcome") != "success":
                return self._outcome(logical_type, classification, "failure", self._result_category(created))

            deploy_preview = self.lifecycle.preview(logical_type, "deploy", actor=BOOTSTRAP_ACTOR)
            if not deploy_preview.get("permitted") or not deploy_preview.get("previewToken"):
                return self._outcome(logical_type, classification, "partial-failure", "deploy-not-permitted")
            deployed = self.lifecycle.execute(
                logical_type, "deploy", deploy_preview["previewToken"], actor=BOOTSTRAP_ACTOR
            )
            status = str(deployed.get("status") or "").upper()
            if deployed.get("outcome") != "success" or status not in READY_STATES:
                return self._outcome(
                    logical_type, classification, "partial-failure",
                    self._result_category(deployed) or "status-verification",
                )
            return self._outcome(logical_type, classification, "success", status=status)
        except Exception as exc:
            return self._outcome(logical_type, classification, "failure", self._category(exc))

    @staticmethod
    def _outcome(logical_type, classification, outcome, category="", *, status=""):
        return {
            "logicalType": logical_type,
            "classification": classification,
            "outcome": outcome,
            "errorCategory": category,
            "status": status,
        }

    def _durable_outcome(self, logical_type, classification, outcome, category=""):
        try:
            self.lifecycle.record_bootstrap_outcome(
                logical_type, classification, outcome, error_category=category
            )
        except Exception as exc:
            self.logger.error(
                "OIE startup bootstrap evidence failed logical_type=%s category=%s",
                logical_type, self._category(exc),
            )
            return self._outcome(logical_type, classification, "failure", "audit-unavailable")
        return self._outcome(logical_type, classification, outcome, category)

    @staticmethod
    def _category(exc: Exception) -> str:
        category = getattr(exc, "category", "failure")
        return str(getattr(category, "value", category) or "failure")[:80]

    @staticmethod
    def _result_category(result: dict[str, Any]) -> str:
        failed = next((step for step in reversed(result.get("steps", [])) if step.get("status") == "failed"), {})
        return str(failed.get("errorCategory") or "")[:80]
