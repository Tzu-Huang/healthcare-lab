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
| core | DOM, status, request, navigation, formatting, clipboard | application shell | `js/core`, `js/api/client.js`, `js/state` | `css/base`, `css/layout`, `css/components` | `index.html`, `partials/sidebar.html` |
| dashboard | service/resource/event state and actions | `lab-console-view` | `js/api/dashboard.js`, `js/views/dashboard.js` | `css/views/dashboard.css` | `views/dashboard.html` |
| patient | forms, validation, protocol previews and inventory | `patient-view` | `js/api/patients.js`, `js/views/patient.js` | `css/views/patient.css` | `views/patient.html` |
| order | protocol modes, previews, creation and record inventory | `order-view` | `js/api/orders.js`, `js/views/order.js` | `css/views/order.css` | `views/order.html` |
| fhir | Medplum inventory, selections, reports, preview and retry | `medplum-view` | `js/api/fhir.js`, `js/views/fhir.js` | `css/views/fhir.css` | `views/fhir.html` |
| dcm4chee | profile, selections, MWL actions, results and attempts | `dcm4chee-view` | `js/api/dcm4chee.js`, `js/views/dcm4chee.js` | `css/views/dcm4chee.css` | `views/dcm4chee.html` |
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

## Assertion ownership

| Existing location | Current assertion type | Migration owner |
|---|---|---|
| `tests/test_architecture_contract.py` | global-definition and selector fingerprints | shared architecture contract |
| `tests/integration/test_app.py:230` | static application script contract | core bootstrap/modules |
| `tests/integration/test_app.py:334` | shell/template navigation contract | core navigation/template |
| `tests/integration/test_app.py:2680` | dcm4chee template and script interaction structure | dcm4chee |
| `tests/integration/test_app.py:2758` | dcm4chee responsive/style structure | dcm4chee |
| `tests/repositories/test_lab_store.py:991` | rendered GDT template contract | gdt |

ZAC-63 owns new module-direction, lifecycle, static-loading, and browser
interaction checks. ZAC-64 owns broad test-file relocation, reusable backend
fixtures/fakes, independent responsibility suites, final collected-test count,
and assertion-ownership audit.

## Focused verification commands

Until individual feature suites are extracted, each feature uses the matching
integration selection plus the shared architecture contract:

```powershell
python -m unittest tests.test_architecture_contract
python -m unittest tests.frontend.test_frontend_characterization
python -m unittest tests.integration.test_app
python -m unittest tests.repositories.test_lab_store
node --check frontend\static\app.js
```

Every extraction commit must narrow this to its new module tests while retaining
the relevant legacy integration selection. The completion gate is:

```powershell
python -m unittest discover -s tests -t .
openspec validate modularize-frontend-by-feature --strict
```

## Static module caching contract

Healthcare Lab keeps native modules as directly served Flask static assets.
The HTML entrypoint uses the existing `asset_version()` mtime query parameter.
Transitive modules use stable relative URLs and Flask's default conditional
revalidation (`SEND_FILE_MAX_AGE_DEFAULT` remains unset/`None`), so a browser
reload revalidates changed child modules instead of retaining a long-lived
immutable response. Architecture/integration verification must reject a
positive static `max-age` unless a transitive versioning strategy is introduced.

## OIE and Settings integration milestone

The ZAC-50 integration milestone is complete when `frontend/static/js/views/oie.js`
owns the operational OIE workbench state, rendering, send, and listener lifecycle;
`frontend/static/js/api/oie.js` owns OIE endpoint access; and the reserved Settings
API/view/state/component/style/template destinations remain free of product
behavior. ZAC-50 may build its Settings workspace on those owners and MUST NOT
add OIE or Settings business behavior back to `frontend/static/app.js`.
