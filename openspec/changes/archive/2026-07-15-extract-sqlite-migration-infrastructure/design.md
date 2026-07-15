## Context

`DemoStore.__init__` currently creates a per-store `threading.RLock`, calls `initialize()`, and then constructs the first extracted repository with `DemoStore.connect` and that lock. `connect()` opens SQLite with a five-second timeout, assigns `sqlite3.Row`, enables foreign keys, commits after a successful context, and always closes the connection. Reads usually use an unlocked connection; writes and startup initialization use the shared reentrant lock.

`DemoStore.initialize()` currently creates 21 application tables and 17 indexes, adds historically introduced columns with `_ensure_column`, repairs missing dcm4chee mappings, advances the patient MRN sequence, and non-destructively seeds lab-server and OIE settings defaults. There is no migration ledger. Some current index statements precede the column checks on which they depend, making upgrade ordering implicit and fragile for sufficiently old databases.

The completed placement contract assigns SQLite persistence to `backend/repositories/` and permits `DemoStore` to remain only as a delegating compatibility facade. ZAC-56 must establish that shared foundation without also extracting every bounded-context repository.

## Goals / Non-Goals

**Goals:**

- Provide one reusable SQLite owner for the path, connection factory, shared write lock, and initialization lifecycle.
- Preserve existing connection, concurrency, transaction, foreign-key, row-factory, and timeout behavior for current callers.
- Give every schema change an ordered identity and record successful application in the database.
- Upgrade fresh, current unversioned, and older partial-schema databases without deleting or overwriting application data.
- Preserve idempotent startup repair and seed behavior where the current application intentionally runs it on every initialization.
- Keep `DemoStore` construction and its retained `path`, `lock`, `connect()`, and `initialize()` seams compatible.
- Make autonomous implementation safe through explicit scope limits, characterization gates, temporary-database verification, and stop conditions.

**Non-Goals:**

- Extract Patient, Order, FHIR, GDT, OIE, dcm4chee, or lab-control queries into their final repositories.
- Change public APIs, domain rules, protocol payloads, frontend behavior, or application configuration.
- Introduce an ORM, connection pool, asynchronous database driver, distributed lock, or new runtime dependency.
- Delete, rename, normalize, or deduplicate existing application data.
- Add uniqueness constraints that could reject a legacy database which starts successfully today.
- Rewrite the architecture baseline to permit new SQL in `DemoStore`.

## Decisions

### Create a repository-layer SQLite owner and delegate from `DemoStore`

A narrow database object under `backend/repositories/` will own the database path, one reentrant write lock, connection context creation, and initialization. Its connection context will retain the five-second timeout, `sqlite3.Row`, per-connection `PRAGMA foreign_keys = ON`, commit-on-success, close-always behavior, and rollback-on-exception behavior currently produced by closing an uncommitted connection.

`DemoStore(path)` will construct this object, initialize it, and expose compatibility aliases or delegating methods for `path`, `lock`, `connect()`, and `initialize()`. Extracted repositories receive the database connection factory and the same lock; new repository code does not depend on `DemoStore`.

Alternative considered: make every repository open and coordinate its own SQLite connections. Rejected because separate locks and subtly different transaction setup would break the current application concurrency boundary.

### Use a small ordered migration registry with an in-database ledger

Initialization will bootstrap a dedicated internal migration-ledger table and execute migrations in monotonically increasing order. Each migration has a stable numeric version, descriptive name, and callable. A migration and its ledger insert complete in the same transaction; a failed migration is not recorded and startup fails visibly.

The initial registry will describe the existing end state rather than inventing historical release versions that were never recorded. Its ordered phases will create missing tables first, ensure historically additive columns second, create indexes only after their required columns exist, and then run versioned data upgrades. All phases remain safe to execute against unversioned databases that already contain any subset of the target objects.

Alternative considered: set a current `PRAGMA user_version` after running the existing monolithic initializer. Rejected because a single integer provides no migration identity or audit trail and does not solve ordering or partial-failure reasoning.

Alternative considered: infer a legacy version from existing columns. Rejected because real databases may contain partial or manually repaired schemas; idempotent convergence is safer than guessing provenance.

### Keep schema declarations complete and migrations additive

The extracted schema is the authority for all existing application tables, columns, constraints, and indexes. Fresh databases converge to the same schema as today. Legacy upgrades may use `CREATE ... IF NOT EXISTS`, inspected `ALTER TABLE ... ADD COLUMN`, and non-destructive inserts/updates only. The change introduces no application-table drop, column removal, table rebuild, destructive rewrite, or stricter uniqueness rule.

The column helper will continue tolerating the duplicate-column race while re-raising unrelated SQLite errors. Identifier inputs remain code-owned constants rather than user input.

