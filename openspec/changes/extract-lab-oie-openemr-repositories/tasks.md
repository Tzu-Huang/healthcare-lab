## 1. Characterize Extraction Boundaries

- [ ] 1.1 Move or add focused lab repository tests for server CRUD, health persistence, operation history, validation errors, result projections, and shared-lock behavior using disposable SQLite databases.
- [ ] 1.2 Move or add focused OIE repository tests for success, error, duplicate, unmatched, patient/order matching, result listing, settings composition, and shared-lock behavior using disposable SQLite databases.
- [ ] 1.3 Add OpenEMR client and domain tests for configuration status, row mapping, list/get, query parameters, unavailable driver, connection failure, missing schema, verification results, and connection closure using test doubles.

## 2. Extract Lab Control-Plane Persistence

- [ ] 2.1 Create `backend/repositories/lab.py` with lab server validation/projection and registry, persisted-health, and operation-history operations over an injected connection factory and write lock.
- [ ] 2.2 Compose `LabRepository` from `SQLiteDatabase` in `DemoStore` and replace retained lab persistence methods with explicit compatibility delegates.
- [ ] 2.3 Inject the lab repository directly into lab workflow composition and narrow the lab service port without changing dashboard or API behavior.

## 3. Extract OIE Persistence

- [ ] 3.1 Create `backend/repositories/oie.py` with OIE result projection, duplicate detection, success/error persistence, matching references, and result queries over the shared SQLite owner.
- [ ] 3.2 Remove `OieSettingsRepository` validation/serialization dependence on bound `DemoStore` implementation while preserving settings payload and validation behavior.
- [ ] 3.3 Compose OIE repositories in `DemoStore` and replace retained settings/result methods with explicit compatibility delegates.
- [ ] 3.4 Split OIE workflow and listener dependencies into narrow result and patient/order coordination ports, keeping cross-context inventory/workbench assembly out of the OIE repository.

## 4. Extract OpenEMR Query Ownership

- [ ] 4.1 Move OpenEMR normalization and procedure-row-to-GDT-order mapping into `backend/domain/openemr.py` with unchanged output projections.
- [ ] 4.2 Create `backend/clients/openemr.py` owning MariaDB configuration, connection, procedure-order SQL, missing-schema handling, list/get, and query verification behavior.
- [ ] 4.3 Update application and lab verification composition to use the OpenEMR client directly, removing OpenEMR SQL and driver ownership from `backend/lab_store.py` while retaining only a tested compatibility re-export if an existing caller requires it.

## 5. Enforce Architecture and Compatibility

- [ ] 5.1 Move remaining mixed `DemoStore` assertions into responsibility-specific repository, client, domain, and service test modules while retaining only genuine integration coverage.
- [ ] 5.2 Update architecture contracts and remove all extracted lab/OIE/OpenEMR implementation and SQL entries from the legacy baseline without adding or changing a baseline exception.
- [ ] 5.3 Verify retained `DemoStore` delegates and direct owners produce identical result shapes, exceptions, transaction behavior, and shared-lock identity.

## 6. Verification

- [ ] 6.1 Run focused repository, client, domain, service, runtime, and integration tests for the extracted boundaries using only disposable databases and external-service doubles.
- [ ] 6.2 Run the architecture contract tests and confirm no new catch-all, SQL, payload, workflow, or transport baseline entry is introduced.
- [ ] 6.3 Run the full automated test suite and confirm no `instance/*.db`, live OpenEMR/OIE, Docker lifecycle, deployment, push, merge, or release action was used.
