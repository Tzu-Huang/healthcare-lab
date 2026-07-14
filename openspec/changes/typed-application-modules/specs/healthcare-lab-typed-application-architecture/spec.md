## ADDED Requirements

### Requirement: Typed application modules own distinct responsibilities
Healthcare Lab SHALL provide typed backend modules for API handling, services, external clients, runtime components, repositories, domain rules, templates, configuration, and application assembly, with project guidance that identifies the correct destination for each responsibility.

#### Scenario: Contributor places new backend behavior
- **WHEN** a contributor consults the project architecture guidance for a route, workflow, protocol integration, runtime listener, persistence operation, domain rule, or generated template
- **THEN** the guidance identifies a responsibility-specific module that does not require adding the implementation to `app.py` or the general-purpose `DemoStore`

### Requirement: Module dependencies follow the declared direction
API modules SHALL map HTTP input and output through services; services SHALL coordinate clients and repositories without Flask request dependencies; clients SHALL remain independent of Flask and SQLite; repositories SHALL remain independent of HTTP response construction; and domain modules SHALL remain framework-independent.

#### Scenario: Architecture dependencies are verified
- **WHEN** the architecture contract tests inspect imports and boundary modules
- **THEN** lower-level client, repository, template, and domain modules do not depend on Flask request handling or higher-level API modules

### Requirement: Process entrypoint remains thin
`app.py` SHALL contain only process entrypoint and compatibility wiring, while `backend/app_factory.py` SHALL own Flask application creation, dependency assembly, Blueprint registration, and configured runtime startup.

#### Scenario: Entrypoint contract is tested
- **WHEN** the architecture contract test inspects `app.py`
- **THEN** it finds no route implementations, SQL operations, external protocol implementations, listener or watcher class implementations, or workflow orchestration

### Requirement: HTTP and runtime behavior remains compatible
The modularization SHALL preserve existing URLs, request and response shapes, HTTP status codes, persistence semantics, integration behavior, and runtime startup and shutdown behavior.

#### Scenario: Existing regression suite runs after extraction
- **WHEN** the full automated test and smoke verification suites execute against the modular application
- **THEN** existing API contracts and runtime workflows continue to pass without consumer migration

### Requirement: Runtime and external integrations have dedicated ownership
Listener, watcher, socket, retry, and lifecycle state implementations SHALL reside in runtime modules, while external HTTP and protocol operations SHALL reside in clients or services according to whether they perform transport or workflow coordination.

#### Scenario: Existing integration behavior is relocated
- **WHEN** an existing listener, watcher, FHIR operation, DICOM operation, or other external integration is extracted from `app.py`
- **THEN** its implementation resides in the declared runtime, client, or service module and retains focused regression coverage

### Requirement: OIE settings persistence uses a repository boundary
OIE settings persistence SHALL be owned by an OIE repository, and new OIE capabilities MUST NOT add persistence methods directly to `DemoStore`; temporary `DemoStore` methods MAY delegate to the repository to preserve compatibility.

#### Scenario: Existing OIE settings caller uses compatibility delegation
- **WHEN** an existing caller invokes a retained `DemoStore` OIE settings method during migration
- **THEN** the call delegates to the OIE repository without changing stored data or transaction semantics

### Requirement: Tests mirror production responsibilities
Automated tests SHALL be organized by API, service, client, runtime, repository, template, integration, or E2E responsibility as applicable, while retaining the existing regression assertions.

#### Scenario: Contributor locates coverage for a module
- **WHEN** a contributor changes a responsibility-specific production module
- **THEN** the corresponding focused tests are available in the matching responsibility-oriented test package

### Requirement: Future frontend work has modular destinations
Project architecture guidance SHALL direct ZAC-50 frontend behavior to categorized API, view, component, and state JavaScript modules and categorized CSS directories rather than extending only the monolithic `app.js` and `styles.css` files.

#### Scenario: ZAC-50 planning selects frontend destinations
- **WHEN** the Settings workspace work is planned
- **THEN** its API access, views, components, state, and styles each have a documented modular destination without requiring a new frontend framework
