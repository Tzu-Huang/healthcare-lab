## 1. Characterize Existing Database Semantics

- [x] 1.1 Add temporary-database tests that pin the five-second timeout, `sqlite3.Row`, foreign-key enforcement, successful commit, exceptional rollback, and connection close behavior.
- [x] 1.2 Add tests proving the existing shared reentrant lock is used by `DemoStore` and extracted repository writes while current read behavior remains compatible.
- [x] 1.3 Add fresh, current-unversioned, and representative partial legacy database fixtures that preserve application rows and user-managed values.
- [x] 1.4 Pin repeatable dcm4chee mapping repair, MRN sequence advancement, lab-server enrichment, and OIE default-seed behavior before moving implementation.

## 2. Introduce Shared SQLite Infrastructure

- [ ] 2.1 Add a repository-layer SQLite owner for the path, connection factory, shared `RLock`, and initialization lifecycle without changing public application behavior.
- [ ] 2.2 Implement the connection context with the characterized timeout, row factory, foreign-key PRAGMA, commit, rollback, and close semantics.
- [ ] 2.3 Add focused tests that use only temporary databases and prove repositories can receive the shared connection factory and lock without depending on `DemoStore`.

## 3. Build Ordered Migration Infrastructure

- [ ] 3.1 Add a stable ordered migration registry and internal ledger containing migration version, name, and successful application timestamp.
- [ ] 3.2 Ensure each migration is recorded only after successful completion, later versions stop on failure, and a corrected rerun resumes deterministically.
- [ ] 3.3 Extract all 21 existing application table declarations into idempotent schema migrations without changing their columns, constraints, or defaults.
- [ ] 3.4 Move every additive column upgrade into ordered migrations and create all 17 indexes only after their required tables and columns exist.
- [ ] 3.5 Add schema parity and rerun tests for fresh, current-unversioned, partial legacy, and injected-failure databases.

## 4. Extract Backfill and Seed Orchestration

- [ ] 4.1 Move the additive column helper and dcm4chee historical mapping backfill to repository-layer migration/maintenance ownership while preserving duplicate-column race handling and conditional repair behavior.
- [ ] 4.2 Move MRN sequence, lab-server, and OIE settings seed orchestration behind the shared initializer without overwriting existing user-managed values.
- [ ] 4.3 Prove repeated initialization neither duplicates rows nor decreases sequences, replaces mappings, or resets edited configuration.

## 5. Delegate DemoStore Compatibility

- [ ] 5.1 Change `DemoStore(path)` to initialize and delegate to the shared database owner while retaining compatible `path`, `lock`, `connect()`, and `initialize()` seams.
- [ ] 5.2 Pass the shared connection factory and lock directly to `OieSettingsRepository` and ensure the pattern is ready for later repository extraction.
- [ ] 5.3 Remove only the SQL/catch-all architecture-baseline entries eliminated by this extraction; do not add or refresh baseline exceptions.

## 6. YOLO Safety Gates and Verification

- [ ] 6.1 Confirm the implementation contains no application-table or application-row deletion, table rebuild, column removal, stricter legacy constraint, real `instance/*.db` access, or public API change; stop for review if any is required.
- [ ] 6.2 Run focused database and repository tests after each extraction stage and stop rather than weaken assertions when transaction, lock, seed, backfill, or legacy-data compatibility differs.
- [ ] 6.3 Run the full repository and integration suites, Python compilation, architecture contracts, `git diff --check`, and strict OpenSpec validation.
- [ ] 6.4 Commit implementation in focused stages so characterization, infrastructure, migrations, maintenance, and compatibility delegation can each be reviewed or reverted independently.
