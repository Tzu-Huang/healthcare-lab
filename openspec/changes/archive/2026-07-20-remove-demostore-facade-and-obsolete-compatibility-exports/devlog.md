---
change: remove-demostore-facade-and-obsolete-compatibility-exports
date: 2026-07-20
---

# Development Log

## Context

ZAC-65 removes the internal `DemoStore` facade, `backend.lab_store`, and the
`demo_store` Flask extension after responsibility-specific owners and tests
were established.

## Implementation

- Added explicit typed application composition and named dependency wiring.
- Removed the broad facade, compatibility exports, extension key, obsolete
  patch seams, and compatibility-only test coverage.
- Updated architecture contracts, ownership documentation, and test support.

## Decisions

- Preserve supported HTTP, configuration, SQLite, protocol, startup, and
  runtime behavior while intentionally breaking obsolete internal seams.
- Do not replace the removed facade with another generic container or service
  locator.

## Validation Plan

- Run focused composition, repository, service, API, runtime, and architecture
  suites with disposable fixtures and external-service doubles.
- Run the complete regression suite, strict OpenSpec validation, syntax checks,
  diff hygiene, and removed-facade source scans.

## Follow-ups

- Resolve any verification failures before initial code review.

## Verification

### Round 1 (2026-07-20 16:26:20 +08:00)

- Tested head: `4ffbe247bb621185d0cf99d8f7e46826edc0232c`
- Status: `fail`
- Checks: PASS — focused composition/repository/service/API/runtime/architecture suites (313 tests); PASS — complete `python -m unittest discover -s tests -v` (486 tests); PASS — strict OpenSpec validation; PASS — in-memory Python compilation of 47 changed Python files; PASS — `node --check frontend\static\app.js`; FAIL — `git diff --check HEAD^ HEAD` (`backend/application_defaults.py:370`, blank line at EOF); FAIL — production/test removed-facade scan (two unused `DEMO_STORE_*` compatibility constants remain in `tests/test_architecture_contract.py`); PASS — worktree remained clean and HEAD unchanged.
- Unresolved failures: remove the trailing blank line from `backend/application_defaults.py` and the two unused compatibility constants from `tests/test_architecture_contract.py`.
- Next action: `/dev-fix "remove EOF whitespace and stale DemoStore architecture constants"`

### Round 2 (2026-07-20 16:33:58 +08:00)

- Tested head: `6214f740e5f8e58d8a638e4bbece5a6eb0f8d6d5`
- Status: `pass`
- Checks: PASS - focused composition, repository, service, API, runtime, and architecture suites (313 tests); PASS - complete `python -m unittest discover -s tests -v` (486 tests); PASS - strict OpenSpec validation; PASS - Python compilation for all changed Python files; PASS - `node --check frontend\static\app.js`; PASS - `git diff --check ee945ee^ HEAD`; PASS - production/test removed-facade scan; PASS - final HEAD unchanged with only this devlog workflow record dirty.
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-20)

- Source: `contexts/work_logs/2026-07-20_feature-ZAC-65_remove-demostore-facade-and-obsolete-compatibility-exports_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `6214f740e5f8e58d8a638e4bbece5a6eb0f8d6d5`
- Transitions: `REV-001 open`
- Open blockers: `REV-001`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-20_feature-ZAC-65_remove-demostore-facade-and-obsolete-compatibility-exports_codex-review-r1.md" REV-001`

## Verification (continued)

### Round 3 (2026-07-20 16:47:01 +08:00)

- Tested head: `ec4526b6078ab05b93f427e8678e5152c99a45f4`
- Status: `pass`
- Checks: PASS - complete `python -m unittest discover -s tests -v` (487 tests); PASS - focused composition/configuration/repository/service/API/runtime/architecture suites (317 tests); PASS - strict OpenSpec validation; PASS - Python compilation for every changed Python file; PASS - `node --check frontend\static\app.js`; PASS - `git diff --check main...HEAD`; PASS - production/test scan for the removed facade and replacement defaults module; PASS - final HEAD unchanged with only review/devlog workflow records dirty.
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review (continued)

### Round 2 (2026-07-20)

- Source: `contexts/work_logs/2026-07-20_feature-ZAC-65_remove-demostore-facade-and-obsolete-compatibility-exports_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `ec4526b6078ab05b93f427e8678e5152c99a45f4`
- Transitions: `REV-001 resolved`
- Open blockers: none
- Follow-ups: none
- Next action: commit only the review and devlog workflow records, then run `/dev-done`
