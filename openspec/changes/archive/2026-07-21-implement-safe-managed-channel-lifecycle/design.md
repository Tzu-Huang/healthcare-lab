## Context

ZAC-46 provides an authenticated OIE 4.5.2 management client with Channel primitives and `override=false` updates. ZAC-47 provides two constrained, versioned HLAB Channel templates with stable logical markers and normalized desired state. The settings profile persists mappings from logical type to OIE Channel ID, name, template version, and last-known revision, but currently replaces all mappings only as part of a complete settings-profile update.

The missing layer must reconcile three independent sources of truth without confusing a familiar name with ownership:

```text
approved template ----+
persisted mapping ----+--> lifecycle snapshot --> preview --> guarded operation
live OIE inventory ---+
```

OIE is shared infrastructure. Channels outside Healthcare Lab's exact identity boundary may belong to another operator, and live revisions can change between preview and execution. Destructive convenience therefore has lower priority than containment, explainability, and recovery.

## Goals / Non-Goals

**Goals:**

- Classify every expected managed Channel and expose external Channels as read-only.
- Produce deterministic, revision-bound previews before mutation.
- Preserve unowned fields during updates and stop on any ownership or revision ambiguity.
- Make create, update, deploy, undeploy, and delete idempotent or safely retryable.
- Persist targeted mapping changes and secret/PHI-safe audit records.
- Return structured per-step outcomes for partial failures.
- Enforce defense-in-depth against accidental, scripted, or “YOLO” bulk/destructive actions.

**Non-Goals:**

- Adopting or editing a same-name external Channel.
- Generic Channel editing or raw XML/JSON editing.
- Automatic reconciliation during application startup.
- Automatic `override=true` retry or force mode.
- Exposing OIE `redeploy-all`, wildcard operations, multi-Channel mutation, or delete-message-history operations.
- Mutating external Channels or deleting OIE message history.
- A safe single-Channel redeploy until the OIE 4.5.2 contract can perform it without affecting other Channels; deploy and undeploy remain supported.

## Decisions

### 1. Use a persistence-neutral lifecycle coordinator

Add a lifecycle service with ports for OIE management, managed-template compilation, mapping persistence, clock/operation-ID generation, and audit persistence. Flask mapping and SQLite stay outside the domain/service contract.

The coordinator owns classification, preview generation, guarded sequencing, retry semantics, and result assembly. The existing management client continues to own transport behavior, while templates continue to own approved payload generation and normalization.

Alternative considered: place orchestration in API routes. Rejected because it would mix transport presentation with ownership and safety policy and make race-condition tests harder.

### 2. Treat identity as conjunctive evidence and fail closed

A live Channel is managed only when its exact marker/logical type agrees with the expected template and its OIE ID agrees with a non-empty persisted mapping. For first creation, absence of a mapping ID plus absence of any matching marker/name permits `Missing`. Name alone is never ownership evidence.

Classification precedence is deliberately conservative:

1. Contradictory IDs, duplicate managed markers, a same-name foreign Channel, malformed managed payload, or marker/type mismatch => `Conflict`.
2. No owned live Channel and no contradictory candidate => `Missing`.
3. Owned normalized state equals desired state => `Unchanged`.
4. Owned normalized state differs only in approved fields => `Drifted`.
5. All unrelated inventory remains `External` and read-only.

The service never adopts, relabels, edits, deploys, undeploys, or deletes a conflicted/external Channel.

Alternative considered: automatically adopt a same-name Channel after inspection. Rejected because historical intent cannot be proven from its payload.

### 3. Bind every mutation to a fresh, single-target preview

Preview is side-effect free and returns an opaque mutation token derived from the operation, logical type, desired normalized state, exact Channel ID (if any), observed revision, and a bounded expiry. The server validates this token and recomputes classification immediately before mutation. Tokens are not reusable for a different operation or Channel.

Create requires a `Missing` preview. Update requires `Drifted`; `Unchanged` returns a no-op without calling OIE. Deploy/undeploy require a currently managed exact ID. Delete requires an exact managed ID and an explicit delete preview. Any stale revision, changed classification, target mismatch, expired token, duplicate/ambiguous identity, or malformed state stops before mutation and returns a new preview requirement.

This is the primary “YOLO” barrier: the API has no force flag, wildcard target, list of targets, skip-preview switch, or override escape hatch. API clients cannot bypass the same service checks used by the UI.

Alternative considered: confirmation by logical type only. Rejected because it does not bind consent to the state the operator reviewed.

### 4. Merge approved fields into the complete live payload

For update, retrieve the complete current Channel immediately before mutation. Copy only approved template-owned fields into that payload, preserve every other live field, retain the live ID and revision, and call the existing update primitive with `override=false` explicitly. Compare normalized state before sending; if there is no owned-field difference, do not update.

Alternative considered: send the newly compiled canonical template as a replacement. Rejected because it could erase OIE-managed metadata or fields outside Healthcare Lab's edit surface.

