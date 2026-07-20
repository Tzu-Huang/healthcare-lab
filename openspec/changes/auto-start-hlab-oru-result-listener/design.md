## Context

ZAC-45 established a single persisted OIE Settings profile with listener host, port, MLLP framing, and auto-start intent. The current `OieResultListener` already owns the socket and daemon thread, but `OieWorkflowService.start_listener()` takes request-body or Flask configuration values and composition never starts the listener. Status reports only a running boolean and error string. A failed manual bind returns an HTTP validation error, while there is no startup degradation contract.

The application uses a lazy WSGI entrypoint, but tests and other callers also construct Flask applications directly. Automatic runtime side effects therefore need an explicit composition seam so production defaults to auto-start while isolated application tests can supply controlled listener doubles or disable runtime activation. The current deployment is a single local lab-app process; coordinating ownership across WSGI workers or replicas is outside this change.

## Goals / Non-Goals

**Goals:**

- Use persisted Settings as the only source for listener lifecycle operations.
- Auto-start once per composed application process without blocking web startup on failure.
- Keep Start and Retry idempotent, make Stop temporary, and expose stopped, running, or degraded status with an actionable error.
- Preserve the existing socket receive, ORU processing, ACK, persistence, duplicate, and matching paths.
- Tell an operator when a successful Settings save changed listener intent that is not yet active.
- Keep runtime construction and frontend behavior testable without binding a real port.

**Non-Goals:**

- Coordinating listener ownership across multiple workers, replicas, or hosts.
- Automatically restarting a running listener when Settings are saved.
- Changing auto-start intent when Stop is pressed.
- Implementing OIE Channel mutation, HLAB pull/fetch, the complete ZAC-50 managed-Channel workspace, or new ORU semantics.

## Decisions

### Adapt persisted listener settings through a narrow private configuration port

The Settings repository will expose a private listener configuration projection containing host, port, MLLP framing, and auto-start. Lifecycle coordination will consume that projection rather than Flask config, public password-safe serialization, or request-body overrides. Start and Retry will always reload the projection immediately before attempting a bind.

Passing the complete public profile was rejected because runtime should not receive Management API or managed-Channel data. Keeping Flask config fallback was rejected because it creates two sources of truth.

### Keep persistence and runtime transitions separate

`PUT /api/oie/settings` will continue to persist desired state atomically and will not start, stop, or reconfigure the listener. When listener fields differ from the previously persisted values, the response will identify that the listener runtime has not applied the new intent. The modular Settings state/view will retain a visible reminder directing the operator to Retry/Start or restart lab-app; refreshing ordinary page data alone does not claim that the socket was reconfigured.

Automatically restarting on Save was rejected because it can interrupt in-flight ORU delivery and contradicts the ZAC-45 persistence boundary. Silently saving without a reminder was rejected because the visible desired settings could disagree with the bound socket.

### Model lifecycle state explicitly and retain the last attempted configuration

Listener status will expose a stable state of `stopped`, `running`, or `degraded`, the effective or last-attempted endpoint and framing, and an actionable `lastError`. A bind/start failure records `degraded` and returns control to composition; successful Start or Retry clears the error. Repeated Start or Retry for an already-running listener with the same persisted configuration returns the existing status without allocating another socket or thread. A request to apply changed settings while running requires Stop first.

Inferring degradation only from `running: false` plus a non-empty string was rejected because stopped-by-operator and failed-to-bind are different operational states.

### Auto-start is a best-effort composition action with an injection seam

After repositories, listener, lifecycle coordination, and API dependencies exist, application composition will read persisted intent and perform exactly one best-effort auto-start. Disabled auto-start leaves the listener stopped. Failure is captured in listener status and must not escape from `create_app` or prevent Blueprint registration. Runtime construction/startup dependencies will be injectable so tests can assert startup behavior without binding port `6665`.

Starting on the first HTTP request was rejected because result delivery must not depend on prior UI traffic and concurrent first requests complicate once-only behavior. An uncontrolled bind in every test application was rejected because it creates nondeterministic port conflicts.

### Keep Stop process-local and expose Retry explicitly

Stop closes the current socket/thread but does not persist `autoStart=false`; the next process start reapplies saved intent. Retry is an explicit API operation with the same persisted-settings behavior as Start, intended to recover from `degraded` after configuration or port ownership is corrected. Neither endpoint accepts endpoint overrides.

Mutating Settings from Stop was rejected because an operational action must not silently alter restart policy. Retaining request-body overrides was rejected because Settings is the designated configuration surface.

### Preserve single-process ownership as a documented constraint

The listener remains protected only by its in-process lock. Deployment and operator documentation will state that exactly one lab-app process may own the configured endpoint. Multi-worker or multi-replica coordination requires a later distributed ownership design.

## Risks / Trade-offs

- [A stale process remains bound after Settings are saved] → Keep Save side-effect free, return the unapplied-state signal, and show a persistent Retry/restart reminder.
- [Auto-start causes test or local port conflicts] → Inject listener/startup behavior and use ephemeral ports or fakes in lifecycle tests.
- [Two lab-app processes race for the same endpoint] → The loser becomes degraded without affecting HTTP availability; document the single-process limitation.
- [A listener thread dies after a successful bind] → Preserve its error in explicit degraded status and allow Retry after cleanup.
- [ZAC-48 and ZAC-49 both touch OIE API/composition] → Keep listener endpoints and lifecycle dependencies narrow so integration conflicts remain mechanical.

## Migration Plan

1. Add the private persisted-listener configuration projection and lifecycle/status contracts without changing stored schema.
2. Rewire Start/Stop/Status, add Retry, and add the Settings unapplied-state response/UI reminder.
3. Enable best-effort auto-start in composition after all dependencies are registered.
4. Deploy as a single lab-app process. Existing seeded profiles auto-start on `0.0.0.0:6665`; operators with a port conflict see degraded status and can correct Settings then Retry.
5. Rollback restores manual startup behavior; no data migration or persisted profile rewrite is required.

## Open Questions

None. Save remains side-effect free, Stop is process-local, Start/Retry use persisted Settings, and startup failure degrades only the listener.
