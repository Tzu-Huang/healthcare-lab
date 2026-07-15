# Code Review

## Findings

### [P1] Remove unreachable legacy database implementation

`DemoStore.initialize()` delegates to `SQLiteDatabase.initialize()` and returns, but the previous `executescript()` schema, additive migration, seed, and backfill implementation remains in the same class after the return (`backend/lab_store.py:711`). The old `_ensure_column`, `_backfill_dcm4chee_mwl_mappings`, and seed helpers also remain later in the class. This leaves duplicate persistence ownership in the compatibility facade, keeps the old SQL in the architecture baseline, and makes future edits likely to modify dead code instead of the new repository-layer owner.

Please remove the unreachable legacy implementation and retain only thin compatibility delegation where existing callers require a method or symbol. Preserve any non-database helper still used by active store operations through an explicit import/delegation to `backend.repositories.maintenance`.

## Verification

- Existing local verification passed: 246 tests, 34 architecture-contract tests, Python compilation, strict OpenSpec validation, and `git diff --check`.
- The finding is structural and is not caught by current behavioral tests because the legacy block is unreachable.
