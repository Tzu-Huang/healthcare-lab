---
change: establish-unified-typed-configuration-ownership
date: 2026-07-23
---

# Development Log

## Context

ZAC-71 establishes the typed persisted-settings foundation used by later
integration-specific Settings work. It assigns one owner to every supported
configuration key and prevents persisted runtime values from competing with
environment, Flask request state, Lab Server inventory, or raw SQL.

## Implementation

- Added the machine-checked configuration ownership registry and published
  ownership matrix.
- Added closed typed profile validation, separated secret persistence, ordered
  SQLite migration, atomic mutation/audit transactions, and create-only
  bootstrap.
- Added public and effective projections, write-only preserve/replace/remove
  secret commands, and the shared typed settings HTTP boundary.
- Migrated Medplum runtime consumers to persisted effective settings and
  adapted the specialized OIE profile without replacing its schema or lifecycle
  operations.
- Added architecture, domain, repository, migration, service, API, and
  cross-integration regression coverage.

## Decisions

- Use closed integration adapters rather than an arbitrary key-value settings
  store.
- Treat a persisted profile as authoritative after one-time bootstrap.
- Keep public secret state separate from private effective projections.
- Preserve the specialized OIE repository and lifecycle concurrency guards.
- Rely on deployment filesystem controls for SQLite at-rest protection; do not
  claim application-managed encryption.

## Validation Plan

- Run focused settings, migration, composition, API, OIE adapter, and
  architecture tests.
- Run the complete repository regression suite.
- Compile all Python sources, check the Git diff, and validate OpenSpec
  strictly.

## Follow-ups

- Later Medplum, GDT, dcm4chee, OpenEMR, and AP Settings issues must register
  typed adapters and consume the effective reader contract.
- External secret storage or application-managed encryption remains a separate
  future capability.

## Verification

### Round 1 (2026-07-23 11:13 Asia/Taipei)

- Tested head: `d934e193bd6cca25c9bdb3adc408afa631432d15`
- Status: `pass`
- Checks:
  - `python -m unittest tests.test_configuration_ownership tests.test_typed_settings_architecture tests.domain.test_integration_settings tests.repositories.test_integration_settings tests.repositories.test_schema_migrations tests.services.test_integration_settings tests.services.test_oie_settings_adapter tests.api.test_integration_settings tests.test_application_composition tests.api.test_oie tests.services.test_oie_settings tests.repositories.test_oie_settings` — pass, 66 tests.
  - `python -m unittest discover -s tests -p "test_*.py"` — pass, 655 tests.
  - `python -m compileall -q backend tests` — pass.
  - `git diff --check` — pass.
  - `openspec validate establish-unified-typed-configuration-ownership --strict` — pass.
  - Post-check `git status --porcelain` and `git rev-parse HEAD` — pass; no product/test/spec/config mutation and HEAD unchanged.
- Unresolved failures: none
- Next action: `/dev-review`

### Round 2 (2026-07-23 11:31 Asia/Taipei)

- Tested head: `4c7d81fe281a9c2b11b3aafcbfafe185b4ca899c`
- Status: `pass`
- Checks:
  - Focused settings, OIE, migration, composition, API, and architecture suite — pass, 73 tests.
  - `python -m unittest discover -s tests -p "test_*.py"` — pass, 662 tests.
  - `python -m compileall -q backend tests` — pass.
  - `git diff --check` — pass.
  - `openspec validate establish-unified-typed-configuration-ownership --strict` — pass.
  - Post-check HEAD and worktree attribution — pass; HEAD unchanged and only the pre-existing review workflow record remains untracked.
- Unresolved failures: none
- Next action: `/dev-review`

### Round 3 (2026-07-23 11:39 Asia/Taipei)

- Tested head: `328cb49c694e07bd6446f93865cc5b662632e24b`
- Status: `pass`
- Checks:
  - Focused settings, OIE, migration, composition, API, and architecture suite — pass, 74 tests.
  - `python -m unittest discover -s tests -p "test_*.py"` — pass, 663 tests.
  - `python -m compileall -q backend tests` — pass.
  - `git diff --check` — pass.
  - `openspec validate establish-unified-typed-configuration-ownership --strict` — pass.
  - Post-check HEAD and worktree attribution — pass; HEAD unchanged and only the two pre-existing review workflow records remain untracked.
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-23 11:18 Asia/Taipei)

- Source: `contexts/work_logs/2026-07-23_feature-ZAC-71_establish-unified-typed-configuration-ownership_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `d934e193bd6cca25c9bdb3adc408afa631432d15`
- Transitions: `REV-001 open; REV-002 open; REV-003 open; REV-004 open; REV-005 open`
- Open blockers: `REV-001`, `REV-002`, `REV-003`, `REV-004`, `REV-005`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-23_feature-ZAC-71_establish-unified-typed-configuration-ownership_codex-review-r1.md"`

### Round 2 (2026-07-23 11:33 Asia/Taipei)

- Source: `contexts/work_logs/2026-07-23_feature-ZAC-71_establish-unified-typed-configuration-ownership_codex-review-r2.md`
- Mode: `closure`
- Verdict: `changes-requested`
- Reviewed head: `4c7d81fe281a9c2b11b3aafcbfafe185b4ca899c`
- Transitions: `REV-001 resolved; REV-002 still-open; REV-003 resolved; REV-004 resolved; REV-005 resolved`
- Open blockers: `REV-002`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-23_feature-ZAC-71_establish-unified-typed-configuration-ownership_codex-review-r2.md"`

### Round 3 (2026-07-23 11:42 Asia/Taipei)

- Source: `contexts/work_logs/2026-07-23_feature-ZAC-71_establish-unified-typed-configuration-ownership_codex-review-r3.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `328cb49c694e07bd6446f93865cc5b662632e24b`
- Transitions: `REV-002 resolved`
- Open blockers: none
- Follow-ups: none
- Next action: commit only the review/devlog workflow records, then run `/dev-done`
