---
change: extract-sqlite-migration-infrastructure
date: 2026-07-15
---

## Context

ZAC-56 extracts SQLite connection, schema, ordered migration, backfill, and seed ownership from `DemoStore` while preserving existing databases and compatibility seams.

## Implementation

- Added shared repository-layer SQLite connection and migration infrastructure.
- Added ordered schema migrations and migration ledger for fresh and legacy databases.
- Extracted repeatable maintenance, backfill, and seed orchestration.
- Reduced `DemoStore` database responsibilities to compatibility delegation.

## Decisions

- Kept the existing timeout, row factory, foreign-key, lock, and transaction conventions.
- Kept legacy upgrades additive and idempotent; no destructive data migration was introduced.
- Retained `DemoStore(path)`, `connect()`, `initialize()`, `path`, and `lock` compatibility seams.

## Validation Plan

- Run repository and integration tests, architecture contract tests, Python compilation, strict OpenSpec validation, and diff checks.
- Use temporary databases for migration and legacy-data verification; do not mutate real instance databases.

## Follow-ups

- Future changes may extract bounded-context repositories from the compatibility facade.

## Verification

### Round 1 (2026-07-15)

- PASS: full test suite, 246 tests.
- PASS: architecture contract, 34 tests.
- PASS: backend Python compilation, strict OpenSpec validation, and `git diff --check`.
- SKIP: external Docker/deployment smoke checks and real `instance/*.db` verification; temporary-database migration coverage passed.

## Code Review

### Round 1 (2026-07-15)

- Initial review found unreachable legacy database implementation in `DemoStore`; it was removed in `9d6e731`.
- Follow-up review verdict: no findings. Active lab-server validation/CRUD methods remain intact and the compatibility facade delegates to the repository-layer owner.
