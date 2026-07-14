## 1. Architecture Foundations

- [x] 1.1 Create the typed `backend/api`, `services`, `clients`, `runtime`, `repositories`, `domain`, and `templates` packages with explicit public boundaries.
- [x] 1.2 Extract environment and application configuration parsing into `backend/config.py` with focused compatibility tests.
- [x] 1.3 Add project-level architecture and placement guidance, including the reserved modular frontend destinations for ZAC-50.
- [x] 1.4 Add an initial AST-based architecture contract test for dependency direction and the allowed `app.py` entrypoint shape.

## 2. Domain and External Client Extraction

- [x] 2.1 Move framework-independent models, statuses, errors, validation, and shared mapping helpers into typed domain modules.
- [x] 2.2 Extract Medplum/FHIR authentication and transport operations into typed client modules while preserving retry, error, and response behavior.
- [x] 2.3 Extract dcm4chee/DICOMweb transport operations into typed client modules while preserving verification and error classification behavior.
- [x] 2.4 Add or relocate focused client and domain tests before removing the corresponding implementations from `app.py`.

## 3. Runtime Component Extraction

- [x] 3.1 Move existing listeners, watchers, sockets, retry loops, and lifecycle state into responsibility-specific runtime modules.
- [x] 3.2 Preserve runtime construction, start/stop order, status reporting, and shutdown behavior through explicit composition hooks.
- [x] 3.3 Add or relocate focused runtime lifecycle tests before removing the corresponding implementations from `app.py`.

## 4. Repository and Service Boundaries

- [x] 4.1 Introduce a typed OIE settings repository that preserves the existing SQLite schema, connection, and transaction semantics.
- [x] 4.2 Delegate retained `DemoStore` OIE settings methods to the repository and prevent new OIE persistence methods from expanding `DemoStore`.
- [ ] 4.3 Move workflow and integration coordination out of HTTP handlers into responsibility-specific services with injected clients and repositories.
- [x] 4.4 Add or relocate focused repository and service tests for the extracted behavior.

## 5. API Blueprints and Application Assembly

- [ ] 5.1 Move dashboard and infrastructure HTTP routes into typed API Blueprints without changing their contracts.
- [ ] 5.2 Move patient, order, result, GDT, and OIE settings routes into responsibility-specific API Blueprints without changing their contracts.
- [ ] 5.3 Implement `backend/app_factory.py` as the composition root for configuration, dependencies, Blueprint registration, and runtime startup.
- [x] 5.4 Reduce `app.py` to process entrypoint and explicitly required compatibility wiring, then tighten the architecture contract allowlist.

## 6. Test Organization and Regression Preservation

- [ ] 6.1 Split monolithic tests into matching `api`, `services`, `clients`, `runtime`, `repositories`, `templates`, `integration`, and `e2e` packages as applicable.
- [ ] 6.2 Confirm moved tests retain the existing assertions and remove superseded monolithic test locations without reducing collected coverage.
- [ ] 6.3 Verify architecture contract failures clearly identify misplaced routes, SQL, protocol logic, runtime classes, and workflow implementation.

## 7. Verification

- [ ] 7.1 Run focused tests after each extraction boundary and resolve import, lifecycle, transaction, and API compatibility regressions.
- [ ] 7.2 Run the full automated test suite, Python compilation, frontend and Compose contract tests, and appropriate application smoke checks.
- [ ] 7.3 Run `git diff --check` and strict OpenSpec validation, and document the final behavior-preservation evidence.
