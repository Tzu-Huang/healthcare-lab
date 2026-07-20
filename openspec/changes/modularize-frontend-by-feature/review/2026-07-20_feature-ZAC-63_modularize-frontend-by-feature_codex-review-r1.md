---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-63_modularize-frontend-by-feature
base: main
reviewed_head: 79fba5064af0fc99be0902e887204cf9f9f966f5
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P2 | open | Patient and Order initialization always registers listeners; application initialization also registers an unguarded GDT listener. |
| REV-002 | P2 | open | Feature initializers execute sequentially without per-feature error isolation. |
| REV-003 | P2 | open | Six implemented feature families still share one 49 KB `application.css` owner. |
| REV-004 | P2 | open | OIE send duplicates `fetch` and JSON parsing outside the shared client. |

## New blocking findings

### [P2][REV-001] Repeated application initialization duplicates Patient, Order, and GDT handlers

- Evidence: `frontend/static/js/views/patient.js:253-265` and `frontend/static/js/views/order.js:197-210` register every input/change/click listener without an `initialized` guard. `frontend/static/js/views/application.js:248-300` has no application guard and adds the GDT order-flow listener directly at line 300.
- Impact: invoking the published initialization seam more than once causes one user action to execute multiple callbacks or requests. This violates the explicit deterministic-lifecycle acceptance criterion that repeated initialization/navigation must not accumulate handlers.
- Classification: initial-review blocking P2 because it violates an explicit requirement.
- Required resolution: make the application and every feature initializer idempotent, and add an executable browser/unit regression that invokes initialization repeatedly and proves a representative Patient, Order, and GDT action fires once.

### [P2][REV-002] A single feature initialization exception prevents unrelated workspaces from initializing

- Evidence: `frontend/static/js/views/application.js:259-300` calls each initializer in one synchronous sequence with no per-feature boundary. For example, a missing Dashboard element makes `initializeDashboardView()` throw at `frontend/static/js/views/dashboard.js:16`, preventing all later feature initialization. Existing error handling in `core/navigation.js` only wraps asynchronous activation callbacks, not initialization.
- Impact: one malformed or temporarily unavailable feature disables later unrelated workspaces and produces no required feature diagnostic. This directly contradicts the requirement that one feature initialization failure remain diagnosable without silently disabling other views.
- Classification: initial-review blocking P2 because it violates an explicit requirement.
- Required resolution: isolate each feature initializer, record/dispatch a feature-specific initialization error, continue initializing the remaining features, and add a controlled test that injects one initialization failure while proving another workspace remains operable.

### [P2][REV-003] Feature CSS remains consolidated in a catch-all view stylesheet

- Evidence: `frontend/static/css/views/` contains only `application.css` (49,117 bytes) and the reserved `settings.css`. Dashboard, FHIR, dcm4chee, OIE, and GDT rules are selector-scoped inside the same 2,544-line file rather than residing in feature-owned view stylesheets.
- Impact: selector scope prevents leakage but does not establish the required feature stylesheet owners or discoverable placement destination. New feature styling still has to enter a catch-all file, contrary to the explicit `Styles have layered and scoped ownership` scenario.
- Classification: initial-review blocking P2 because it violates an explicit acceptance criterion.
- Required resolution: move implemented feature-only rule groups into named view stylesheets (with shared rules retained only in layout/components), import them in stable cascade order, and extend architecture/characterization tests to reject new feature families in the catch-all owner.

### [P2][REV-004] OIE send bypasses the centralized JSON transport contract

- Evidence: `frontend/static/js/api/oie.js:25-32` calls `fetch`, sets JSON headers, parses JSON, and handles response semantics directly. The only other `fetch` implementations are the shared functions in `frontend/static/js/api/client.js`.
- Impact: OIE send can drift from normalized network, non-JSON, HTTP, and business-failure behavior, while the architecture contract claims common JSON transport/error behavior is centralized.
- Classification: initial-review blocking P2 because it violates an explicit requirement.
- Required resolution: add the response-envelope behavior needed by OIE to the shared client, migrate `sendOieLocalOrder` to it, and test success, HTTP failure, business failure, non-JSON response, and network rejection through the shared contract.

## Follow-up findings

- The 302-line `views/application.js` coordinator still owns substantial Order/dcm4chee rendering and GDT patient-creation behavior. It is a named module rather than a legacy entrypoint, so this does not independently block the current acceptance contract, but further feature ownership work should keep shrinking it instead of adding new branches.

## Verification and residual risk

- Reviewed the complete `main...79fba5064af0fc99be0902e887204cf9f9f966f5` change against the OpenSpec proposal, design, requirements, tasks, production modules, CSS owners, template partials, and focused tests.
- The persisted `/dev-test` round passed 478 full regression tests, 71 focused frontend/browser tests, 125 Flask integration tests, 49 architecture tests, 31 JavaScript syntax checks, and strict OpenSpec validation.
- Those checks do not execute repeated application initialization, injected feature-initializer failure, per-feature stylesheet ownership, or the OIE shared-client failure matrix described above.
- Live external systems remain optional deployment-specific residual risk as documented in `docs/frontend-module-map.md`.

## Next Action

`/dev-fix --review "openspec/changes/modularize-frontend-by-feature/review/2026-07-20_feature-ZAC-63_modularize-frontend-by-feature_codex-review-r1.md"`

Reason: four blocking P2 findings violate explicit ZAC-63 acceptance criteria.
