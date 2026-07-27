---
change: preserve-degraded-medplum-readiness-across-restart
date: 2026-07-27
---

## Context

ZAC-80 prevents a failed required Medplum Save-and-test result from being forgotten after application restart or retained container recreation.

## Implementation

- Added an opaque Medplum configuration revision and bounded persisted verification projection.
- Bound successful and degraded evidence to the exact tested revision with stale-write rejection.
- Derived readiness from matching persisted evidence without network activity during startup or readiness reads.
- Added migration, repository, API, readiness, concurrency, redaction, and same-database reconstruction coverage.

## Decisions

- Persist only allowlisted state, stage, category, revision, and timestamp data.
- Treat missing or stale evidence as `needs-setup` and matching failed evidence as `degraded`.
- Require explicit re-verification rather than probing Medplum during readiness reads.

## Validation Plan

- Run focused Medplum, Settings, migration, API, frontend, restart, and redaction tests.
- Run the complete unit/integration/frontend suite, Python compile checks, OpenSpec strict validation, and diff hygiene.
- Re-run the ZAC-78 synthetic Medplum failure through an isolated retained-container recreation and capture bounded evidence.

## Follow-ups

- Complete the isolated Docker recreation after exclusive ownership or a genuinely isolated Compose override is available.

## Verification

### Round 1 (2026-07-27 11:19:38 +08:00)

- Tested head: `ef058f8f797dd62ba0b1a7333c00bafc26cefc4e`
- Status: `incomplete`
- Checks: pass — focused regression (`python -m unittest tests.repositories.test_schema_migrations tests.repositories.test_integration_settings tests.services.test_integration_settings tests.services.test_medplum_diagnostics tests.services.test_settings_readiness tests.api.test_integration_settings tests.api.test_settings_readiness tests.frontend.test_medplum_settings tests.test_zac80_medplum_readiness`), 80 tests; pass — full suite (`python -m unittest discover -s tests`), 858 tests with 1 existing non-required skip; pass — targeted Python compile; pass — `openspec validate preserve-degraded-medplum-readiness-across-restart --strict`; pass — committed diff hygiene; skip (required) — isolated ZAC-78 Medplum failure and retained-container recreation evidence, because the running shared instance owns the fixed `interoperability-lab` network, port 5000, and retained volume.
- Unresolved failures: required live recreation and bounded evidence tasks 4.1 and 4.2 remain incomplete; the shared instance was not mutated.
- Next action: `/dev-fix "complete required isolated Docker recreation and bounded evidence"`

### Round 2 (2026-07-27 11:33:57 +08:00)

- Tested head: `cc992f2c2f5ac6b2c85076d130d506cbc83b8e1a`
- Status: `pass`
- Checks: pass — focused regression suite, 80 tests; pass — full suite, 858 tests with 1 existing non-required skip; pass — targeted Python compile; pass — `openspec validate preserve-degraded-medplum-readiness-across-restart --strict`; pass — committed diff hygiene; pass — committed isolated retained-container recreation evidence confirms degraded state and `complete=false` before and after recreation, with secret canary scans clean; pass — all 13 OpenSpec tasks complete.
- Unresolved failures: none.
- Next action: `/dev-review`

### Round 3 (2026-07-27 11:44:14 +08:00)

- Tested head: `1d6e810f5c658982013b015afb2370935eb7f4b2`
- Status: `pass`
- Checks: pass — focused Medplum, Settings readiness, migration, repository, service, API, frontend, restart, and redaction regression suite, 82 tests; pass — full suite, 860 tests with 1 existing non-required skip; pass — targeted Python compile; pass — `openspec validate preserve-degraded-medplum-readiness-across-restart --strict`; pass — committed diff hygiene; pass — all 13 OpenSpec tasks remain complete and committed retained-container recreation evidence remains applicable.
- Unresolved failures: none.
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-27 11:36:22 +08:00)

- Review artifact: `contexts/work_logs/2026-07-27_fix-ZAC-80_preserve-degraded-medplum-readiness-across-restart_codex-review-r1.md`
- Mode: `initial`
- Reviewed head: `cc992f2c2f5ac6b2c85076d130d506cbc83b8e1a`
- Verdict: `changes-requested`
- Finding transitions: `REV-001` opened as a blocking P2 acceptance-contract violation.
- Open blockers: `REV-001`
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-27_fix-ZAC-80_preserve-degraded-medplum-readiness-across-restart_codex-review-r1.md"`

### Round 2 (2026-07-27 11:45:13 +08:00)

- Source: `contexts/work_logs/2026-07-27_fix-ZAC-80_preserve-degraded-medplum-readiness-across-restart_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `1d6e810f5c658982013b015afb2370935eb7f4b2`
- Transitions: `REV-001 resolved`
- Open blockers: `none`
- Follow-ups: `none`
- Next action: `/dev-done`
