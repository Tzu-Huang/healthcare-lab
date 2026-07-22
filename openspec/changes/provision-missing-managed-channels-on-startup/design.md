## Context

Healthcare Lab already compiles exactly two managed OIE 4.5.2 Channel templates and classifies live inventory as missing, unchanged, drifted, conflicted, or external. Its guarded lifecycle service creates one missing Channel, rediscovers and persists its identity, and separately deploys a single owned Channel. Today a new settings profile has no mapping rows and runtime activation starts only the HLAB result listener. Production exposes a lazy WSGI wrapper, so concrete application construction can occur on the first HTTP request.

ZAC-67 must compose those capabilities into a best-effort startup workflow without weakening ownership checks, updating drift, blocking HTTP availability, or exposing secrets. The supported deployment uses one Gunicorn worker; multi-replica coordination is out of scope.

## Goals / Non-Goals

**Goals:**

- Persist canonical desired mapping intent on a fresh profile without overwriting saved operator settings.
- Run one bounded `create-missing` attempt per concrete lab-app runtime, independently of browser traffic.
- Wait through normal OIE startup delay and keep lab-app available on timeout or failure.
- Create and deploy only missing managed Channels through refreshed single-target guards.
- Produce durable, secret-safe evidence attributed to `startup-bootstrap`.

**Non-Goals:**

- Automatically update drifted fields, adopt same-name external Channels, resolve conflicts, delete, undeploy, or redeploy existing Channels.
- Automatically start an existing unchanged but stopped Channel; deployment is coupled only to a Channel created by this bootstrap run.
- Add multi-replica leader election or recover independently deleted lab-app/OIE volumes.
- Change browser lifecycle APIs or expose arbitrary bootstrap actions.

## Decisions

### Seed canonical mapping intent through repeatable database maintenance

The OIE profile maintenance step will insert missing logical mapping rows for both canonical routes with empty OIE identity/revision and complete desired configuration. Inserts will be conflict-safe and will never replace existing rows or operator-edited settings. This makes desired state visible before OIE is reachable and gives create persistence a stable compare-and-update target.

Alternative considered: let successful lifecycle creation insert mapping rows. Rejected because a fresh profile would not expose its complete desired route contract while OIE is unavailable and configuration seeding would remain implicit.

### Use a dedicated bootstrap coordinator over guarded lifecycle primitives

A runtime-neutral coordinator will own readiness retry, per-Channel sequencing, overall deadline, outcomes, and logging. It will call lifecycle operations with a `startup-bootstrap` actor, retaining state-bound preview/revalidation or an equivalent internal guarded entry point. Each newly created Channel is read back and persisted before a fresh guarded deploy and status readback. The coordinator will inspect both logical types individually so one conflict or failure does not broaden mutation or prevent safe handling of the other.

Alternative considered: call the Management API client directly. Rejected because that would duplicate ownership classification, stale-state protection, identity persistence, and audit behavior.

### Retry readiness failures, not lifecycle policy outcomes

Each attempt will establish an authenticated, supported OIE Management API session and obtain complete inventory. Transport, authentication availability, and transient server readiness failures are retried at the configured interval until the overall timeout. Once inventory is readable, missing/unchanged/drifted/conflict classifications are terminal for that runtime; mutation failures are recorded but not repeatedly replayed in the same startup run.

Alternative considered: retry every failed mutation until the deadline. Rejected because uncertain partial creation or persistence outcomes require a new explicit inventory reconciliation, and repeated writes make startup behavior harder to reason about.

### Start asynchronously at concrete application construction

When runtime activation is enabled and mode is `create-missing`, composition will start one named daemon worker after repositories and lifecycle services are ready. Bootstrap work will not block returning the Flask application or its health endpoints. The production entrypoint will eagerly construct the concrete application before serving requests instead of relying on first-request lazy construction; import-safe test seams remain available through explicit factories and `activate_runtime=False`.

Alternative considered: start from `before_request` or a browser GET. Rejected because it violates process-start semantics and makes provisioning depend on user traffic.

### Keep configuration explicit and bounded

Environment-backed configuration will accept only `create-missing` or `off`, default to `create-missing`, and validate positive overall timeout and retry interval values. Compose and `.env.example` will document the settings. Invalid configuration will fail application configuration validation rather than silently selecting a broader behavior.

### Attribute audits without expanding their payload

Lifecycle event construction will accept a bounded actor supplied by the caller, defaulting existing operator flows to `local-operator`. Bootstrap uses `startup-bootstrap`; persisted fields remain on the existing allowlist and contain no credentials, Channel XML, HL7, PHI, or upstream response bodies. Logs will use logical type, classification, bounded outcome/category, and elapsed/attempt data only.

## Risks / Trade-offs

- [Risk] OIE becomes ready immediately after the deadline. -> Record a timeout and leave lab-app healthy; the next lab-app restart retries, and manual lifecycle controls remain available.
- [Risk] Creation succeeds remotely but readback or persistence fails. -> Record partial failure, stop mutation for that logical type, and rely on conservative inventory reconciliation on the next explicit operation or restart to prevent duplicates.
- [Risk] The daemon worker is interrupted during process shutdown. -> Keep each external mutation single-target and independently auditable; do not claim rollback or process completion without readback.
- [Risk] Eager WSGI construction changes import behavior. -> Limit eager construction to the production entrypoint contract and retain factory-based, runtime-disabled test construction.
- [Risk] Future deployments use multiple workers or replicas. -> Document the one-worker constraint and keep leader election explicitly out of scope.

## Migration Plan

1. Add validated bootstrap configuration and non-destructive canonical mapping maintenance.
2. Add actor-aware guarded lifecycle composition and the runtime-neutral bootstrap coordinator.
3. Wire one asynchronous bootstrap start into concrete runtime activation and adjust the production WSGI startup boundary.
4. Document Compose/environment controls and verify clean, restart, partial, delayed, timeout, conflict, and secret-safety scenarios.
5. Rollback by setting bootstrap mode to `off`; code rollback leaves created managed Channels and persisted identities intact for existing manual lifecycle management.

## Open Questions

None. This proposal chooses mapping seeding, newly-created-only deployment, and eager production construction as the bounded ZAC-67 contract.
