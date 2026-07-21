---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-48_implement-safe-managed-channel-lifecycle
base: main
reviewed_head: 5ebf1aa07d8b32654236231c1eb1621722a52160
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

None.

## New blocking findings

### [P1][REV-001] Complete Channel XML is truncated before lifecycle reconciliation

- Evidence: [`backend/clients/oie_management.py:383`](C:/Personal_repo/Projects/healthcare-lab/backend/clients/oie_management.py:383) redacts every returned mapping through `_redact_mapping`, and [`backend/clients/oie_management.py:459`](C:/Personal_repo/Projects/healthcare-lab/backend/clients/oie_management.py:459) truncates every string beyond 512 characters. The lifecycle requires complete XML at [`backend/services/oie_channel_lifecycle.py:125`](C:/Personal_repo/Projects/healthcare-lab/backend/services/oie_channel_lifecycle.py:125).
- Reproduction: passing the approved 22,574-character ORM XML through `get_channel()` returned 526 characters ending in `[TRUNCATED]`.
- Impact: real managed Channel inspection becomes `Conflict`/parse failure, and safe update cannot preserve or merge the complete current Channel. This defeats create readback, drift detection, and update acceptance criteria.
- Classification: initial blocking correctness defect.
- Required resolution: add an internal complete-Channel result boundary that preserves the full payload while maintaining secret-safe public/log projections. Exercise list/get through the actual management client in lifecycle tests with payloads longer than 512 characters.

### [P1][REV-002] Update can silently consume a post-preview revision instead of failing stale

- Evidence: execution validates the token against a list-derived snapshot at [`backend/services/oie_channel_lifecycle.py:63`](C:/Personal_repo/Projects/healthcare-lab/backend/services/oie_channel_lifecycle.py:63), but `_update` then fetches the Channel again and immediately merges/sends that new payload at [`backend/services/oie_channel_lifecycle.py:92`](C:/Personal_repo/Projects/healthcare-lab/backend/services/oie_channel_lifecycle.py:92). It never compares the fetched ID, marker, or revision with the preview-bound snapshot.
- Impact: if another operator changes the Channel between list revalidation and `get_channel`, Healthcare Lab uses the newer revision in its outgoing payload. OIE sees no stale revision and may accept the update, bypassing the required fresh-preview/revision-conflict workflow.
- Classification: initial blocking concurrency/safety defect.
- Required resolution: immediately before every exact-target mutation, fetch the complete Channel and verify ID, ownership marker, logical type, and revision against the preview-bound snapshot. A mismatch must return stale-preview before any write. Add race tests for update, deploy, undeploy, and delete.

### [P2][REV-003] Required lifecycle audit events are missing or silently discarded

- Evidence: `preview()` at [`backend/services/oie_channel_lifecycle.py:51`](C:/Personal_repo/Projects/healthcare-lab/backend/services/oie_channel_lifecycle.py:51) never writes the preview audit required by the specification. Deploy/undeploy and failure paths call `_audit`, but [`backend/services/oie_channel_lifecycle.py:145`](C:/Personal_repo/Projects/healthcare-lab/backend/services/oie_channel_lifecycle.py:145) catches every audit exception and still returns success/failure without surfacing the persistence loss.
- Impact: authorized previews and some mutation outcomes leave no durable record, while an audit database failure can be reported as a successful lifecycle operation. This violates the explicit durable audit requirement.
- Classification: initial P2 blocking because it violates an explicit requirement.
- Required resolution: persist bounded preview audits, make mutation audit failure part of the structured failure/partial-failure result, and add tests for preview audit plus deploy/undeploy audit-write failure. Avoid catch-all suppression.

### [P2][REV-004] Operation results omit required refreshed state and no-op semantics

- Evidence: deploy/undeploy calls `channel_status()` at [`backend/services/oie_channel_lifecycle.py:73`](C:/Personal_repo/Projects/healthcare-lab/backend/services/oie_channel_lifecycle.py:73) but discards the returned state. `_success` at [`backend/services/oie_channel_lifecycle.py:141`](C:/Personal_repo/Projects/healthcare-lab/backend/services/oie_channel_lifecycle.py:141) returns neither refreshed status nor final classification. `_permitted` at line 135 permits deploy/undeploy irrespective of current state, so an already-achieved state still invokes OIE rather than returning a no-op.
- Impact: callers cannot see the refreshed deployment state promised by the API contract, and repeated operations perform unnecessary mutations instead of distinguishing no-op steps.
- Classification: initial P2 blocking because it violates explicit operation-result and idempotency scenarios.
- Required resolution: model intended-state no-ops, include refreshed status/final classification when available, and test repeated deploy/undeploy plus step ordering and unattempted/no-op projection.

## Follow-up findings

### [P2][REV-005] Preview signing is process-local

[`backend/app_factory.py:332`](C:/Personal_repo/Projects/healthcare-lab/backend/app_factory.py:332) creates a random signing key at each process start. Restart invalidation is safe, but a multi-worker deployment can issue a preview on one worker and reject it on another. Consider a configured shared secret if Healthcare Lab is deployed with multiple workers. This is non-blocking for the current local-lab runtime.

## Verification and residual risk

- Reviewed `main...5ebf1aa07d8b32654236231c1eb1621722a52160` against the ZAC-48 proposal, design, specifications, tasks, implementation, and tests.
- Existing verification remains green: 518 full-suite tests (5 environment skips), 101 focused tests, syntax/compile/OpenSpec/diff checks.
- Live OIE 4.5.2 response-shape and destructive lifecycle verification remain unperformed; REV-001 shows the mocked client/service seam currently masks a real boundary incompatibility.

## Next Action

`/dev-fix --review "openspec/changes/implement-safe-managed-channel-lifecycle/review/2026-07-20_feature-ZAC-48_implement-safe-managed-channel-lifecycle_codex-review-r1.md"`

Reason: four blocking findings remain.
