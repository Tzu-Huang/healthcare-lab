---
change: add-ap-external-device-connection-profiles
date: 2026-07-24
---

# Development Log

## Context

Add multi-profile AP and external-device connection settings with effective
HL7, GDT, and DICOM projections, bounded diagnostics, safe observations,
readiness, APIs, and a modular Settings experience.

## Implementation

- Added profile domain, migration, persistence, bootstrap, CRUD, default
  selection, validation, and value-safe audit behavior.
- Added effective integration projections without automatic OIE channel
  mutation or deployment.
- Added bounded diagnostics, PHI-safe interaction metadata, readiness states,
  Settings Overview integration, and the AP/External Devices Settings UI.

## Decisions

- OIE drift is reported as `apply-required`; saving a profile does not mutate
  or deploy a channel.
- Effective projections retain each integration's ownership of its independent
  runtime and filesystem settings.
- Diagnostics and interaction observations expose only closed, value-safe
  metadata.

## Validation Plan

- Run the complete Python regression suite and focused architecture contracts.
- Validate all frontend JavaScript syntax and Python compilation.
- Run strict OpenSpec validation and Git diff hygiene.
- Confirm the tested product state remains attributable to the captured HEAD.

## Follow-ups

- Complete the initial closure code review.

## Verification

### Round 1 (2026-07-24)

- Tested head: `3490ac596e617ba81f8d402596e5167011f845b0`
- Status: `pass`
- Checks: `python -m unittest discover -s tests -p 'test*.py' -v` — pass
  (809 passed, 1 skipped); `python -m unittest
  tests.test_architecture_contract -q` — pass (46 passed); `node --check`
  across all 39 `frontend/**/*.js` files — pass; `python -m compileall -q
  app.py backend tests` — pass; `openspec validate
  add-ap-external-device-connection-profiles --strict` — pass; `git diff
  --check` — pass; root `npm test` — skip (not required; no root
  `package.json`).
- Unresolved failures: none
- Next action: `/dev-review`

### Round 2 (2026-07-24)

- Tested head: `c7df9b3810c8642d2fb355c60dfc6631065294c9`
- Status: `pass`
- Checks: `python -m unittest discover -s tests -p 'test*.py' -v` — pass
  (810 passed, 1 skipped); `python -m unittest
  tests.test_architecture_contract -q` — pass (46 passed); `node --check`
  across all 39 `frontend/**/*.js` files — pass; `python -m compileall -q
  app.py backend tests` — pass; `openspec validate
  add-ap-external-device-connection-profiles --strict` — pass; `git diff
  --check` — pass; root `npm test` — skip (not required; no root
  `package.json`).
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-24)

- Source: `contexts/work_logs/2026-07-24_feature-ZAC-76_add-ap-external-device-connection-profiles_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `3490ac596e617ba81f8d402596e5167011f845b0`
- Transitions: `REV-001 open; REV-002 open; REV-003 open`
- Open blockers: `REV-001, REV-002, REV-003`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-24_feature-ZAC-76_add-ap-external-device-connection-profiles_codex-review-r1.md"`

### Round 2 (2026-07-24)

- Source: `contexts/work_logs/2026-07-24_feature-ZAC-76_add-ap-external-device-connection-profiles_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `c7df9b3810c8642d2fb355c60dfc6631065294c9`
- Transitions: `REV-001 resolved; REV-002 resolved; REV-003 resolved`
- Open blockers: none
- Follow-ups: none
- Next action: commit only the r1 and r2 review records, then run `/dev-done`
