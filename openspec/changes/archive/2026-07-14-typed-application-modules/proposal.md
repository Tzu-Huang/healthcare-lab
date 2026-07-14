## Why

Healthcare Lab now concentrates HTTP routes, integration clients, workflow logic, runtime components, persistence, and regression tests in a few monolithic files. ZAC-46 through ZAC-52 will expand OIE management substantially, so explicit typed module boundaries are needed first to prevent further coupling while preserving current behavior.

## What Changes

- Add a typed backend package structure for API, services, clients, runtime, repositories, domain rules, templates, configuration, and application assembly.
- Make `app.py` a thin process entrypoint and move Flask construction and dependency assembly to `backend/app_factory.py`.
- Move existing routes into domain Blueprints without changing URLs, payloads, status codes, or runtime semantics.
- Move listener and watcher components into runtime modules and external protocol operations into clients or services.
- Place OIE settings persistence behind an OIE repository, retaining temporary `DemoStore` delegation where compatibility requires it.
- Split tests so they mirror production responsibilities and add an architecture contract test that prevents monolithic logic from returning to `app.py`.
- Add project-level placement guidance, including the modular JavaScript and CSS destinations required for the later ZAC-50 frontend work.
- Preserve all existing application behavior; this change does not implement ZAC-46 through ZAC-52.

## Capabilities

### New Capabilities

- `healthcare-lab-typed-application-architecture`: Defines typed application module boundaries, dependency direction, thin entrypoint and composition rules, mirrored test organization, behavior-preserving migration constraints, and placement guidance for future OIE work.

### Modified Capabilities

None. Existing externally observable capability requirements remain unchanged.

## Impact

- Backend entrypoint, Flask application assembly, API routes, integrations, runtime components, persistence boundaries, and configuration under `app.py` and `backend/`.
- Existing tests in `tests/test_app.py` and new responsibility-oriented test packages.
- Project architecture documentation and future frontend placement under `frontend/static/js/` and categorized CSS directories.
- No new framework, ORM, frontend framework, API contract, persistence semantic, or OIE management behavior.
