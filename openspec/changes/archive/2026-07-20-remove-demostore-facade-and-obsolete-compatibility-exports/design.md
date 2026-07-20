## Context

Earlier changes extracted SQLite ownership, bounded-context repositories, protocol/domain/template logic, workflow services, frontend modules, and responsibility-oriented tests. `backend/lab_store.py` is now a roughly 1,200-line compatibility/composition shell, but `backend/app_factory.py` still creates `DemoStore`, reaches through approximately sixty `store.*` attributes, publishes it as `app.extensions["demo_store"]`, and imports constants/helpers through the compatibility module. Production does not read that extension key; integration tests do so extensively for setup and state inspection.

ZAC-65 is the final cleanup after those migrations. Internal Python import and test seams may break, while HTTP, process-entrypoint, configuration, database, runtime, payload, and external-integration contracts must remain stable. Verification must use disposable databases and external-service doubles.

## Goals / Non-Goals

**Goals:**

- Make the database, maintenance lifecycle, repositories, enrichment loaders, coordinators, and service capabilities explicit at the composition root.
- Delete `DemoStore`, `backend/lab_store.py`, and the `demo_store` Flask extension key without a compatibility period.
- Remove delegated methods, duplicate constants/helpers, obsolete patch paths, compatibility tests, and architecture exceptions that exist only for the deleted facade.
- Let integration tests prepare and inspect state through HTTP, named repository fixtures, or explicit injection rather than a production service locator.
- Preserve supported observable behavior and make architecture enforcement stricter and simpler.

**Non-Goals:**

- Extracting another repository, redesigning services, changing frontend behavior, or reorganizing unrelated modules.
- Changing routes, JSON, status codes, configuration keys, database schema/migrations/data, timestamps, transaction boundaries, payloads, or runtime startup/shutdown ordering.
- Adding a dependency, framework, generic dependency-injection container, global registry, or replacement facade.
- Accessing live OIE, Medplum, OpenEMR, GDT, dcm4chee, Docker, or committed database resources.

## Decisions

### Use a dedicated application-composition owner with explicit typed outputs

Move the construction currently embedded in `DemoStore.__init__()` to a named composition module. It may return immutable dataclasses or similarly explicit typed groups for construction convenience, but every field must be declared and cohesive. It must not expose business methods, implement arbitrary forwarding, use `__getattr__`, or be accepted by a service/API as a broad dependency.

This is preferred over leaving all construction inline in `create_app()` because the dependency graph is large and deserves focused composition tests. A generic container or renamed `DemoStore` is rejected because it would preserve the service-locator problem.

### Delete `backend.lab_store` in one change

All remaining constants, pure helpers, repositories, coordinators, and client symbols already have or must receive responsibility-specific owners. Every repository-local caller will import those owners directly, after which `backend/lab_store.py` will be deleted. No shim, deprecation release, or dynamic import fallback will remain because the user has confirmed that this internal module is not a supported public API.

### Remove the broad Flask extension without replacement

Delete `app.extensions["demo_store"]`. Production does not read it, so the direct migration cost is limited to tests. Runtime objects that genuinely need Flask lifecycle lookup may retain existing narrow keys such as watcher/listener/service keys. The application must not publish a new `dependencies`, `repositories`, `store`, or equivalent broad extension.

### Give tests explicit access to their owner

Integration setup will choose the narrowest suitable seam:

1. Use HTTP when the setup or assertion is itself public API behavior.
2. Use named repository fixtures for persistence setup and inspection.
3. Use an explicit application-factory injection or focused fake for exceptional states that cannot be created through supported HTTP.

Shared test support may hold a typed test-only dependency fixture, but production Flask extensions and services must not receive it. Compatibility tests whose only assertion is that a deleted delegate/import exists will be removed; behavioral assertions will move to their true owner.

### Preserve the process entrypoint, not obsolete patch aliases

Root `app.py` remains importable as the documented process entrypoint and continues to expose the application contract required by deployment. Whole-module aliasing and test-only symbol patch paths may be removed after callers patch the actual owner or receive injected collaborators. Entrypoint syntax and startup verification must protect the supported contract.

### Shrink enforcement instead of replacing exceptions

Architecture classifiers, legacy fingerprints, compatibility allowlists, and documentation entries specific to `DemoStore` will be removed. No refreshed fingerprint, renamed exception, dynamic loading, or broader allowlist may compensate for the deletion. New checks will reject production imports of `backend.lab_store`, broad application containers, generic forwarding, and the `demo_store` extension key.

## Risks / Trade-offs

- **[Composition becomes a renamed DemoStore]** → Permit only declared typed fields, forbid business delegates/forwarding, and prove that services receive narrow ports rather than the composition result.
- **[Integration coverage is weakened while removing direct store access]** → Inventory every `demo_store` test use, classify it as HTTP/setup/state/compatibility, and retain each behavioral assertion under a named owner before removing the old access.
- **[Initialization ordering or shared-lock behavior changes]** → Preserve the single `SQLiteDatabase`, migration/maintenance order, shared reentrant lock, lazy callbacks, and coordinator construction order with focused composition and disposable-database tests.
- **[Patch-path removal changes runtime behavior]** → Replace only test/internal patch seams, verify the root entrypoint contract, and retain injection/callback behavior needed by actual runtime workflows.
- **[Constants or helpers are moved to the wrong layer]** → Import from the existing domain/template/client/configuration owner; add a new focused owner only when none exists, without duplicating behavior.
- **[Large mechanical change obscures regression]** → Implement in focused commits by composition, callers, tests, and cleanup; run nearest suites after each step and full verification before review.

## Migration Plan

1. Inventory `DemoStore` fields/delegates, `backend.lab_store` imports, `demo_store` test accesses, compatibility exports, and architecture exceptions; map every retained behavior to its owner.
2. Add explicit composition types/functions and focused tests while preserving the existing database lifecycle, repository graph, coordinators, and callbacks.
3. Rewire `backend/app_factory.py`, services, Blueprints, listeners/watchers, configuration callbacks, and root entrypoint imports to named owners.
4. Migrate integration setup and assertions to HTTP, named repository fixtures, or explicit injection; delete compatibility-only assertions.
5. Remove the extension key, all remaining production/test imports, obsolete exports and patch seams, `DemoStore`, and `backend/lab_store.py`.
6. Remove compatibility classifiers/baselines/allowlists, update ownership/architecture/docs and verification commands, and prove forbidden references are absent.
7. Run focused repository/service/API/runtime/architecture suites, the full regression and frontend suites, disposable database initialization, Flask creation/startup checks, syntax compilation, diff checks, and strict OpenSpec validation.

Rollback is a code revert only. No schema or stored-data migration is introduced. If removal exposes a previously unknown external Python consumer, stop rather than restoring an unbounded shim; that compatibility contract requires an explicit scope decision.

## Open Questions

None. The user confirmed immediate deletion of `backend/lab_store.py`, accepted removal of `app.extensions["demo_store"]`, and accepted preservation of only the supported root process-entrypoint contract.
