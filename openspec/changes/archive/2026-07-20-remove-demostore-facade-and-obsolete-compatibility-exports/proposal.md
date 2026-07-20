## Why

Healthcare Lab's persistence, protocol, workflow, and presentation responsibilities now have explicit owners, but production startup still constructs the broad `DemoStore` facade and integration tests reach through `app.extensions["demo_store"]`. With the prerequisite repository, domain/template, service, frontend, and test migrations complete, ZAC-65 can remove this final service-locator-shaped compatibility layer and make application dependencies explicit.

## What Changes

- Add an explicit application-composition owner for the shared database, maintenance lifecycle, repositories, enrichment loaders, coordinators, and narrow service capabilities.
- Replace all production `DemoStore` construction and `store.*` access with named dependencies; services and Blueprints continue to receive only their narrow ports.
- **BREAKING** Remove the internal `backend.lab_store` module, its `DemoStore` facade, delegated methods, duplicate helpers/constants, and compatibility re-exports without a temporary shim.
- **BREAKING** Remove the internal Flask extension key `app.extensions["demo_store"]` without replacing it with another broad container or service locator.
- Migrate integration setup and assertions to HTTP interactions, named repository fixtures, or explicit dependency injection according to test ownership.
- Keep root `app.py` as the supported process entrypoint while removing obsolete test-only patch/import compatibility that is not required by that entrypoint.
- Tighten architecture contracts, shrink legacy baselines and compatibility allowlists, and update architecture/test-ownership documentation.
- Preserve HTTP routes and responses, configuration keys, SQLite schema and stored-data semantics, migrations, protocol payloads, runtime lifecycle, process startup, and external-integration behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `healthcare-lab-typed-application-architecture`: require explicit application composition with no `DemoStore`, broad Flask extension container, forwarding facade, or test-only production compatibility seam, while preserving public and runtime behavior.

## Impact

- Affected production code: `backend/app_factory.py`, `backend/lab_store.py`, composition modules, remaining compatibility import sites, and root `app.py` compatibility wiring.
- Affected verification: integration fixtures and suites, repository compatibility coverage, architecture contracts and legacy baselines, disposable-database startup/runtime checks, and test ownership documentation.
- Internal Python imports of `backend.lab_store`, `DemoStore` methods, the `demo_store` Flask extension key, and obsolete patch paths intentionally break; they are not public contracts.
- No new dependency, schema/data migration, route, frontend, deployment, configuration, or external-protocol change is intended.
