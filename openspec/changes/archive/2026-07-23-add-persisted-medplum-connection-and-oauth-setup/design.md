## Context

ZAC-71 introduced a persisted typed Medplum profile and ZAC-72 introduced a modular Settings shell. The current profile already owns the FHIR base URL and core OAuth fields, but it lacks a browser UI URL and request timeout, and the Settings section is still a placeholder. Workflow composition mostly reads the persisted profile, while Lab Server health and smoke behavior can still read inventory or hard-coded values. Auth managers are created repeatedly, which prevents useful in-memory token reuse.

The change crosses persistence, security-sensitive OAuth behavior, application composition, diagnostics, inventory compatibility, and browser UI. It must preserve the local-first FHIR ledger behavior and must not expose secrets, tokens, authorization headers, or resource bodies.

## Goals / Non-Goals

**Goals:**

- Establish one canonical effective Medplum profile for every application workflow and diagnostic.
- Apply saved settings to subsequent operations without container recreation.
- Give operators a clearly labelled browser form and independent connection-test stages.
- Preserve write-only secret semantics and in-memory-only access tokens.
- Keep Docker-local internal and browser-facing defaults topologically correct.

**Non-Goals:**

- Creating, rotating, or deleting Medplum ClientApplication resources.
- Persisting access or refresh tokens.
- Changing clinical FHIR mappings, ledger ownership, or supported resource scope.
- Moving deployment-only Medplum server, database, Redis, image, or published-port settings into runtime persistence.

## Decisions

### Extend the existing closed Medplum profile

The profile will add `webUiUrl` and one positive integer `timeoutSeconds`. `baseUrl` remains the application-facing FHIR R4 URL. A single timeout keeps the operator contract understandable and will bound metadata, token, and FHIR requests consistently.

Alternative: separate connect, token, and read timeouts. This adds tuning complexity without a demonstrated operational requirement.

### Preserve one-time bootstrap ownership

Missing profiles will seed eligible legacy OAuth and tuning values once. The internal FHIR default will be `http://medplum:8103/fhir/R4`, and the browser URL default will be `http://127.0.0.1:3000`. Existing profiles remain authoritative and receive schema evolution through a deterministic persisted-profile migration rather than environment reseeding.

Alternative: continue deriving missing fields from Lab Server inventory on each read. This would retain competing ownership and make runtime behavior depend on presentation data.

### Compose a reusable Medplum runtime provider

Application composition will expose one provider that reads the effective profile, supplies the enabled base URL and timeout, and owns a reusable in-memory auth manager. It will invalidate cached authorization state when credential, token endpoint, scope, base URL, grace, enabled state, or timeout configuration changes.

Alternative: construct an auth manager for every operation. This is simple but defeats token caching and can cause unnecessary token requests.

### Make inventory a projection, not a workflow owner

The Medplum Lab Server record may remain for presentation and deployment controls, but its application URL, browser link, health, and smoke inputs will be derived from or linked to the effective typed profile. Mutating Medplum connection decisions through inventory remains rejected.

Alternative: synchronize two writable records. Bidirectional synchronization creates conflict and failure modes without user value.

### Save first, then run independent bounded checks

“Save and test” will persist a valid profile atomically and then run three ordered stages against that saved profile:

1. HTTP/FHIR metadata reachability.
2. OAuth token acquisition.
3. An authenticated bounded FHIR read that requests no resource body for display or diagnostics.

A test failure will not roll back a valid saved profile. Each stage returns a stable state and bounded value-free message so operators can distinguish URL, credential, and authorization failures.

Alternative: test before save. Blank-secret preservation and testing the exact effective persisted state become ambiguous, and successful validation could still diverge from the subsequent save.

### Keep diagnostics allowlisted and resource-free

Diagnostic projections will include stage identifier, state, bounded status/category, and safe summary only. Upstream response bodies, submitted URLs in error strings, credentials, tokens, headers, and FHIR resources will not be logged or returned. The authenticated read will be narrowly bounded by count and resource type.

## Risks / Trade-offs

- [Existing persisted rows lack new fields] → Add an idempotent schema-version migration before strict validation and cover restart behavior.
- [A settings change races with an in-flight request] → Snapshot one immutable effective profile per operation; invalidate the shared auth state for subsequent operations.
- [Saving a wrong URL immediately disrupts workflows] → Keep save atomic, show independent test failures, and retain mutation audit metadata for operator recovery.
- [Health and smoke regress to inventory data] → Add composition and architecture tests that prohibit Medplum workflow decisions from reading inventory connection fields.
- [Upstream exceptions contain sensitive bodies] → Translate failures at the Medplum boundary into allowlisted categories and test with canary secrets, tokens, headers, and resource content.

## Migration Plan

1. Add idempotent persisted-profile evolution for `webUiUrl` and `timeoutSeconds`.
2. Extend bootstrap projection and safe defaults without overwriting existing operator values.
3. Introduce the effective runtime provider and route consumers to it.
4. Project canonical settings into inventory health/smoke compatibility.
5. Add the Settings UI and Save-and-test API.
6. Deploy normally; no container recreation is required for profile activation.

Rollback may restore the prior application version while leaving additive profile fields stored. The prior reader must ignore or be migrated to tolerate those fields before rollback is considered supported.

## Open Questions

- Confirm the bounded authenticated probe resource and query shape; `_count=1` against `Patient` is the preferred default.
- Confirm whether a disabled profile reports diagnostic stages as `disabled` without any network activity; this design assumes yes.
