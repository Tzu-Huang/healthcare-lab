---
change: implement-safe-managed-channel-lifecycle
date: 2026-07-20
---

# Development Log

## Context

ZAC-48 combines the OIE 4.5.2 management client and approved HLAB Channel templates into a guarded managed lifecycle.

## Implementation

- Added conservative managed/external inventory classification and owned-field diffs.
- Added state-bound preview tokens and fail-closed single-target mutations.
- Added targeted mapping persistence, lifecycle audits, guarded API endpoints, and Settings UI controls.
- Added XML Channel mutation support while retaining the existing JSON client contract.

## Decisions

- Never adopt by name, force a revision, expose redeploy-all, or perform bulk/startup mutation.
- Require a fresh exact-target preview and explicit logical-type confirmation for delete.
- Keep external Channels read-only and lifecycle audits free of secrets, PHI, HL7 content, and complete payloads.

## Validation Plan

- Run the full automated suite and focused lifecycle/security/architecture tests.
- Validate Python and JavaScript syntax, OpenSpec strict conformance, and diff hygiene.
- Run live OIE destructive checks only against an explicitly disposable managed Channel.

## Follow-ups

- Verify the real OIE 4.5.2 complete Channel response shape in a disposable environment.
- Review process-local preview signing and deploy/undeploy audit-failure behavior during code review.

## Verification

### Round 1 (2026-07-20 Asia/Taipei)

- Tested head: `5ebf1aa07d8b32654236231c1eb1621722a52160`
- Status: `pass`
- Checks:
  - `python -m unittest discover -s tests -q` — pass, 518 tests; 5 Playwright-dependent tests skipped because Playwright is unavailable.
  - Focused lifecycle, repository, API, client, architecture, Settings, and shared-component suite — pass, 101 tests.
  - `node --check` for Settings API/state/view/application modules — pass.
  - `python -m compileall -q backend tests` — pass.
  - `openspec validate implement-safe-managed-channel-lifecycle --strict` — pass.
  - `git diff --check` — pass.
  - Live OIE 4.5.2 destructive lifecycle — skipped; no explicitly disposable live target was established, and live mutation is not required by the mocked acceptance criteria.
- Unresolved failures: none
- Next action: `/dev-review ZAC-48`

### Round 2 (2026-07-20 Asia/Taipei)

- Tested head: `4cd2d5782ac15bcd19d098b9b697231e29081deb`
- Status: `pass`
- Checks:
  - `python -m unittest discover -s tests -q` — pass, 524 tests with no skips.
  - Focused lifecycle, complete-payload, revision-race, audit, result-contract, repository, API, architecture, and Settings suite — pass, 111 tests.
  - `node --check` for Settings API/state/view/application modules — pass.
  - `python -m compileall -q backend tests` — pass.
  - `openspec validate implement-safe-managed-channel-lifecycle --strict` — pass.
  - `git diff --check` — pass.
  - Live OIE 4.5.2 destructive lifecycle — skipped; no explicitly disposable live target was established, and live mutation is not required by the mocked acceptance criteria.
- Unresolved failures: none
- Next action: `/dev-review ZAC-48`

## Code Review

### Round 1 (2026-07-20 Asia/Taipei)

- Source: `openspec/changes/implement-safe-managed-channel-lifecycle/review/2026-07-20_feature-ZAC-48_implement-safe-managed-channel-lifecycle_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `5ebf1aa07d8b32654236231c1eb1621722a52160`
- Transitions: `REV-001 new; REV-002 new; REV-003 new; REV-004 new; REV-005 follow-up`
- Open blockers: `REV-001, REV-002, REV-003, REV-004`
- Follow-ups: `REV-005`
- Next action: `/dev-fix --review "openspec/changes/implement-safe-managed-channel-lifecycle/review/2026-07-20_feature-ZAC-48_implement-safe-managed-channel-lifecycle_codex-review-r1.md"`

### Round 2 (2026-07-21 Asia/Taipei)

- Source: `contexts/work_logs/2026-07-21_feature-ZAC-48_implement-safe-managed-channel-lifecycle_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `4cd2d5782ac15bcd19d098b9b697231e29081deb`
- Transitions: `REV-001 resolved; REV-002 resolved; REV-003 resolved; REV-004 resolved; REV-005 follow-up`
- Open blockers: none
- Verification: focused 31 passed; full suite 524 passed; closure diff hygiene passed
- Residual risk: live destructive OIE 4.5.2 validation was not run without an explicitly disposable target
- Next action: commit only the review and devlog records, then run `/dev-done ZAC-48`