### 5. Model mutations as explicit bounded step sequences

Each operation produces an operation ID and ordered step results.

- Create: revalidate -> create -> rediscover/read created Channel -> persist exact ID/revision -> audit.
- Update: revalidate/read -> merge -> update without override -> refresh -> persist revision -> audit.
- Deploy/undeploy: revalidate/read -> exact primitive -> refresh status -> audit.
- Delete: revalidate/read -> inspect status -> undeploy if required -> delete exact ID -> clear persisted ID/revision while retaining logical mapping -> audit.

There is no generic loop over selected Channels. A request addresses exactly one logical type and the service makes at most the declared primitive calls. A repeated request first refreshes live state and returns a no-op when the intended state already holds. If a later step fails after an earlier external mutation succeeds, return `partial-failure` with every attempted/not-attempted step; do not roll forward using assumptions.

### 6. Do not expose redeploy-all

The existing OIE client primitive affects all Channels and therefore violates the single-target ownership boundary. Lifecycle APIs and UI SHALL NOT call or expose it. A future single-Channel redeploy requires separately verified OIE behavior and a specification change. Until then, the managed lifecycle exposes deploy and undeploy only.

### 7. Add targeted mapping persistence with optimistic expectations

Extend the settings repository boundary with operations that update or clear one logical mapping using expected prior Channel ID/revision values. This avoids replacing unrelated profile fields/mappings and detects local concurrent changes. Creating or updating a mapping and writing the corresponding audit record should share one SQLite transaction after the OIE result is known.

The OIE mutation cannot participate in that transaction. If OIE succeeds and local persistence fails, the response is a partial failure and the next inspection must rediscover the exact marker/ID before offering repair. It must not blindly repeat create/delete.

### 8. Persist minimal append-only lifecycle audits

Store operation ID, timestamp, actor label where available, operation, logical type, Channel ID, before/after revision, classification, outcome/error category, and changed owned-field paths. Never store credentials, cookies, authorization headers, complete Channel payloads, HL7 messages, message content, patient identifiers, or arbitrary upstream bodies.

Audit writes are append-only through the lifecycle port. First release retains records without automatic cleanup. Read exposure may be limited to the needs of the settings UI, but audit persistence and tests are part of this change.

### 9. Keep API outcomes stable and explicit

Inspection and preview responses include classification, identity facts, owned-field diffs, permitted actions, and blocking reasons. Mutation responses use `success`, `failure`, or `partial-failure`, plus ordered steps and a refreshed final classification when available. Existing OIE error categories are propagated as safe stable categories rather than leaking raw bodies.

Destructive endpoints require the preview token and exact logical type. Delete additionally requires an explicit confirmation value matching the logical type; this is a human-error guard, not a substitute for server-side identity validation.

## Risks / Trade-offs

- [OIE response shapes may differ from sanitized fixtures] -> Keep parsing/merge logic behind focused adapters, reject malformed ownership evidence, and expand mocked contract fixtures before live validation.
- [OIE succeeds but SQLite persistence fails] -> Return partial failure, audit best-effort without secrets, and rediscover live state on retry rather than replaying the original mutation.
- [SQLite succeeds only after an external revision changes again] -> Treat persisted revision as last-known evidence, always refresh OIE before mutation, and rely on `override=false` for the final race.
- [Conservative classification blocks a legitimate Channel] -> Surface precise conflict evidence and require manual OIE remediation; do not add an adoption shortcut.
- [Preview tokens add state/complexity] -> Use signed, short-lived tokens or a persisted operation-preview record with exact input binding; whichever existing project dependency footprint supports with fewer moving parts.
- [Delete has an unavoidable undeploy/delete partial-failure window] -> Report step-level status and make retry reclassify current state before deciding whether delete remains safe.
- [Permanent audit retention grows storage] -> Records are small and bounded in content; retention policy can be added later without weakening initial accountability.

## Migration Plan

1. Add the lifecycle audit schema and any mapping constraints/indexes through the existing idempotent SQLite migration path.
2. Add targeted mapping/audit repository ports and tests without changing existing settings API behavior.
3. Add lifecycle domain contracts, coordinator, and mocked service tests.
4. Add API mapping and composition, keeping mutation unavailable until the coordinator is wired.
5. Expose preview and single-target actions in the settings UI only after backend safety tests pass.
6. Validate against mocked OIE 4.5.2 responses; any live-lab validation uses only known disposable managed Channels.

Rollback removes API/UI exposure first. The additive audit table and mapping data can remain; no rollback operation should mutate OIE Channels automatically.

## Open Questions

- Verify during implementation whether signed preview tokens can use an existing application signing facility; otherwise use short-lived persisted preview records.
- Confirm the minimal actor identity available from the current application. If none exists, record a stable `local-operator` actor rather than collecting new identity data in this change.
