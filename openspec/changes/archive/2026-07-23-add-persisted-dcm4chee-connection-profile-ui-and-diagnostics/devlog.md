---
change: add-persisted-dcm4chee-connection-profile-ui-and-diagnostics
date: 2026-07-23
---

## Context

ZAC-75 moves dcm4chee connectivity from startup-only environment projection to
the shared persisted typed Settings boundary and exposes integration-owned
configuration, readiness, and bounded diagnostics.

## Implementation

- Added typed profile persistence, one-time legacy bootstrap, secret-safe
  projections, mounted-reference validation, and stable identity protection.
- Migrated Patient ADT, MWL, result reconciliation, viewer, fixture, and lab
  smoke consumers to the application-scoped effective profile.
- Added independent Web UI, QIDO-RS, HL7 TCP, and DIMSE TCP diagnostics with
  redacted partial results.
- Added the modular dcm4chee Settings experience and readiness registration.

## Decisions

- Persisted settings are authoritative after the missing-profile bootstrap.
- TCP reachability is reported only as transport reachability.
- Identity changes are rejected while dependent DICOM records exist.
- Mounted certificate and private-key paths are references; contents and raw
  filesystem errors are never returned.

## Validation Plan

- Run focused typed-settings, dcm4chee workflow, diagnostic, readiness, API,
  frontend, and architecture tests.
- Run the complete repository test suite.
- Run Python compile, JavaScript syntax, and strict OpenSpec validation.

## Follow-ups

- Complete initial code review before closure.

## Verification

### Round 1 (2026-07-23 16:42:59 +08:00)

- Tested head: `6b79baa0fee8f816a2acb2ae1b0de56b7cb82e7a`
- Status: `pass`
- Checks: `node --check frontend/static/js/settings/dcm4chee.js` — pass; selected Python modules via `python -m py_compile` — pass; focused `python -m unittest ...` — 68 passed; `python -m unittest discover -s tests` — 774 passed, 1 skipped; `openspec validate add-persisted-dcm4chee-connection-profile-ui-and-diagnostics --strict` — pass; post-check product worktree — clean
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-23 16:50:00 +08:00)

- Source: `contexts/work_logs/2026-07-23_feature-ZAC-75_add-persisted-dcm4chee-connection-profile-ui-and-diagnostics_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `6b79baa0fee8f816a2acb2ae1b0de56b7cb82e7a`
- Transitions: `REV-001 open; REV-002 open; REV-003 open; REV-004 open; REV-005 open`
- Open blockers: `REV-001, REV-002, REV-003, REV-004, REV-005`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-23_feature-ZAC-75_add-persisted-dcm4chee-connection-profile-ui-and-diagnostics_codex-review-r1.md"`

## Verification

### Round 2 (2026-07-23 17:07:45 +08:00)

- Tested head: `4cbe71b2607c63a998d4fa24be0e77d4a10381fe`
- Status: `pass`
- Checks: `python -m compileall -q backend tests` — pass; `node --check frontend/static/js/settings/dcm4chee.js` — pass; focused dcm4chee settings, transport, diagnostics, readiness, workflow, API, and frontend tests — 70 passed; `python -m unittest discover -s tests` — 779 passed, 1 skipped (non-required); `openspec validate add-persisted-dcm4chee-connection-profile-ui-and-diagnostics --strict` — pass; post-check product worktree — clean at tested HEAD
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review

### Round 2 (2026-07-23 17:09:56 +08:00)

- Source: `contexts/work_logs/2026-07-23_feature-ZAC-75_add-persisted-dcm4chee-connection-profile-ui-and-diagnostics_codex-review-r2.md`
- Mode: `closure`
- Verdict: `changes-requested`
- Reviewed head: `4cbe71b2607c63a998d4fa24be0e77d4a10381fe`
- Transitions: `REV-001 still-open; REV-002 resolved; REV-003 resolved; REV-004 resolved; REV-005 resolved`
- Open blockers: `REV-001`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-23_feature-ZAC-75_add-persisted-dcm4chee-connection-profile-ui-and-diagnostics_codex-review-r2.md"`

## Verification

### Round 3 (2026-07-23 17:17:07 +08:00)

- Tested head: `f0c515c1c5044cbb98489f6e7715493c1f361bf0`
- Status: `pass`
- Checks: `python -m compileall -q backend tests` — pass; `node --check frontend/static/js/settings/dcm4chee.js` — pass; focused dcm4chee settings, secured transport, TLS redaction, diagnostics, readiness, workflow, API, and frontend tests — 73 passed; `python -m unittest discover -s tests` — 782 passed, 1 skipped (non-required); `openspec validate add-persisted-dcm4chee-connection-profile-ui-and-diagnostics --strict` — pass; post-check product worktree — clean at tested HEAD
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review

### Round 3 (2026-07-23 17:18:03 +08:00)

- Source: `contexts/work_logs/2026-07-23_feature-ZAC-75_add-persisted-dcm4chee-connection-profile-ui-and-diagnostics_codex-review-r3.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `f0c515c1c5044cbb98489f6e7715493c1f361bf0`
- Transitions: `REV-001 resolved; REV-002 resolved; REV-003 resolved; REV-004 resolved; REV-005 resolved`
- Open blockers: none
- Follow-ups: none
- Next action: commit only the review and devlog workflow records, then run `/dev-done`
