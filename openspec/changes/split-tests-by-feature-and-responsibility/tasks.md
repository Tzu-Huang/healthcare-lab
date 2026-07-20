## 1. Baseline and ownership inventory

- [x] 1.1 Pin the current mainline commit and capture the complete unittest test-ID and collection baseline.
- [x] 1.2 Reconcile the existing ZAC-63 records of 478 and 484 tests and document the authoritative baseline and counting command.
- [x] 1.3 Enumerate all 125 `tests/integration/test_app.py` tests and 27 `tests/repositories/test_lab_store.py` tests by feature and responsibility.
- [x] 1.4 Create the assertion-ownership matrix mapping each old test or assertion family to its new focused owner and verification command.

## 2. Shared test support

- [x] 2.1 Add unittest-compatible disposable database, Flask app/client, and deterministic payload factories under a focused test-support package.
- [x] 2.2 Centralize reusable HTTP, database, protocol, runtime, and external-service fakes without moving behavior assertions into helpers.
- [x] 2.3 Add focused support-contract coverage or characterization where a shared fake replaces duplicated setup behavior.

## 3. Integration test split

- [x] 3.1 Move application shell, route registration, static asset, and shared Flask rendering assertions into an application-shell suite.
- [x] 3.2 Move dashboard and lab control-plane API/health/operation assertions into responsibility-focused suites.
- [x] 3.3 Move Patient and Order API assertions, retaining only genuine Patient-to-Order boundary scenarios in a cross-feature suite.
- [x] 3.4 Move FHIR and dcm4chee API/workflow assertions into their feature suites, retaining only cross-context coordination at integration level.
- [x] 3.5 Move GDT and OIE API/runtime-facing assertions into their feature suites while preserving controlled external doubles.
- [x] 3.6 Verify that frontend module, CSS, template ownership, and browser interaction tests remain in `tests/frontend` under ZAC-63 ownership.

## 4. Repository, domain, and template test split

- [x] 4.1 Move database initialization, migration, and shared infrastructure assertions from `test_lab_store.py` to the database/schema owners.
- [x] 4.2 Move Patient and Order persistence assertions to their repository suites and pure validation/payload assertions to domain/template suites.
- [x] 4.3 Move FHIR ledger, dcm4chee patient-sync/MWL/results, and related mapping assertions to their existing responsibility owners.
- [x] 4.4 Move GDT workflow and OIE result/settings assertions to their repository, domain, template, or runtime owners.
- [x] 4.5 Isolate retained DemoStore and compatibility-import assertions in an explicitly named compatibility suite for the ZAC-65 handoff.
- [x] 4.6 Remove duplicate assertions only after the ownership matrix proves that the behavior remains covered by the new owner.

## 5. Independent verification and cleanup

- [ ] 5.1 Add focused unittest commands for every new integration, repository, domain, template, runtime, and compatibility suite.
- [ ] 5.2 Run each focused suite with disposable databases and external-service doubles and record the results.
- [ ] 5.3 Compare old and new test IDs, collection counts, and assertion ownership; explain intentional additions or removals.
- [ ] 5.4 Remove obsolete `test_app.py` and `test_lab_store.py` responsibility locations only after all ownership and focused checks pass.
- [ ] 5.5 Update the test ownership/baseline documentation and ZAC-65 compatibility handoff.

## 6. Quality gate

- [ ] 6.1 Run the complete unittest regression suite and architecture contracts.
- [ ] 6.2 Run the focused frontend suites and confirm ZAC-63 ownership remains intact.
- [ ] 6.3 Run Python compilation, diff checks, and strict OpenSpec validation.
- [ ] 6.4 Record the final collection comparison, residual manual boundaries, and verification commands in the change devlog before review.
