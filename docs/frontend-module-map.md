# Frontend Module and Verification Map

This is the ZAC-63 production ownership map and the shared ZAC-64 assertion
ownership baseline. Both changes use the feature names in this document.

## Baseline

Captured on 2026-07-18 from commit `9264dae` before product extraction:

- `frontend/static/app.js`: 195,008 bytes; shared bootstrap plus every feature.
- `frontend/static/styles.css`: 53,447 bytes; base, layout, component, and view rules.
- `frontend/templates/index.html`: 44,580 bytes; application shell plus seven views.
- Full verification: `python -m unittest discover -s tests -t .` — 403 tests passed.
- Architecture contract: reviewed JavaScript definition and CSS selector-family
  fingerprints may shrink but may not grow.

The baseline test count is a regression signal, not proof that assertions were
preserved. The location-bound assertions below must acquire a named owner before
their old read path is removed.

## Production ownership

| Owner | Current JavaScript area | View root | Target JavaScript | Target CSS | Template owner |
|---|---|---|---|---|---|
| core | DOM, status, request, navigation, formatting, clipboard | application shell | `js/core`, `js/api/client.js`, `js/state` | `css/base.css`, `css/layout.css`, `css/components.css` | `index.html`, `shell/sidebar.html` |
| dashboard | service/resource/event state and actions | `lab-console-view` | `js/api/dashboard.js`, `js/views/dashboard.js` | `css/views/dashboard.css` | `views/dashboard.html` |
| patient | forms, validation, protocol previews and inventory | `patient-view` | `js/api/patient.js`, `js/state/patient.js`, `js/views/patient.js` | `css/views/patient.css` | `views/patient.html` |
| order | protocol modes, previews, creation and record inventory | `order-view` | `js/api/order.js`, `js/state/order.js`, `js/views/order.js` | `css/views/order.css` | `views/order.html` |
| fhir | Medplum inventory, selections, reports, preview and retry | `medplum-view` | `js/api/fhir.js`, `js/views/fhir.js` | `css/views/fhir.css` | `views/fhir.html` |
| dcm4chee | profile, selections, MWL actions, results and attempts | `dcm4chee-view` | `js/api/dcm4chee.js`, `js/state/dcm4chee.js`, `js/views/dcm4chee.js` | `css/views/dcm4chee.css` | `views/dcm4chee.html` |
| oie | inventory, selection, payloads, send and listener controls | `oie-view` | `js/api/oie.js`, `js/views/oie.js` | `css/views/oie.css` | `views/oie.html` |
| gdt | bridge settings/watcher, patients, orders, results and artifacts | `gdt-view` | `js/api/gdt.js`, `js/views/gdt.js` | `css/views/gdt.css` | `views/gdt.html` |
| settings | reserved for ZAC-50; no product behavior in ZAC-63 | `settings-view` | `js/api/settings.js`, `js/views/settings.js` | `css/views/settings.css` | `views/settings.html` |

Shared component ownership is earned by use from at least two feature contracts;
otherwise presentation remains inside its feature. Cross-view patient/order
selection belongs to `js/state/selection.js`; feature inventory and preview
state remain with the feature.

### Shared-owner audit

| Shared owner | Consumers | Decision |
|---|---|---|
| `components/status.js` | dashboard, patient, order, FHIR, OIE, and GDT views | Retain: all consumers use the same status text/state presentation contract without feature branching. |
| `components/settings-shell.js` | Settings view only | Reserved destination rather than a reusable component; it contains only the ZAC-50 boundary message and must not acquire cross-feature behavior. |
| `core/dom.js` | every implemented feature view | Retain: generic element lookup/construction and table-cell helpers. |
| `core/clipboard.js` | FHIR, OIE, and GDT views plus the compatibility coordinator | Retain: shared clipboard interaction with no feature branching. |
| `core/formatting.js` | patient, order, FHIR, OIE, and GDT views plus the compatibility coordinator | Retain: protocol/display formatting primitives shared without workflow ownership. |
| `core/navigation.js` | application bootstrap | Retain as application-shell infrastructure, not a feature component. |

No feature-specific renderer or request workflow qualifies as a shared
component. Such behavior remains in its owning view/API module even when the
bootstrap temporarily coordinates it during extraction.

## Dependency direction

```text
js/app.js -> views -> api / state / components -> core
```

- API modules do not manipulate DOM.
- Components do not initiate feature workflows.
- State modules do not import views.
- Views do not import another view's private implementation.
- Compatibility entrypoints receive no new business logic.

