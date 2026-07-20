## 1. Inventory and Guardrails

- [ ] 1.1 Inventory every `DemoStore` field/delegate, `backend.lab_store` import/re-export, `app.extensions["demo_store"]` access, root-entrypoint patch seam, architecture exception, baseline entry, documentation reference, and verification command; map each retained behavior to its named owner.
- [ ] 1.2 Add failing architecture/source-contract coverage that forbids `DemoStore`, `backend.lab_store`, the `demo_store` extension key, broad replacement containers, arbitrary forwarding, and production consumers of the composition result without expanding baselines or allowlists.
- [ ] 1.3 Characterize the existing database initialization/maintenance order, shared connection/lock identities, repository/coordinator wiring, root process entrypoint, runtime registrations, and disposable application startup before movement.

## 2. Explicit Application Composition

- [ ] 2.1 Add a dedicated application-composition module with explicit typed dependency groups for the shared `SQLiteDatabase`, maintenance lifecycle, repositories, enrichment loaders, coordinators, and narrow capabilities.
- [ ] 2.2 Preserve migration and maintenance ordering, one shared reentrant lock, repository callbacks, timestamp/payload collaborators, and coordinator construction semantics with focused composition tests.
- [ ] 2.3 Prove the composition outputs contain only declared data fields, no business delegates, `__getattr__`, generic lookup, or arbitrary forwarding, and are not accepted as broad service/API/runtime dependencies.

## 3. Production Rewiring

- [ ] 3.1 Replace `DemoStore` construction and every `store.*` access in `backend/app_factory.py` with named composition dependencies and responsibility-owner imports.
- [ ] 3.2 Rewire Blueprints, workflow services, listeners/watchers, configuration callbacks, lab/dashboard helpers, OIE/FHIR/GDT/dcm4chee coordination, and runtime extensions to their existing narrow ports while preserving lifecycle order and callbacks.
- [ ] 3.3 Remove `app.extensions["demo_store"]` without adding a broad `dependencies`, `repositories`, `services`, `store`, or equivalent replacement; retain only purpose-named runtime extension keys with production consumers.
- [ ] 3.4 Keep root `app.py` as the supported process entrypoint while replacing obsolete whole-module aliasing and test-only patch exports with owner imports or explicit injection.

## 4. Integration and Compatibility Test Migration

- [ ] 4.1 Classify every integration-suite `demo_store` access as public API setup/assertion, named persistence setup/assertion, exceptional-state injection, or compatibility-only coverage, and record its destination in the ownership handoff.
- [ ] 4.2 Extend shared test support with explicit named repository/composition fixtures for disposable databases; do not expose the production composition result through Flask or create a new catch-all test assertion owner.
- [ ] 4.3 Migrate Patient, Order, FHIR, GDT, OIE, dcm4chee, Dashboard/Lab, and shared integration setup to HTTP, named owner fixtures, or focused injection while retaining behavioral assertions and independent focused-suite execution.
- [ ] 4.4 Remove tests whose sole contract is a deleted `DemoStore` delegate/import/extension/patch seam, and reconcile test IDs, assertion ownership, and intentional count changes so behavior coverage is not silently lost.

## 5. Facade and Legacy Enforcement Removal

- [ ] 5.1 Move every remaining constant, helper, projector, validation function, template/client symbol, and coordinator import from `backend.lab_store` to its established responsibility-specific owner, adding a focused owner only where none exists and never duplicating implementation.
- [ ] 5.2 Delete all `DemoStore` delegates and construction code and remove `backend/lab_store.py` with no shim, deprecation alias, dynamic fallback, or compatibility re-export.
- [ ] 5.3 Remove DemoStore-specific delegate maps, composition fingerprints, compatibility caller allowlists, catch-all classifications, legacy-baseline entries, and architecture tests; replace only with stricter absence and explicit-composition contracts.
- [ ] 5.4 Prove repository-wide production and test scans contain no `DemoStore`, `backend.lab_store`, or `demo_store` extension references and no renamed broad facade/container.

## 6. Documentation and Verification

- [ ] 6.1 Update architecture, project boundary, test ownership, README verification commands, and relevant module documentation to identify the application composition owner, narrow dependency rules, supported root entrypoint, and removed compatibility seams.
- [ ] 6.2 Run focused composition, repository, domain/template, service, API integration, runtime, architecture, and frontend suites using disposable databases and external-service doubles only.
- [ ] 6.3 Verify supported existing-database initialization, migration/maintenance execution, Flask application creation, root process-entrypoint import/startup, runtime lifecycle registration, syntax compilation, and absence of live external-service or committed-database access.
- [ ] 6.4 Run the complete regression suite, test-ID/assertion ownership comparison, architecture contracts, frontend checks, diff checks, and strict OpenSpec validation; confirm no schema, migration, stored-data, route, payload, configuration, deployment, dependency, baseline-expansion, or unrelated changes.
- [ ] 6.5 Record implementation and verification evidence for closure review, including any intentional compatibility-test removals and proof that public/runtime behavior remains unchanged.
