---
change: auto-start-hlab-oru-result-listener
date: 2026-07-20
---

## Context

ZAC-49 moves the HLAB ORU result listener from manual, request-overridable startup to persisted OIE Settings ownership and safe application auto-start.

## Implementation

- Added narrow persisted listener configuration projection, explicit stopped/running/degraded runtime state, idempotent Start/Retry, temporary Stop, and best-effort composition auto-start.
- Kept Settings saves independent from runtime mutation and added the minimal Settings reminder and listener configuration surface.
- Removed listener endpoint editing from the operational OIE console and documented single-process ownership.

## Decisions

- Persisted Settings is the only listener configuration source.
- Bind failure degrades listener status without preventing HTTP availability.
- Stop remains process-local; changed Settings require Stop plus Retry or a lab-app restart.

## Validation Plan

- Run focused repository, runtime, service, API, composition, ORU regression, frontend module, and Playwright interaction tests.
- Run full unittest discovery, Python compilation, recursive JavaScript syntax checks, strict OpenSpec validation, and final diff/scope checks.

## Follow-ups

- Initial closure code review is required before archival.

## Verification

### Round 1 (2026-07-20 17:40 Asia/Taipei)

- Tested head: `73d46e56e41d37d6e6ec69aff9c98f3ed89539d8`
- Status: `pass`
- Checks: pass — `python -m unittest discover -s tests -t .` (499 tests, no skips); pass — focused ZAC-49 repository/runtime/service/API/composition/frontend/Playwright suites (25 tests, no skips); pass — `python -m compileall -q backend tests`; pass — recursive `node --check` for `frontend/static/**/*.js`; pass — `openspec validate auto-start-hlab-oru-result-listener --strict`; pass — `git diff --check main...HEAD`; pass — post-check product state remained clean and scope audit found no OIE Channel mutation, multi-replica coordination, HLAB pull/fetch, or unrelated managed-Channel UI.
- Unresolved failures: none
- Next action: `/dev-review`

### Round 2 (2026-07-20 17:50 Asia/Taipei)

- Tested head: `0fcb1fd4040c3031591eb48848d42690a61b5602`
- Status: `fail`
- Checks: fail — `python -m unittest discover -s tests -t .` ran 499 tests but `test_settings_save_shows_reminder_until_retry_applies_listener` timed out after browser reload waiting for the persisted `127.0.0.2` host; prior isolated and focused executions passed, so the new REV-001 browser regression is order/timing-sensitive; not run after required failure — focused repeat, compile, recursive JavaScript syntax, OpenSpec strict, and diff checks.
- Unresolved failures: REV-001 Playwright reload regression is not deterministic under full discovery, so the fixed HEAD cannot receive stable verification evidence.
- Next action: `/dev-fix "REV-001 Playwright reload regression is flaky under full discovery"`

### Round 3 (2026-07-21 09:32 Asia/Taipei)

- Tested head: `0537747282ce772f746026110af57d186b11fb3a`
- Status: `pass`
- Checks: pass — `python -m unittest discover -s tests -t .` (499 tests, no skips); pass — `python -m compileall -q backend tests`; pass — recursive `node --check` for 31 `frontend/static/**/*.js` files; pass — `openspec validate auto-start-hlab-oru-result-listener --strict`; pass — `git diff --check main...HEAD`; pass — post-check product state remained clean and scope audit found no OIE Channel mutation, multi-replica coordination, HLAB pull/fetch, or unrelated managed-Channel UI.
- Unresolved failures: none
- Next action: `/dev-review`

### Round 4 (2026-07-21 09:42 Asia/Taipei)

- Tested head: `a0df3dcf7c4f91a7d988dfca751a185dfb2a8271`
- Status: `pass`
- Checks: pass — `python -m unittest discover -s tests -t .` (499 tests, no skips); pass — `python -m compileall -q backend tests`; pass — recursive `node --check` for 31 `frontend/static/**/*.js` files; pass — `openspec validate auto-start-hlab-oru-result-listener --strict`; pass — `git diff --check main...HEAD`; pass — post-check product state remained clean and scope audit found no OIE Channel mutation, multi-replica coordination, HLAB pull/fetch, or unrelated managed-Channel UI.
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-20 17:43 Asia/Taipei)

- Source: `contexts/work_logs/2026-07-20_feature-ZAC-49_auto-start-hlab-oru-result-listener_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `73d46e56e41d37d6e6ec69aff9c98f3ed89539d8`
- Transitions: `REV-001 open`
- Open blockers: `REV-001`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-20_feature-ZAC-49_auto-start-hlab-oru-result-listener_codex-review-r1.md"`

### Round 2 (2026-07-21 09:35 Asia/Taipei)

- Source: `contexts/work_logs/2026-07-21_feature-ZAC-49_auto-start-hlab-oru-result-listener_codex-review-r2.md`
- Mode: `closure`
- Verdict: `changes-requested`
- Reviewed head: `0537747282ce772f746026110af57d186b11fb3a`
- Transitions: `REV-001 still-open`
- Open blockers: `REV-001`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-21_feature-ZAC-49_auto-start-hlab-oru-result-listener_codex-review-r2.md"`

### Round 3 (2026-07-21 09:45 Asia/Taipei)

- Source: `contexts/work_logs/2026-07-21_feature-ZAC-49_auto-start-hlab-oru-result-listener_codex-review-r3.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `a0df3dcf7c4f91a7d988dfca751a185dfb2a8271`
- Transitions: `REV-001 resolved`
- Open blockers: none
- Follow-ups: none
- Next action: commit only the review and devlog workflow records, then run `/dev-done`
