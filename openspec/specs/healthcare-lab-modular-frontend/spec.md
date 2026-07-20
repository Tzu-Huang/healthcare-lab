# healthcare-lab-modular-frontend Specification

## Purpose
TBD - created by archiving change modularize-frontend-by-feature. Update Purpose after archive.
## Requirements
### Requirement: Frontend responsibilities have named module owners

Healthcare Lab SHALL provide named core, API, state, component, and feature-view JavaScript owners for dashboard, patient, order, FHIR, dcm4chee, OIE, GDT, and Settings behavior without requiring a frontend framework or build step.

#### Scenario: Contributor locates frontend behavior
- **WHEN** a contributor changes shared transport, application state, reusable presentation, or feature interaction behavior
- **THEN** the categorized frontend structure identifies one owning module outside the legacy catch-all implementation

### Requirement: Frontend dependencies follow the declared direction

The frontend bootstrap SHALL initialize views; views SHALL coordinate feature API, state, component, and core modules; API modules MUST NOT manipulate DOM; components MUST NOT initiate feature API workflows; state modules MUST NOT import views; and cross-feature coordination MUST use an explicit shared state or coordinator rather than another view's internal implementation.

#### Scenario: Module imports are inspected
- **WHEN** architecture verification inspects new and changed frontend imports
- **THEN** dependencies follow the declared direction and no lower-level module imports a feature view or bootstrap implementation

### Requirement: Browser bootstrap and view lifecycle are deterministic

The browser application SHALL use a thin no-build bootstrap and explicit feature initialization so event handlers are registered once, navigation remains compatible, and one feature's initialization failure is diagnosable without silently disabling unrelated views.

#### Scenario: User navigates repeatedly
- **WHEN** a user activates the same workspace multiple times
- **THEN** its controls execute each interaction once and do not accumulate duplicate event handlers or background requests

#### Scenario: Feature initialization fails
- **WHEN** one feature cannot complete initialization
- **THEN** the application exposes a diagnostic and other independently initialized workspaces remain operable

### Requirement: Shared requests, errors, and state are not duplicated

Healthcare Lab SHALL centralize common JSON request and error normalization behavior and SHALL expose explicit shared-state operations for genuinely cross-workspace selections while retaining feature-local inventory, preview, expansion, and request state within the owning feature.

#### Scenario: Feature performs an API operation
- **WHEN** a feature requests Healthcare Lab JSON data and receives success, HTTP failure, business failure, or network failure
- **THEN** it uses the shared transport/error contract and presents a compatible actionable result without duplicating transport logic

#### Scenario: Selection crosses workspaces
- **WHEN** a patient or order selection is intentionally reused by another workspace
- **THEN** the selection passes through an explicit shared-state or coordination API rather than a writable global or another view's private state

### Requirement: Styles have layered and scoped ownership

Frontend styles SHALL be organized into base, layout, component, and feature-view owners; feature-specific selectors SHALL be scoped beneath the owning workspace; and any retained global stylesheet SHALL be a thin ordered loader or compatibility entrypoint by completion.

#### Scenario: Feature adds visual behavior
- **WHEN** a contributor adds styling used by only one workspace
- **THEN** the rule resides in that feature's view stylesheet and is scoped so it does not affect unrelated workspaces

#### Scenario: Shared component is styled
- **WHEN** multiple workspaces use the same documented component contract
- **THEN** its shared styling resides in a component stylesheet and preserves the established cascade and responsive behavior

### Requirement: Template ownership follows stable feature boundaries

The Flask application shell SHALL retain application-level structure while major workspace markup SHALL have feature-owned template destinations where decomposition is useful. Template extraction MUST preserve DOM identifiers, accessibility semantics, route rendering, and client-side interaction contracts.

#### Scenario: Workspace markup is extracted
- **WHEN** a stabilized feature view moves from the catch-all template to a Flask partial
- **THEN** the rendered application exposes the same interaction hooks and accessibility behavior without adding server-side workflow logic

### Requirement: Frontend migration preserves behavior incrementally

Each feature extraction SHALL preserve existing API, payload, workflow, navigation, rendering, and responsive behavior; SHALL move location-bound assertions before deleting their old location; and SHALL keep compatibility entrypoints thin and prohibited from receiving new business responsibility.

#### Scenario: Feature moves to its owner
- **WHEN** production behavior is extracted from a catch-all frontend asset
- **THEN** its existing assertions move to a named focused owner in the same implementation increment and focused verification passes

#### Scenario: New work targets a catch-all asset
- **WHEN** a change attempts to add new feature API, state, rendering, or workflow behavior to a compatibility entrypoint
- **THEN** architecture verification rejects the placement and identifies the categorized owner

### Requirement: ZAC-50 uses the modular OIE and Settings foundation

The modular frontend SHALL establish OIE and Settings API, view, state/component, style, template, and verification destinations before ZAC-50 implements its Settings and managed-Channel UI.

#### Scenario: ZAC-50 product implementation begins
- **WHEN** the OIE Settings workspace adds connection, listener, or managed-Channel interactions
- **THEN** the implementation uses the modular destinations and does not extend legacy global business logic

### Requirement: Major views have interaction verification

Automated verification SHALL exercise sidebar navigation, initialization without unexpected browser errors, and representative interactions for dashboard, patient, order, FHIR, dcm4chee, OIE, GDT, and Settings when Settings becomes implemented. Verification SHALL retain existing backend regression coverage and MUST NOT depend on live external services.

#### Scenario: Frontend refactor reaches a quality gate
- **WHEN** focused or full frontend verification runs
- **THEN** each implemented major view initializes and performs its representative interaction using the test application and controlled doubles without live OIE, Medplum, dcm4chee, OpenEMR, or GDT infrastructure

### Requirement: ZAC-63 and ZAC-64 share verification ownership

ZAC-63 and ZAC-64 SHALL use the same feature taxonomy, SHALL retain an assertion-ownership inventory in addition to test-count comparison, and MUST complete production and test ownership before deleting catch-all source or test locations. ZAC-63 SHALL own new frontend architecture and interaction checks, while ZAC-64 SHALL own broad test organization, reusable fixtures/fakes, and responsibility-suite independence.

#### Scenario: Production extraction and test reorganization overlap
- **WHEN** a frontend feature is extracted while ZAC-64 reorganizes its tests
- **THEN** the feature's production and assertion owners remain traceable, its focused verification command runs independently, and no assertion is discarded solely because its former file path changed
