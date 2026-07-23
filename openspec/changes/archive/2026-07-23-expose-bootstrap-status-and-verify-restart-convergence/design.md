## Context

ZAC-67 and ZAC-68 introduced a bounded `OieManagedChannelBootstrap` that runs once in a daemon thread, waits for OIE readiness, and reconciles each canonical Channel through guarded lifecycle operations. Its return value is currently discarded. Per-operation lifecycle audits retain useful fragments, but they do not represent a complete run or expose waiting/running/completed state, timing, retry evidence, or operator guidance.

Settings currently obtains live inventory directly from the lifecycle service, and Runtime Diagnostics probes delivery layers independently. ZAC-69 crosses orchestration, persistence, API, diagnostics, frontend, and live OIE verification. Bootstrap evidence must remain secret- and PHI-safe, and it must not become part of ZAC-71's persisted operator-configuration ownership.

## Goals / Non-Goals

**Goals:**

- Make the latest bootstrap run queryable before, during, and after execution.
- Persist bounded run evidence so the last completed result remains visible after restart.
- Reuse one guarded reconciliation path for startup and explicit Retry.
- Prevent overlapping bootstrap runs and prevent every read path from causing mutation.
- Keep both canonical templates visible even when OIE inventory cannot be read.
- Add an independent bootstrap diagnostic layer and actionable, allowlisted guidance.
- Prove idempotent convergence against the supported OIE 4.5.2 Compose lab.

**Non-Goals:**

- Arbitrary OIE Channel editing, automatic drift repair, or forced ownership adoption.
- Distributed locking or production HA orchestration.
- Treating bootstrap evidence as operator configuration.
- Preserving OIE message history after deliberate OIE appdata deletion.

## Decisions

### Persist operational run snapshots separately from configuration

Add a focused bootstrap-run repository backed by SQLite. Store a run row and exactly one bounded outcome row per canonical logical type. The data model contains only allowlisted values: run identifier, trigger (`startup` or `retry`), mode, state, timestamps, attempts, outcome, safe error category, guidance code, logical type, classification, deployment state, and per-channel outcome.

This survives restart and supports deterministic API projection without replaying lifecycle audits. Reconstructing state from generic lifecycle audits was rejected because those records do not contain run boundaries, waiting state, attempts, or completion semantics. Storing the result only in memory was rejected because operators would lose the last failure during the restart they are diagnosing.

### Separate mutable execution from immutable status projection

Introduce a bootstrap coordinator around the existing reconciliation service. The coordinator owns a process-local non-blocking execution lock, creates the running snapshot before the first OIE call, updates bounded retry evidence, and atomically completes the snapshot. The existing reconciliation rules remain the single mutation path.

GET status, Settings refresh, inventory reads, and diagnostics read the repository only. They never invoke `run`, `inspect` for bootstrap purposes, or lifecycle mutation. Explicit Retry is a POST command and starts one asynchronous run only after eligibility and lock checks.

### Model process state and durable state honestly

The current process exposes `idle`, `running`, or `completed` plus the durable latest snapshot. On startup, an unfinished row left by a terminated process is projected as `interrupted`, not as currently running. Completion persists in a transaction after both logical types have bounded outcomes. A repository failure is surfaced as `status-unavailable` while HTTP availability remains intact.

### Use allowlisted Retry eligibility and guidance

Retry is accepted after readiness/timeout-style outcomes and other explicitly enumerated recoverable infrastructure categories. It is rejected while a run is active, when mode is `off`, or when the latest result only contains drift, external ownership, conflict, or other policy blockers. Even an accepted Retry executes the normal create-missing/recovery reconciliation and therefore cannot update drifted Channels or adopt external Channels.

Guidance is selected from category-to-guidance-code mappings in application code. Arbitrary exception text, upstream response bodies, credentials, Channel payloads, and HL7 content are never persisted or returned.

### Keep canonical template intent independent of live inventory

The managed-channel inventory projection starts with the two approved template definitions and overlays live classification when inspection succeeds. If inspection fails, the API returns an explicit bounded inventory error together with the two template identities in an unavailable state. This avoids both a misleading empty section and any read-triggered creation.

### Extend diagnostics without conflating runtime concerns

Runtime Diagnostics adds a `bootstrap` probe sourced from bootstrap status. It reports healthy, running, degraded, blocked, disabled, or unavailable semantics independently of the HLAB listener probe. Diagnostics does not Retry bootstrap and does not inspect or mutate OIE on behalf of this probe.

### Verify live convergence with stable, non-PHI evidence

The live runbook records Compose/OIE versions, scenario timestamps, logical types, bounded classifications/outcomes, Channel identifiers or hashes where appropriate, revision comparisons, and Channel counts. It excludes credentials, exported Channel payloads, messages, and PHI. Destructive persistence-reset scenarios require explicit volume targeting and exclusive use of the lab.

## Risks / Trade-offs

- [A process exits after mutation but before completing its snapshot] → Mark the stale run interrupted on next startup and let guarded reconciliation establish the next idempotent result.
- [Startup and Retry race] → Use one coordinator lock and return a stable conflict without starting a second worker.
- [SQLite evidence write fails] → Keep HTTP serving, emit bounded logs, and expose status unavailable; do not continue unobservable Retry mutation.
- [ZAC-71 changes configuration composition] → Keep bootstrap evidence behind its own operational repository and adapt only composition wiring after rebasing.
- [Live reset affects another worktree] → Require exclusive Compose use, resolved project/volume names, backups where applicable, and scenario-specific cleanup.

## Migration Plan

1. Add the bootstrap operational tables with idempotent schema creation.
2. Wire the repository and coordinator while preserving the current bootstrap mode defaults.
3. On first deployment, expose `idle/not-run` until a new startup run begins; do not synthesize historical runs from lifecycle audits.
4. Add status, Retry, diagnostics, and Settings projections.
5. Run automated tests, then execute the live OIE 4.5.2 matrix with exclusive Compose ownership.

Rollback removes the new API/UI usage and coordinator wiring. The additive tables can remain safely unused; existing lifecycle mappings and OIE Channels are not migrated or deleted.

## Open Questions

- Final Retry allowlist should be pinned during implementation from the existing `OieErrorCategory` values and tested as a closed set.
- The live report should decide whether raw OIE Channel IDs are acceptable non-PHI operational evidence or should be hashed.
