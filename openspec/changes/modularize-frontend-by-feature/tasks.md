## 1. Characterization and shared ownership

- [x] 1.1 Record the frontend source inventory, global state and function ownership, DOM/view boundaries, CSS selector families, current test collection baseline, and location-bound assertion inventory using the shared ZAC-63/ZAC-64 taxonomy.
- [x] 1.2 Add or relocate characterization tests for navigation, startup, API/error behavior, cross-view selections, feature initialization, responsive layout, and existing representative workflows before moving their implementations.
- [x] 1.3 Define focused verification commands for shared frontend infrastructure and every feature, and document which checks are owned by ZAC-63 versus ZAC-64.
- [x] 1.4 Characterize Flask static-module URL generation and transitive import caching, then select and test a no-build-compatible cache invalidation contract.

## 2. Native-module foundation

- [ ] 2.1 Create the categorized `js/core`, `js/api`, `js/state`, `js/components`, and `js/views` structure plus the thin native-module bootstrap without changing current startup behavior.
- [x] 2.2 Extract shared DOM, clipboard, formatting, status, navigation, JSON request, and normalized error behavior with focused tests and declared dependency direction.
- [x] 2.3 Replace writable cross-view globals with explicit shared navigation/selection state while leaving feature inventory, preview, expansion, and request state in its owning view.
- [x] 2.4 Introduce idempotent feature initialization and activation seams, isolate initialization diagnostics, and verify repeated navigation does not duplicate handlers or requests.
- [x] 2.5 Extend architecture contracts so new catch-all responsibility and invalid frontend dependency direction fail while approved compatibility baselines may only shrink.

## 3. OIE and ZAC-50 integration milestone

- [x] 3.1 Establish empty but owned Settings API, view, state/component, style, template, and focused-test destinations without implementing ZAC-50 product behavior.
- [x] 3.2 Extract OIE endpoint adapters, feature state, rendering/components, listener interactions, and view lifecycle from the catch-all script while preserving OIE console behavior.
- [x] 3.3 Move OIE location-bound structural assertions to their focused owners and add controlled interaction verification for inventory refresh, selection, preview, send, and listener controls.
- [x] 3.4 Verify and document the OIE/Settings foundation milestone that permits ZAC-50 implementation to begin without extending legacy assets.

## 4. Dashboard, Patient, and Order extraction

- [x] 4.1 Extract Dashboard API, state, service/resource/event rendering, actions, and lifecycle; move its assertions and run focused Dashboard verification.
- [x] 4.2 Extract Patient API, state, form validation, protocol previews, record rendering, dcm4chee/FHIR coordination seams, and lifecycle; move its assertions and run focused Patient verification.
- [x] 4.3 Extract Order API, shared patient selection, mode-specific forms and previews, record rendering, dcm4chee actions, and lifecycle; move its assertions and run focused Order verification.
- [x] 4.4 Verify Dashboard-to-Order GDT navigation and Patient-to-Order shared selection remain compatible without direct feature-view imports.

## 5. FHIR, dcm4chee, and GDT extraction

- [x] 5.1 Extract FHIR/Medplum API, feature state, inventory, resource selection, DiagnosticReport rendering, preview/retry interactions, and lifecycle; move its assertions and run focused FHIR verification.
- [ ] 5.2 Extract dcm4chee API, feature state, patient/order selection, result grouping, workflow status/actions, preview/history rendering, and lifecycle; move its assertions and run focused dcm4chee verification.
- [x] 5.3 Extract GDT API, feature state, bridge/watcher controls, patient/order/result/artifact rendering, preview/import/write interactions, and lifecycle; move its assertions and run focused GDT verification.
- [x] 5.4 Audit shared components created during feature extraction and retain them as shared owners only where at least two feature contracts use them without feature-specific branching.

## 6. CSS and template ownership

- [ ] 6.1 Establish base, layout, component, and feature-view CSS layers while preserving the characterized cascade order and making the retained global stylesheet a thin loader.
- [ ] 6.2 Scope feature-only selectors beneath their owning workspace and verify existing responsive behavior at representative desktop and narrow viewport widths.
- [ ] 6.3 Move stabilized Dashboard, Patient, Order, FHIR, dcm4chee, OIE, and GDT markup into feature-owned Flask partials while preserving DOM IDs, accessibility semantics, and route rendering.
- [ ] 6.4 Keep the application shell and sidebar ownership explicit, reserve the Settings include point, and update structural tests so they follow rendered ownership rather than one physical template file.

## 7. Interaction and regression verification

- [ ] 7.1 Add or extend controlled browser smoke coverage for sidebar navigation, startup without unexpected console errors, Dashboard refresh, and representative Patient and Order interactions.
- [ ] 7.2 Add or extend controlled browser smoke coverage for representative FHIR, dcm4chee, OIE, and GDT interactions without live external infrastructure.
- [ ] 7.3 Run syntax/import validation over every JavaScript module, focused feature suites, Flask integration tests, architecture contracts, and the complete regression suite.
- [ ] 7.4 Compare final test collection with the baseline and complete the ZAC-64 assertion-ownership audit, explaining intentional changes rather than treating count equality as sufficient evidence.

## 8. Compatibility cleanup and documentation

- [ ] 8.1 Remove remaining business logic, writable feature globals, and obsolete selectors/markup from compatibility entrypoints only after their production and assertion owners are verified.
- [ ] 8.2 Confirm `app.js` and the global stylesheet are thin bootstrap/loaders, no old test location retains unowned assertions, and architecture baselines shrank without new exceptions.
- [ ] 8.3 Update frontend placement, dependency, lifecycle, caching, feature verification, and ZAC-50/ZAC-64 coordination guidance in project documentation.
- [ ] 8.4 Run the complete quality gate and strict OpenSpec validation, recording any external-runtime browser scenarios that remain explicitly manual.
