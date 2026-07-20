## Context

The browser application currently concentrates approximately 4,800 lines of JavaScript in `frontend/static/app.js`, all styles in `frontend/static/styles.css`, and every workspace in `frontend/templates/index.html`. The files combine bootstrap, navigation, API transport, mutable selections, payload formatting, reusable DOM construction, feature rendering, orchestration, and event registration. Existing Python integration tests also inspect literal content in these catch-all files.

ZAC-63 is a behavior-preserving frontend refactor. ZAC-64 reorganizes the corresponding integration and repository tests, and its instruction to move tests with production extraction means both tickets need the same feature taxonomy and incremental migration boundary. ZAC-50 will add a substantial OIE Settings and managed-Channel workspace, so its destination must exist before that implementation expands the legacy files.

Constraints include Flask static serving, no build step, no new framework, unchanged backend/API/persistence behavior, a dirty-worktree stop boundary during implementation, and browser interaction verification for major views.

## Goals / Non-Goals

**Goals:**

- Give shared frontend infrastructure and every current feature a discoverable implementation owner.
- Enforce one-way dependencies among bootstrap, views, components/state/API modules, and core utilities.
- Keep global assets as thin compatibility entrypoints during incremental migration and remove their business responsibilities by completion.
- Preserve all observable workflows while production code and its assertions move together.
- Establish OIE and Settings destinations early enough for ZAC-50.
- Coordinate ZAC-64 test organization through matching feature names, focused commands, assertion ownership, and collection baselines.

**Non-Goals:**

- Introducing React, Vue, a bundler, npm-based production compilation, or a frontend state framework.
- Redesigning the UI, changing API contracts, modifying backend behavior, or changing stored data.
- Implementing the ZAC-50 Settings experience or managed-Channel lifecycle.
- Completing the broad backend repository/domain test split owned by ZAC-64.
- Replacing all existing integration coverage with browser E2E tests.

## Decisions

### Use native ES modules with a thin bootstrap

`frontend/static/js/app.js` will be loaded with `type="module"` and will only assemble shared context, initialize navigation, and call feature initialization functions. Modules will use browser-native `import` and `export`; no transpilation or bundling is introduced.

This provides enforceable symbol boundaries while retaining no-build deployment. Continuing script-order globals would make extraction less reliable, while adding a bundler would broaden deployment and dependency scope.

The implementation must verify static module URLs and caching behavior. If entrypoint-only asset versioning does not invalidate imported modules, the design will use a Flask-compatible versioned module URL strategy or documented cache headers without adding a build system.

### Organize by responsibility and feature

The target JavaScript ownership is:

```text
frontend/static/js/
  app.js
  core/          DOM, navigation, errors, formatting
  api/           shared client and feature endpoint adapters
  state/         shared navigation and cross-view selections
  components/    reusable presentation and interaction helpers
  views/         dashboard, patient, order, fhir, dcm4chee, oie, gdt, settings
```

Feature API modules express endpoint intent but do not manipulate DOM. Components do not initiate feature requests. State does not import views. Views own feature event binding, rendering coordination, and calls to their API/state/component dependencies. Cross-feature behavior uses an explicit shared state or coordinator instead of importing another feature view's internals.

Settings is reserved immediately even though ZAC-50 owns its behavior. OIE is extracted early because Settings shares its connection/listener/channel concepts.

### Use explicit, idempotent view lifecycle functions

Each major view will expose an initialization function that may be called safely once by bootstrap and an activation function when view navigation requires refresh or focus behavior. Event registration must not duplicate after navigation. A feature initialization failure must produce a diagnostic without silently disabling unrelated views.

This replaces one catch-all `DOMContentLoaded` block and gives browser tests a stable interaction seam.

### Separate shared state from feature state

Shared state is limited to navigation and genuinely cross-workspace selections such as the current patient/order context. FHIR, dcm4chee, OIE, and GDT inventory, preview, expansion, and request state remain owned by their features. State APIs expose explicit reads/updates rather than writable global variables.

A third-party state library is unnecessary for the current application and would violate the dependency constraint.

### Layer CSS and scope feature rules

CSS will be divided into base, layout, component, and view layers. `frontend/static/css/app.css` or the retained `styles.css` will be a thin ordered import/loader entrypoint. View-only selectors must be rooted beneath the owning workspace class. Shared visual behavior moves to a component stylesheet only when multiple views use the same contract.

