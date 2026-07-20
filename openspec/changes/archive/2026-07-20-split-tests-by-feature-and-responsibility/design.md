## Context

The current repository already contains production-aligned packages under `backend/api`, `backend/services`, `backend/repositories`, `backend/domain`, and `backend/templates`, as well as focused test packages. However, `tests/integration/test_app.py` still contains 125 tests in one broad API class, and `tests/repositories/test_lab_store.py` contains 27 tests covering multiple repositories, domain rules, payload/template behavior, and compatibility seams.

ZAC-63 established the shared feature taxonomy, frontend ownership map, focused frontend suites, and the rule that production and test ownership must move together. ZAC-64 owns the remaining broad test organization, reusable fixtures/fakes, assertion ownership, and responsibility-suite independence. ZAC-65 depends on this work before removing the `DemoStore` facade and obsolete compatibility exports.

Constraints:

- Preserve all observable behavior and existing regression assertions.
- Use the repository's current `unittest` workflow; do not add a test framework or runtime dependency.
- Do not move ZAC-63 frontend module tests back into the integration catch-all.
- Do not access live external services or committed database files during verification.
- Keep compatibility tests explicit until ZAC-65 removes the corresponding seams.

## Goals / Non-Goals

**Goals:**

- Give each integration, repository, domain, template, runtime, and compatibility responsibility a discoverable test owner.
- Separate true cross-feature workflow tests from single-feature API tests.
- Reuse setup and fakes while keeping assertions in the suite that owns the behavior.
- Produce a test-ID/assertion ownership inventory and a reproducible collection comparison.
- Provide focused commands that can be run independently during later production extraction and cleanup.

**Non-Goals:**

- Changing application behavior, API contracts, database schema, stored data, or external integration semantics.
- Removing `DemoStore` production compatibility; that belongs to ZAC-65.
- Replacing backend integration tests with browser E2E tests.
- Reorganizing the already focused frontend module suites except where an assertion is proven to have the wrong owner.
- Treating equal test counts as proof that behavior was preserved.

## Decisions

### Use the existing production taxonomy

Integration tests will be grouped by dashboard/lab control-plane, patient, order, FHIR, dcm4chee, GDT, and OIE boundaries, with shell/static checks in an application-shell suite and only genuine cross-boundary scenarios in a cross-feature workflow suite. Repository, domain, and template tests will follow the corresponding backend owners and existing test packages.

This is preferred over splitting by file size or endpoint prefix because it keeps each suite aligned with the production placement map and future ZAC-65 cleanup boundaries.

### Move assertions by ownership, not by whole test method

A method that currently verifies multiple responsibilities will be decomposed where necessary. Persistence assertions remain with the repository suite, pure validation or payload assertions move to domain/template suites, and an end-to-end interaction assertion remains in integration only when it verifies the boundary between components.

This avoids both duplicated assertions and the loss of behavior hidden inside a large `DemoStore` test.

### Keep shared setup in unittest-compatible support modules

Common disposable database setup, Flask app/client construction, HTTP responses, database doubles, protocol fakes, and payload factories will live under a focused `tests/support/` package. Helpers will prepare inputs and collaborators but will not own feature assertions or silently perform verification.

The alternative of a large inheritance-based test base is rejected because it hides dependencies and makes independent suite execution harder to understand.

### Preserve explicit compatibility coverage

Tests that exist only to prove a retained `DemoStore` delegate or compatibility import will move to a clearly named compatibility suite and be recorded as ZAC-65 handoff items. They will not be deleted as part of the broad test split.

### Establish a fresh baseline before migration

The implementation will record test IDs, collection counts, and assertion owners from the current mainline. The documented ZAC-63 records contain both 478 and 484 as final counts, so ZAC-64 will resolve that discrepancy rather than carrying either value forward as an assumption.

Test count comparison is a guardrail. The completion audit must also show where each old assertion moved and explain intentional additions or removals.

### Migrate incrementally and verify each group

The work proceeds in small feature/responsibility increments. Each increment runs its new focused suite and the nearest existing regression selection before the old location is removed. The final gate runs the full suite, architecture contracts, frontend-focused suites, syntax/import checks where applicable, and strict OpenSpec validation.

## Risks / Trade-offs

- **[Assertions are lost while splitting mixed tests]** → Maintain an old-test-ID to new-owner inventory and review every removed method before deleting its source location.
- **[Shared helpers recreate a hidden catch-all]** → Keep helpers limited to setup, fakes, and deterministic factories; retain behavior assertions in owner suites.
- **[Cross-feature tests are assigned to the wrong feature]** → Keep only true boundary interactions in a named cross-feature suite and document the participating owners.
- **[Focused suites pass while the full suite regresses]** → Run the complete regression and architecture gates after all migrations and compare collection evidence.
- **[Compatibility tests are removed before ZAC-65]** → Label DemoStore/import seam tests explicitly and include them in the next-ticket handoff.
- **[Baseline count remains ambiguous]** → Capture a fresh baseline on the pinned mainline commit and compare stable test IDs as well as counts.

## Migration Plan

1. Capture the current baseline, enumerate the 125 integration tests and 27 mixed store tests, and publish the initial ownership matrix.
2. Add the small shared `unittest` support package and migrate common fakes/setup without changing assertions.
3. Split application-shell, dashboard/lab, patient, order, FHIR, dcm4chee, GDT, OIE, and cross-feature integration coverage one group at a time.
4. Move mixed `test_lab_store.py` assertions into existing or newly named repository, domain, template, and compatibility suites.
5. Run each focused suite, compare test IDs/counts and assertion ownership, and remove obsolete catch-all test locations only after the audit passes.
6. Run the complete regression, architecture, frontend-focused, diff, and strict OpenSpec checks; record the ZAC-65 compatibility handoff.

Rollback is limited to reverting the test/documentation commits. No production data, schema, API, or deployment rollback is required.

## Open Questions

- Should the final integration filenames use feature names (`test_patient_api.py`) or responsibility names (`test_patient_routes.py`) where both are plausible? The default is feature names for API suites and responsibility names for non-feature infrastructure.
- Should the ownership matrix live as a new `docs/test-ownership-map.md` or as an expanded section of the existing frontend map? The default is a new backend-inclusive test ownership document to keep the frontend map focused.
- Which compatibility delegates must remain covered until ZAC-65, and which tests can be converted to direct repository composition during this ticket? The implementation should preserve them unless the next-ticket boundary is explicitly changed.
