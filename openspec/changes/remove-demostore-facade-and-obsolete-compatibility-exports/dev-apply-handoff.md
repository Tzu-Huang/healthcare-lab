# ZAC-65 implementation handoff

## Implemented

- Replaced the broad persistence facade with private, explicit construction in
  `backend.application_composition` and narrow application ports.
- Removed the facade module, Flask extension key, root-module alias, arbitrary
  forwarding, and compatibility-only repository test.
- Migrated disposable integration/repository support to named dependencies and
  retained shared database, lock, migration, maintenance, callback, and runtime
  wiring semantics.
- Removed facade-specific architecture baselines and added a source contract
  that rejects the deleted facade/module/extension spellings in production.

## Verification evidence

- Focused integration suites: 113 passed.
- Repository discovery: 93 passed.
- Complete discovery: 486 passed in 66.664 seconds.
- Syntax compilation passed for changed production and shared test modules.
- Frontend JavaScript syntax checks passed.
- Strict OpenSpec validation and `git diff --check` passed.
- Production/test source scan found no removed facade, module import, or Flask
  extension reference.

The repository ownership inventory intentionally changed from 27 to 26 cases
because the deleted case asserted only the internal compatibility seam. Public
routes, payloads, configuration keys, SQLite schema/migrations, stored-data
semantics, and runtime extension behavior were not changed.