The migration will preserve current cascade order until selectors are characterized. Splitting only by file size is explicitly rejected because it would not establish ownership.

### Split templates after behavioral module boundaries stabilize

`index.html` will retain the application shell and include feature-owned Flask partials after the matching JS and CSS extraction is verified. Template partials will not introduce new server-side behavior. This sequencing isolates JavaScript/CSS regressions before markup movement and keeps DOM IDs and accessibility behavior compatible.

### Coordinate ZAC-63 and ZAC-64 incrementally

Both tickets use the feature identifiers `dashboard`, `patient`, `order`, `fhir`, `dcm4chee`, `oie`, `gdt`, and `settings`, plus shared `core/components` responsibilities. When ZAC-63 extracts a feature, all assertions tied to the old production location move in the same increment to the matching focused test owner. ZAC-64 owns broad test-file organization, reusable backend fixtures/fakes, collection-count comparison, and the repository/domain/template split. ZAC-63 owns new module contracts and major-view browser interaction coverage.

Neither ticket may delete a legacy source or test location until its responsibilities and assertions have named owners. Test count is a guardrail, not proof by itself; an assertion-ownership inventory must also show that behavior was retained.

### Verify behavior at three levels

- Architecture tests verify dependency direction, thin entrypoints, allowed compatibility seams, and absence of new catch-all responsibility.
- Focused feature tests verify formatting, DOM rendering contracts, API adapters, and structural/template ownership without assuming all behavior lives in one file.
- A small browser smoke suite verifies navigation, initialization without console errors, Dashboard refresh, and representative Patient/Order/OIE/GDT/FHIR/dcm4chee interactions using backend doubles or the local test app.

Browser coverage remains deliberately small; backend API behavior continues to be protected by the existing Python suites.

## Risks / Trade-offs

- **[Native-module caching leaves stale child modules]** → Characterize Flask static caching and implement a no-build-compatible invalidation contract before switching the entrypoint.
- **[Module extraction changes global initialization order]** → Characterize startup and migrate one view at a time behind idempotent lifecycle functions.
- **[Circular imports emerge through shared selections]** → Keep state lower than views and use explicit events/coordinators for cross-view actions.
- **[CSS cascade changes visual behavior]** → Preserve original ordering during extraction, scope new view rules, and add responsive browser snapshots or interaction smoke at representative widths.
- **[Literal-path tests fail or lose assertions]** → Move assertions with each extraction, record ownership, and compare focused/full collection evidence under ZAC-64.
- **[Compatibility entrypoints become permanent dumping grounds]** → Architecture checks prohibit new responsibilities and allow the baseline only to shrink.
- **[ZAC-50 races ahead of the foundation]** → Complete bootstrap, OIE, Settings destinations, and their test seams before ZAC-50 product implementation begins.
- **[Large review surface]** → Commit by infrastructure or single feature, with focused verification after every increment.

## Migration Plan

1. Capture current frontend behavior, architecture baseline, test collection, and assertion ownership; add missing characterization before movement.
2. Add core/bootstrap, API-client, state, component, CSS-layer, and feature-test destinations while retaining legacy entrypoints.
3. Extract OIE shared infrastructure and reserve the Settings view/style/API destinations; verify this integration point before ZAC-50.
4. Extract dashboard, patient, order, FHIR, dcm4chee, OIE, and GDT behavior one feature at a time. Move relevant assertions and run the focused command in the same increment.
5. Split CSS ownership while preserving cascade order, then split Flask view partials while preserving DOM contracts.
6. Run browser interaction smoke for every major view, the complete Python suite, JavaScript syntax/import checks, architecture contracts, and strict OpenSpec validation.
7. Remove remaining catch-all business logic and obsolete test locations only after ZAC-64 ownership and collection/assertion audits are complete.

Rollback is incremental: revert the most recent feature extraction and keep the compatibility entrypoint loading the last verified owner. No database or API rollback is needed because this change does not alter those contracts.

## Open Questions

- Which no-build cache invalidation mechanism best fits Flask's current `asset_version` helper for transitive module imports?
- Should the existing test tooling host the browser smoke directly, or should a minimal Playwright setup be proposed as a separately approved dependency if none exists?
- Does ZAC-50 begin immediately after the OIE/Settings foundation milestone, or wait for every ZAC-63 feature extraction? The recommended answer is the milestone boundary.