Alternative considered: replace the schema with a normalized redesign while extracting it. Rejected because it combines architectural movement with a data migration and violates the ticket's preservation constraint.

### Separate one-time migrations from repeatable startup maintenance

Structural creation and historical upgrades belong to the ordered migration registry. Existing behaviors that intentionally converge mutable startup state remain explicit post-migration maintenance steps under the same initialization lock and connection:

- repair missing dcm4chee mappings from historical attempt rows;
- advance, but never decrease, the patient MRN sequence;
- insert or enrich known lab-server defaults without overwriting user-managed connection values; and
- insert the default OIE profile only when absent.

This preserves today's reopen behavior while keeping the migration ledger truthful: a recorded structural migration is not rerun merely because application rows were later changed.

Alternative considered: record every seed and repair as a one-time migration. Rejected because current tests and runtime semantics expect selected repairs and non-destructive seeds to converge again on later startup.

### Characterize transaction and failure semantics before moving implementation

Focused tests will first pin down connection configuration, commit-on-success, rollback-on-error, read/write lock sharing, initialization reruns, and preservation of current seed and backfill behavior. The extraction then moves behavior behind the shared owner without changing those assertions.

Migration failure coverage will prove that the failed version is absent from the ledger, later migrations do not run, prior committed versions remain valid, and a corrected rerun resumes deterministically. Tests will use temporary databases only.

Alternative considered: improve transaction boundaries during extraction without characterization. Rejected because apparently safer transaction changes can alter concurrency and startup recovery behavior relied upon by existing repositories.

### Encode autonomous/YOLO guardrails as implementation gates

The apply phase must follow the ordered tasks and stop rather than improvise when any of these conditions occurs:

- a migration appears to require destructive SQL, application-row deletion, table rebuilding, or a new uniqueness constraint;
- preserving a legacy database conflicts with the proposed target schema;
- transaction, lock, seed, or backfill behavior cannot be matched by characterization tests;
- verification would require opening or modifying a real `instance/*.db` rather than a temporary fixture;
- implementation would require extracting bounded-context repositories or changing a public API; or
- architecture checks would pass only by adding or refreshing a legacy baseline entry.

Implementation commits should remain focused by stage so a failed stage can be reverted without discarding earlier characterization or infrastructure work.

## Risks / Trade-offs

- [An unversioned database may represent an unknown partial historical state] -> Make every initial migration inspect or create only what is missing and exercise representative partial-schema fixtures.
- [SQLite DDL or `executescript()` boundaries differ from ordinary statements] -> Avoid relying on implicit script transactions in the migration runner and prove failure/ledger behavior with real SQLite tests.
- [A migration is recorded despite incomplete work] -> Insert the ledger row only through the same successful migration transaction and test injected failures.
- [Repeatable backfills overwrite later user intent] -> Retain only the current narrowly conditional repairs and assert that existing target rows and user-edited values remain unchanged.
- [Multiple `DemoStore` instances do not share an in-process lock] -> Preserve the current per-owner lock and SQLite timeout semantics; cross-instance/distributed locking is outside this refactor.
- [Moving SQL changes architecture fingerprints] -> Remove corresponding legacy baseline entries as implementation leaves `DemoStore`; never add or refresh entries to conceal new catch-all SQL.
- [The proposal grows into broad repository extraction] -> Limit production changes to shared infrastructure, schema/migrations/maintenance ownership, and compatibility delegation.

## Migration Plan

1. Add characterization tests for current connection, lock, transaction, initialization, seed, and backfill semantics using temporary databases.
2. Introduce the shared SQLite owner and migration abstractions without moving bounded-context queries.
3. Extract complete table declarations, additive column upgrades, and indexes into ordered idempotent migrations, with indexes after their dependency columns.
4. Add the migration ledger and failure/resume tests for fresh, current unversioned, and representative legacy partial schemas.
5. Move repeatable backfill and seed orchestration behind the database initializer.
6. Delegate the retained `DemoStore` database seams and pass the shared connection factory and lock to repositories.
7. Remove only the migrated `DemoStore` architecture-baseline entries and run focused, repository, integration, compilation, architecture, and strict OpenSpec verification.

Deployment requires no manual database command. The first startup upgrades and records an existing unversioned database before normal application use.

Rollback of code is safe before a new migration has run. After the ledger table or additive schema objects have been created, rollback leaves those additive objects in place; older application code must continue to tolerate them. No rollback step deletes schema objects or data.

## Open Questions

None. The implementation must preserve characterized behavior; any discovered need for destructive migration or semantic change stops the YOLO flow and requires a separate reviewed decision.