## Final assertion ownership audit

| Assertion family | Final owner | Audit result |
|---|---|---|
| Entrypoint growth, dependency direction, and legacy baselines | `tests/test_architecture_contract.py` | Retained as a cross-feature architecture contract; function and selector legacy baselines are empty. |
| Shell navigation, template includes, CSS loading, caching, and selector scope | `tests/frontend/test_frontend_characterization.py` | Moved to the focused frontend owner and follows all template partials rather than one physical file. |
| Dashboard module behavior | `tests/frontend/test_dashboard_view_module.py` and controlled major-view smoke | Focused owner present. |
| Patient API/state/view behavior | `tests/frontend/test_patient_*` and controlled major-view smoke | Focused owners present; integration tests retain only rendered/cross-workspace contracts. |
| Order API/state/view behavior | `tests/frontend/test_order_*` and controlled major-view smoke | Focused owners present; integration tests retain only rendered/cross-workspace contracts. |
| FHIR API/view behavior | `tests/frontend/test_fhir_api_module.py` and controlled major-view smoke | Focused owner present. |
| dcm4chee API/state/view behavior | `tests/frontend/test_dcm4chee_*` and controlled major-view smoke | Focused owners present. |
| OIE view and end-to-end controlled interactions | `tests/frontend/test_oie_view_module.py`, `test_oie_interactions.py` | Focused owner present; no live OIE dependency. |
| GDT view and controlled interactions | `tests/frontend/test_gdt_view_module.py` and controlled major-view smoke | Focused owner present; no live filesystem watcher dependency. |
| Shared selection, formatting, navigation, and component contracts | matching modules under `tests/frontend/` | Focused owners present and shared consumers are documented above. |

ZAC-63 owns new module-direction, lifecycle, static-loading, and browser
interaction checks. ZAC-64 may continue broad backend test-file relocation,
fixture/fake reuse, and responsibility-suite independence without moving these
frontend-focused owners back into a catch-all suite.

### Final collection comparison

- Baseline at `9264dae`: 403 tests.
- Final ZAC-63 discovery inventory before `/dev-test`: 478 tests.
- Net change: +75 tests.

The increase is intentional: it adds API/state/view module contracts,
cross-view coordination, template/CSS ownership, cache/loading checks, and
controlled browser interactions. No assertion was removed to force count
equality. The audit above traces each frontend responsibility to a focused or
explicitly cross-boundary owner.

## Focused verification commands

Use the focused frontend suites during implementation and reserve the complete
suite for `/dev-test`:

```powershell
python -m unittest tests.test_architecture_contract
python -m unittest tests.frontend.test_frontend_characterization
python -m unittest discover -s tests/frontend -t .
python -m unittest tests.frontend.test_major_view_interactions tests.frontend.test_oie_interactions
```

Every extraction commit must narrow this to its new module tests while retaining
the relevant legacy integration selection. The completion gate is:

```powershell
python -m unittest discover -s tests -t .
openspec validate modularize-frontend-by-feature --strict
```

JavaScript syntax verification must recurse over every `frontend/static/**/*.js`
file rather than checking only the compatibility entrypoint.

## Static module caching contract

Healthcare Lab keeps native modules as directly served Flask static assets.
The HTML entrypoint uses the existing `asset_version()` mtime query parameter.
Transitive modules use stable relative URLs and Flask's default conditional
revalidation (`SEND_FILE_MAX_AGE_DEFAULT` remains unset/`None`), so a browser
reload revalidates changed child modules instead of retaining a long-lived
immutable response. Architecture/integration verification must reject a
positive static `max-age` unless a transitive versioning strategy is introduced.

## OIE and Settings integration milestone

`frontend/static/js/views/oie.js` owns the operational OIE workbench state,
rendering, send, and process-local listener controls; it does not edit listener
endpoints. The Settings API/view/state/component/style/template owners provide
the persisted listener configuration surface and the unapplied-runtime reminder.
Later ZAC-50 managed-Channel behavior must extend those categorized owners and
MUST NOT add OIE or Settings business behavior back to `frontend/static/app.js`.

## External-runtime boundary

The controlled Chromium suites cover application startup, navigation,
responsive layout, and representative interactions without live services.
Real Medplum authentication, dcm4chee DICOMweb/MWL traffic, OIE MLLP sockets,
and GDT watcher filesystem interoperability remain environment-specific manual
or deployment verification. They are not hidden browser-test skips and are
covered by their existing integration/deployment runbooks.
