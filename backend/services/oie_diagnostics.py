"""Secret-safe, independently degradable OIE runtime diagnostics."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any, Protocol

from backend.domain.oie_management import OieManagementError


class ManagementClientPort(Protocol):
    def login(self): ...
    def close(self) -> None: ...
    def current_user(self): ...
    def channel_status(self, channel_id: str): ...
    def destination_statistics(self, channel_id: str): ...
    def ports_in_use(self): ...


GUIDANCE = {
    "management-api": "Verify the saved OIE URL, TLS policy, credentials, and OIE availability.",
    "hlab-listener": "Retry the HLAB listener after resolving its bind address or port conflict.",
    "managed-channel": "Apply or redeploy the managed ORU Channel in OIE.",
    "port-contract": "Correct the endpoint ownership; recreate containers only for published-port changes.",
    "delivery-state": "Inspect retained OIE messages and restore the destination before retrying delivery.",
}


class OieRuntimeDiagnosticService:
    def __init__(
        self,
        management_client: Callable[[], ManagementClientPort],
        listener_status: Callable[[], Mapping[str, Any]],
        port_contract: Callable[[], Mapping[str, Any]],
        *,
        channel_id: str | Callable[[], str],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._management_client = management_client
        self._listener_status = listener_status
        self._port_contract = port_contract
        self._channel_id = channel_id
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def diagnose(self) -> dict[str, Any]:
        observed_at = self._timestamp()
        probes = [
            self._probe("management-api", self._management),
            self._probe("hlab-listener", self._listener),
            self._probe("managed-channel", self._channel),
            self._probe("port-contract", self._ports),
            self._probe("delivery-state", self._delivery),
        ]
        state = "healthy" if all(p["state"] == "healthy" for p in probes) else "degraded"
        return {"state": state, "observedAt": observed_at, "probes": probes}

    def _timestamp(self) -> str:
        value = self._clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def _probe(self, layer: str, operation: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            result = operation()
        except OieManagementError as exc:
            result = {
                "state": "unavailable", "category": exc.category.value,
                "summary": f"{layer} probe is unavailable.",
            }
        except Exception:
            result = {
                "state": "unavailable", "category": "probe-failure",
                "summary": f"{layer} probe failed.",
            }
        return {
            "layer": layer,
            "state": result["state"],
            "category": result["category"],
            "summary": result["summary"][:160],
            "observedAt": self._timestamp(),
            "guidance": GUIDANCE[layer],
            **({"evidence": result["evidence"]} if "evidence" in result else {}),
        }

    def _management(self) -> dict[str, Any]:
        self._with_client(lambda client: client.current_user())
        return {"state": "healthy", "category": "connected", "summary": "OIE Management API is reachable."}

    def _listener(self) -> dict[str, Any]:
        status = self._listener_status()
        state = str(status.get("state") or "unknown").lower()
        running = bool(status.get("running")) or state == "running"
        category = "listening" if running else ("port-conflict" if state == "bind-failed" else "not-listening")
        return {
            "state": "healthy" if running else "degraded", "category": category,
            "summary": "HLAB result listener is running." if running else "HLAB result listener is not running.",
            "evidence": {"state": state},
        }

    def _channel(self) -> dict[str, Any]:
        channel_id = self._resolved_channel_id()
        if not channel_id:
            return {"state": "unavailable", "category": "not-configured", "summary": "Managed ORU Channel identity is not configured."}
        status = self._with_client(lambda client: client.channel_status(channel_id))
        deployed = str(status.status).upper() in {"STARTED", "DEPLOYED"}
        return {
            "state": "healthy" if deployed else "degraded",
            "category": "deployed" if deployed else "not-deployed",
            "summary": "Managed ORU Channel is deployed." if deployed else "Managed ORU Channel is not deployed.",
            "evidence": {"state": str(status.status).upper()},
        }

    def _ports(self) -> dict[str, Any]:
        contract = self._port_contract()
        valid = bool(contract.get("valid"))
        conflicts = contract.get("conflicts")
        count = len(conflicts) if isinstance(conflicts, (list, tuple)) else int(bool(conflicts))
        return {
            "state": "healthy" if valid else "degraded",
            "category": "valid" if valid else "port-conflict",
            "summary": "Runtime port ownership is valid." if valid else "Runtime port ownership has a conflict.",
            "evidence": {"conflictCount": count},
        }

    def _delivery(self) -> dict[str, Any]:
        channel_id = self._resolved_channel_id()
        if not channel_id:
            return {"state": "unavailable", "category": "not-configured", "summary": "OIE destination statistics are unavailable."}
        stats = self._with_client(
            lambda client: client.destination_statistics(channel_id)
        )
        availability = str(stats.values.get("availability") or "unavailable")
        if availability != "available":
            return {
                "state": "unavailable", "category": availability,
                "summary": "OIE destination statistics are unavailable.",
            }
        queued, errors = int(stats.values["queued"]), int(stats.values["errors"])
        degraded = errors > 0
        return {
            "state": "degraded" if degraded else "healthy",
            "category": "destination-errors" if degraded else "available",
            "summary": "OIE destination has delivery errors." if degraded else "OIE destination statistics are available.",
            "evidence": {"queued": queued, "errors": errors},
        }

    def _with_client(self, operation: Callable[[ManagementClientPort], Any]) -> Any:
        client = self._management_client()
        try:
            client.login()
            return operation(client)
        finally:
            client.close()

    def _resolved_channel_id(self) -> str:
        value = self._channel_id() if callable(self._channel_id) else self._channel_id
        return str(value or "").strip()
