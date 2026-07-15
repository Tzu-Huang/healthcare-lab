# healthcare-lab-sqlite-infrastructure Specification

## Purpose
TBD - created by archiving change extract-sqlite-migration-infrastructure. Update Purpose after archive.
## Requirements
### Requirement: Shared SQLite connection infrastructure

Healthcare Lab SHALL provide repository-layer SQLite infrastructure that owns the database path, connection factory, and shared application write lock independently of `DemoStore`.

#### Scenario: Open a repository connection

- **WHEN** a repository opens a connection through the shared infrastructure
- **THEN** the connection uses the configured database path, a five-second busy timeout, `sqlite3.Row` results, and enabled SQLite foreign-key enforcement

#### Scenario: Share the application write lock

- **WHEN** `DemoStore` and an extracted repository are composed for the same database owner
- **THEN** their write operations use the same reentrant lock while read-only operations retain the existing unlocked connection convention

### Requirement: Compatible connection transaction lifecycle

The shared connection context SHALL preserve the existing successful-commit, exceptional-rollback, and always-close behavior observed by current repositories and callers.

#### Scenario: Successful connection context

- **WHEN** a caller changes data and exits the connection context normally
- **THEN** the changes are committed and visible from a later connection

#### Scenario: Failed connection context

- **WHEN** a caller changes data and exits the connection context with an exception
- **THEN** the uncommitted changes are rolled back, the connection is closed, and the original exception remains visible

### Requirement: Ordered versioned migrations

Healthcare Lab SHALL execute schema migrations in a stable monotonically increasing order and SHALL persist the identity of each successfully completed migration in an internal migration ledger.

#### Scenario: Initialize a fresh database

- **WHEN** initialization runs against an empty database
- **THEN** all migrations run in order and produce every existing application table, column, constraint, and index plus the internal migration ledger

#### Scenario: Reopen a current database

- **WHEN** initialization runs again after every migration has been recorded
- **THEN** recorded structural migrations are not reapplied and the schema remains unchanged

#### Scenario: Migration fails

- **WHEN** a migration raises an error before successful completion
- **THEN** that migration is not recorded, later migrations do not run, startup reports the failure, and a corrected rerun can resume deterministically

### Requirement: Non-destructive legacy database convergence

Migrations SHALL converge current unversioned and supported partial legacy databases to the target schema without deleting application rows, dropping application schema objects, rebuilding tables, or introducing constraints that reject previously accepted data.

#### Scenario: Upgrade an unversioned current database

- **WHEN** initialization opens a database containing the current application schema but no migration ledger
- **THEN** idempotent migrations record the database as current without changing existing application rows or user-managed values

#### Scenario: Upgrade a partial legacy schema

- **WHEN** initialization opens a supported database missing additive columns or indexes
- **THEN** migrations create missing tables and columns before dependent indexes and preserve every pre-existing row

#### Scenario: Migration rerun after partial failure

- **WHEN** initialization reruns after an earlier migration failure left only safely committed earlier versions
- **THEN** already recorded versions remain intact and pending idempotent versions complete without duplicating or losing data

### Requirement: Repeatable backfill and seed orchestration

After structural migrations, Healthcare Lab SHALL run the existing conditional backfill and seed operations under the shared initialization lock without overwriting established target rows or user-managed configuration.

#### Scenario: Repair historical dcm4chee attempts

- **WHEN** historical MWL attempt rows have no canonical mapping during initialization
- **THEN** the existing deterministic mapping backfill creates only missing mappings and links eligible attempts without replacing existing mappings

#### Scenario: Advance the MRN sequence

- **WHEN** stored generated MRNs imply a next value greater than the recorded patient sequence
- **THEN** initialization advances the sequence without decreasing it or reusing an allocated value

#### Scenario: Preserve edited seed data

- **WHEN** lab-server or OIE settings seed rows already exist with user-managed values
- **THEN** initialization retains those values while applying only the existing non-destructive default enrichment behavior

### Requirement: DemoStore database compatibility facade

`DemoStore` SHALL delegate database infrastructure to the repository-layer owner while retaining the construction and database seams required by existing callers.

#### Scenario: Construct a legacy store

- **WHEN** an existing caller constructs `DemoStore(path)`
- **THEN** the shared database is initialized and the caller can continue to use the retained `path`, `lock`, `connect()`, and `initialize()` behavior

#### Scenario: Compose an extracted repository

- **WHEN** `DemoStore` exposes or composes an extracted bounded-context repository
- **THEN** the repository receives the shared connection factory and lock directly and does not depend on `DemoStore` for database ownership

### Requirement: Safe migration verification boundary

Healthcare Lab SHALL provide automated migration coverage that operates only on disposable databases and proves schema, data, transaction, concurrency, seed, and backfill compatibility before the extraction is considered complete.

#### Scenario: Run migration verification

- **WHEN** the migration verification suite executes
- **THEN** it creates isolated temporary databases and does not open or mutate a repository `instance/*.db`

#### Scenario: Detect an incompatible implementation

- **WHEN** an implementation requires destructive SQL, broader repository extraction, changed public behavior, or a new architecture-baseline exception
- **THEN** the change is treated as outside this capability and must stop for a separate reviewed decision

