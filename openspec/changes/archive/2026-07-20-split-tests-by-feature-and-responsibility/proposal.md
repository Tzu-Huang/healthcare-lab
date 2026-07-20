## Why

Healthcare Lab now has responsibility-specific production modules, but important regression coverage remains concentrated in `tests/integration/test_app.py` and `tests/repositories/test_lab_store.py`. ZAC-64 is needed now to make that coverage discoverable, independently verifiable, and safe for the final `DemoStore` cleanup planned by ZAC-65.

## What Changes

- Capture a fresh test-collection and test-ID baseline on the current mainline and reconcile the existing ZAC-63 count records.
- Split Flask integration coverage by feature, application boundary, and genuine cross-feature workflow instead of retaining one catch-all `test_app.py` suite.
- Split the remaining mixed `test_lab_store.py` coverage into repository, domain, template, and explicitly labeled compatibility owners, reusing existing responsibility-oriented suites where appropriate.
- Add reusable unittest-compatible fixtures, factories, and external-service fakes without moving assertions into generic helpers.
- Maintain an assertion-ownership inventory and compare collected test IDs and counts before and after migration.
- Define and run focused verification commands for each responsibility suite, followed by the full regression, architecture, and OpenSpec checks.
- Remove obsolete catch-all test locations only after every assertion has a named owner and the independent suites pass.
- Preserve the ZAC-63 frontend-focused suites and do not change production behavior, APIs, persistence, runtime integrations, or public compatibility contracts.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `healthcare-lab-typed-application-architecture`: strengthen the requirement that tests mirror production responsibilities with explicit assertion ownership, reusable setup boundaries, independently runnable suites, and collection comparison.
- `healthcare-lab-modular-frontend`: clarify the ZAC-63/ZAC-64 handoff so frontend ownership remains focused while ZAC-64 completes broad integration and repository test organization.

## Impact

- Affected verification areas: `tests/integration/test_app.py`, `tests/repositories/test_lab_store.py`, existing responsibility-oriented tests, and new shared test-support modules.
- Affected documentation: a durable test ownership and baseline record plus focused verification guidance.
- No production API, schema, persisted-data, runtime, external-service, or frontend behavior changes are intended.
- The final result prepares ZAC-65 to remove or reduce `DemoStore` without losing compatibility or regression coverage.
