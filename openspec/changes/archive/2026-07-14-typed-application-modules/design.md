## Context

Healthcare Lab currently combines application construction, HTTP routes, external FHIR and DICOM operations, workflow orchestration, validation, and runtime wiring in a 5,149-line `app.py`. Persistence is concentrated in an 8,021-line `backend/lab_store.py`, regression coverage in a 4,440-line `tests/test_app.py`, and frontend behavior in a 4,828-line `frontend/static/app.js`.

ZAC-46 through ZAC-52 will add OIE management clients, templates, lifecycle orchestration, listener runtime, Settings UI, diagnostics, audit, and E2E verification. The architecture change must establish destinations for that work without changing existing URLs, response shapes, persistence semantics, thread behavior, or integration behavior.

## Goals / Non-Goals

**Goals:**

- Establish typed modules with explicit ownership and dependency direction.
- Keep `app.py` as a process entrypoint and `backend/app_factory.py` as the composition root.
- Move existing code in reviewable stages while preserving public and runtime behavior.
- Separate OIE settings persistence from the general-purpose `DemoStore` surface.
- Make tests mirror production responsibilities and enforce the architecture mechanically.
- Give future OIE tickets unambiguous backend and frontend destinations.

**Non-Goals:**

- Implement ZAC-46 through ZAC-52 functionality.
- Redesign APIs, UI, persistence schemas, or runtime semantics.
- Replace Flask, SQLite, the frontend stack, or the existing testing framework.
- Rewrite every `DemoStore` method or eliminate all temporary compatibility exports in one change.

## Decisions

### Use responsibility-oriented typed packages

Production code will use `backend/api`, `services`, `clients`, `runtime`, `repositories`, `domain`, and `templates`, plus `backend/config.py` and `backend/app_factory.py`. Public functions, classes, and boundary data will carry useful type annotations without requiring a new runtime validation framework.

The allowed dependency direction is API and runtime wiring toward services; services toward clients, repositories, domain, and templates; clients and repositories toward domain. Domain and templates remain independent of Flask request state, while clients remain independent of Flask and SQLite.

Alternative considered: split files only by current feature names while retaining unrestricted imports. Rejected because it would reduce file sizes without establishing enforceable ownership or destinations for new work.

### Keep application assembly separate from request implementation

`backend/app_factory.py` will create Flask applications, load configuration, construct shared dependencies, register Blueprints, and start configured runtime components. Route parsing and HTTP response mapping live in `backend/api`; `app.py` only imports the factory, exposes compatibility entrypoints where required, and runs the process.

Alternative considered: leave `create_app()` and nested routes in `app.py`. Rejected because the process entrypoint would remain the default destination for unrelated behavior.

### Extract incrementally behind compatibility seams

Extraction will proceed in focused stages: package/configuration foundations, pure domain and external client code, runtime components, repositories and services, API Blueprints and composition, then entrypoint cleanup. Existing import paths may temporarily re-export moved symbols when tests or integrations rely on them, but new implementation must live in its owning module and compatibility exports must be explicit.

Alternative considered: move all code and tests in one mechanical rewrite. Rejected because the resulting diff would obscure behavior regressions and make rollback difficult.

### Isolate OIE settings persistence with delegation

An OIE settings repository will own OIE profile persistence. `DemoStore` may delegate existing methods to that repository during migration so current callers and database semantics remain compatible; new OIE capabilities must use the repository rather than add methods directly to `DemoStore`.

Alternative considered: postpone the repository boundary until ZAC-48. Rejected because later OIE workflow code would otherwise deepen the monolith before the boundary exists.

### Mirror production responsibilities in tests

Tests will be organized under `tests/api`, `services`, `clients`, `runtime`, `repositories`, `templates`, `integration`, and `e2e` as applicable. Existing regression assertions will be moved or retained without reducing coverage. An AST-oriented architecture contract test will assert that `app.py` stays within an allowlisted entrypoint shape and does not define routes, SQL, protocol clients, listener/watcher classes, or workflow implementations.

Alternative considered: rely on documentation and code review alone. Rejected because the monolithic placement pattern is easy to reintroduce during later feature work.

### Document frontend destinations without implementing ZAC-50

Project guidance will reserve `frontend/static/js/api`, `views`, `components`, and `state`, plus categorized CSS directories, for ZAC-50. This architecture change defines the placement contract but does not perform the Settings UI implementation or require a frontend framework/build-system migration.

## Risks / Trade-offs

- [Circular imports emerge while routes and services move] -> Keep `app_factory.py` as the composition root, inject dependencies, and avoid importing API modules from lower layers.
- [Compatibility regressions are hidden by a large diff] -> Extract in focused commits and run affected tests after every responsibility boundary.
- [Temporary re-exports become permanent] -> Limit them to named compatibility cases and make the architecture contract reject new implementation in the entrypoint.
- [Runtime startup behavior changes during listener extraction] -> Preserve construction and start/stop order, add focused lifecycle tests, and keep ownership in `app_factory.py` or runtime coordinators.
- [Test movement accidentally reduces coverage] -> Move assertions before deleting old locations and compare full-suite results throughout the migration.
- [Repository extraction changes transactions or schemas] -> Delegate through the existing connection and transaction semantics; do not introduce schema changes in this change.

## Migration Plan

1. Add typed package foundations, configuration boundaries, placement documentation, and architecture tests.
2. Extract framework-independent domain helpers and external protocol clients with compatibility imports where needed.
3. Move listeners, watchers, and lifecycle state into runtime modules with focused tests.
4. Introduce the OIE settings repository and delegate compatible `DemoStore` methods.
5. Move workflow coordination into services and HTTP handling into domain Blueprints.
6. Move application construction to `backend/app_factory.py` and reduce `app.py` to entrypoint wiring.
7. Reorganize tests by responsibility, run full verification, and remove obsolete compatibility scaffolding that is no longer needed.

Each stage remains independently reviewable. Rollback is performed by reverting the stage's focused commit; no data migration or externally visible contract change is required.

## Open Questions

None. Exact extraction batches may adjust to avoid circular imports, but they must preserve the declared ownership and dependency rules.
