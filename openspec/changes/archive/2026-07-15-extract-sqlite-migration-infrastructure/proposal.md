## Why

Healthcare Lab currently concentrates SQLite connection setup, locking, schema creation, additive upgrades, data backfills, and default seeds inside `DemoStore`. This prevents bounded-context repositories from owning persistence independently and leaves existing databases without an explicit, ordered migration history.

## What Changes

- Introduce shared SQLite infrastructure under the repository layer for connection configuration, the application write lock, and the existing transaction convention.
- Move schema initialization, additive upgrades, historical backfills, and seed orchestration out of `DemoStore`.
- Add an ordered migration registry and persistent migration ledger whose steps are idempotent for fresh, current, and legacy unversioned databases.
- Preserve all existing tables, indexes, rows, user-edited seed data, foreign-key enforcement, row behavior, timeout behavior, and repository-visible transaction semantics.
- Retain `DemoStore` as a compatibility facade that delegates database infrastructure while later bounded-context repository extraction proceeds separately.
- Add focused characterization, migration, concurrency, repository, and integration coverage, including explicit safeguards for autonomous/YOLO execution.

## Capabilities

### New Capabilities

- `healthcare-lab-sqlite-infrastructure`: Defines shared SQLite connections, ordered versioned migrations, non-destructive legacy upgrades, backfills, seed orchestration, transaction compatibility, and `DemoStore` delegation.

### Modified Capabilities

None.

## Impact

- Primary implementation areas: `backend/repositories/` and the retained compatibility surface in `backend/lab_store.py`.
- Primary verification areas: focused modules under `tests/repositories/`, existing repository tests, architecture contracts, and application integration tests.
- A new internal migration-ledger table is expected; no public API, payload, protocol, environment-variable, or frontend contract changes are intended.
- No ORM or external runtime dependency is introduced.
- Patient, Order, FHIR, GDT, OIE, dcm4chee, and lab-control repository extraction remains follow-up work.
