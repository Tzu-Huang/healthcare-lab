## Why

Healthcare Lab's browser application has accumulated dashboard, patient, order, FHIR, dcm4chee, OIE, and GDT behavior in single catch-all JavaScript, stylesheet, and template files. ZAC-63 must establish discoverable feature ownership before ZAC-50 adds the OIE Settings workspace, while coordinating test relocation with ZAC-64 so the refactor does not lose behavioral coverage.

## What Changes

- Introduce a no-build, native-module frontend structure with categorized core, API, state, component, and feature-view JavaScript destinations.
- Give dashboard, patient, order, FHIR/Medplum, dcm4chee, OIE, GDT, and future Settings UI explicit production and verification owners.
- Split CSS into base, layout, component, and feature-view layers with scoped selectors and a thin compatibility entrypoint.
- Componentize the Flask view markup where doing so reinforces feature ownership, after the JavaScript and CSS boundaries are stable.
- Centralize shared request/error behavior, navigation/bootstrap behavior, application selections, and reusable presentation helpers without changing public API contracts or user workflows.
- Migrate one feature at a time, moving its structural assertions with the production extraction and adding interaction verification for every major view.
- Coordinate with ZAC-64 through a shared feature taxonomy, test-count and assertion-ownership audits, focused verification commands, and a rule that catch-all cleanup occurs only after production and test extraction are both complete.
- Prepare the OIE and Settings destinations early so ZAC-50 adds new UI to the modular structure rather than extending legacy global assets.
- Preserve Flask's no-build static deployment; no frontend framework or bundler is introduced.

## Capabilities

### New Capabilities

- `healthcare-lab-modular-frontend`: Defines feature-owned native JavaScript modules, layered CSS and template ownership, thin entrypoints, dependency direction, compatibility-preserving migration, and interaction verification.

### Modified Capabilities

- `healthcare-lab-typed-application-architecture`: Strengthens the reserved frontend placement guidance into enforced dependency, entrypoint, migration, and production/test ownership rules shared by ZAC-63 and ZAC-64.

## Impact

- Affected production areas: `frontend/static/app.js`, `frontend/static/styles.css`, `frontend/templates/index.html`, and new categorized frontend module, stylesheet, and template-partial paths.
- Affected verification areas: frontend-related assertions currently in `tests/integration/test_app.py`, architecture contract tests, new focused feature suites, and browser interaction smoke coverage.
- Sequencing impact: establish the module/bootstrap foundation and OIE/Settings destinations before ZAC-50 UI implementation; coordinate each extraction increment with ZAC-64 and finish both before deleting compatibility entrypoints or old test locations.
- Compatibility: existing Flask routes, backend APIs, payloads, persisted data, workflow behavior, and no-build deployment remain unchanged.
- Dependencies: no new frontend runtime framework or build dependency; browser support must include native ES modules.
