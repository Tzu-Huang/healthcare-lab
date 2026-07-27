## Context

The persisted Medplum profile owns configuration and write-only secret state, while `MedplumDiagnosticService` returns allowlisted metadata, OAuth, and authenticated-read stages. The current Medplum readiness provider checks only whether an enabled operator profile and base URL exist. Diagnostic failure state is not durable, so a new process treats field presence as readiness even when the required authenticated check most recently failed.

ZAC-80 is a correctness and safety change for required guided setup. Operational evidence must survive application restart and compatible container recreation, but it must not become a second configuration owner or retain credentials, tokens, FHIR resources, arbitrary upstream errors, or PHI.

## Goals / Non-Goals

**Goals:**

- Preserve only closed Medplum diagnostic state and allowlisted stage categories.
- Associate the result with the exact persisted configuration revision it verified.
- Report `ready` only for a matching successful verification, `degraded` for a matching failed verification, and `needs-setup` for missing or stale verification.
- Invalidate prior evidence whenever an authentication- or connectivity-relevant field or secret changes.
- Preserve deterministic readiness across process restart without performing an unsolicited network probe at startup.

**Non-Goals:**

- Persist OAuth tokens, credentials, submitted field values, FHIR bodies, or upstream response text.
- Introduce background health polling or automatic startup authentication.
- Change Medplum workflow retry policy or general service-health monitoring.
- Make optional integrations block setup completion.

## Decisions

### Persist a closed verification projection

Store one latest Medplum verification record containing a configuration revision, overall state, the three allowlisted stage/state/category tuples, and a timestamp. Summaries may be reconstructed from stable categories rather than persisted from upstream-derived text.

Alternative considered: serialize the complete Save-and-test response. Rejected because it expands the durable data surface and makes future accidental upstream-content retention more likely.

### Use an opaque configuration revision, not secret-derived material

Increment or replace an opaque revision whenever a Medplum public field or secret mutation changes the effective profile. The verification record stores that revision; it never hashes or otherwise derives identifiers from secret values.

Alternative considered: hash all effective values. Rejected because secret-derived fingerprints create unnecessary sensitive material and complicate rotation semantics.

### Treat missing or stale evidence as needs-setup

An enabled, structurally valid Medplum profile is `ready` only when its current revision has a successful three-stage result. A matching failed result is `degraded`. No result, an older revision, or an incomplete required check is `needs-setup`. Disabled behavior remains governed by the existing profile contract.

Alternative considered: automatically rerun diagnostics during readiness reads or startup. Rejected because a read-only readiness request would gain external side effects and startup would become dependent on external service timing.

### Record the result after the saved revision is known

Save-and-test first commits the validated profile mutation, then runs diagnostics against that effective revision, then persists the bounded result for the same revision. If the profile changes concurrently before evidence is recorded, the revision mismatch prevents that result from authorizing readiness.

### Keep readiness and Save-and-test response shapes bounded

Existing public stage names and stable categories remain the interoperability boundary. Repository validation rejects unknown stages, states, categories, oversized content, and any value-bearing fields.

## Risks / Trade-offs

- [A transient Medplum outage remains visible after service recovery] → Keep explicit Save-and-test/Run checks as the operator-controlled path to replace degraded evidence.
- [Migration leaves existing configured profiles without verification evidence] → Report `needs-setup` rather than guessing success, and provide a bounded next action to rerun the check.
- [Concurrent saves and checks race] → Compare the configuration revision before accepting the result; mismatched evidence remains stale.
- [Persisted diagnostics broaden the local database surface] → Store only enums, revision metadata, and timestamp under strict allowlists.

## Migration Plan

1. Add an idempotent SQLite migration for the bounded verification record and opaque profile revision.
2. Existing Medplum profiles receive a revision but no fabricated successful result, so they require one explicit Save-and-test.
3. Deploy repository, service, and readiness changes together.
4. Rollback may ignore the additive table/columns; no credential or profile data is rewritten.

## Open Questions

- Whether Run all checks should persist a matching Medplum result in addition to Save-and-test, provided it uses the same bounded diagnostic service and revision guard.
