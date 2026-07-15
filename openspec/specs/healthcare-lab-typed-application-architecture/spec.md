# healthcare-lab-typed-application-architecture Specification

## Purpose
TBD - created by archiving change typed-application-modules. Update Purpose after archive.
## Requirements
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

### Requirement: Bounded contexts have an implementation-ready placement map

Healthcare Lab SHALL publish target backend, frontend, and test trees and SHALL assign every current patient, order, FHIR, GDT, OIE, dcm4chee, and lab control-plane responsibility in retained large modules to a named destination. The placement map SHALL identify the responsibility category, current compatibility source, target owner, and mirrored test destination.

#### Scenario: Contributor locates an existing responsibility destination

- **WHEN** a contributor plans to move or extend a responsibility currently held by a large compatibility module
- **THEN** the placement map identifies its bounded context, owning layer and module destination, and corresponding test package

#### Scenario: Contributor places a new responsibility

- **WHEN** an engineer or Codex classifies new behavior by bounded context and by HTTP, workflow, transport, runtime, persistence, domain, template, or composition responsibility
- **THEN** the documented decision process yields a named production destination and mirrored test destination outside the catch-all modules

### Requirement: Compatibility facades are explicit migration seams

Healthcare Lab SHALL enumerate allowed compatibility facades and their owning destinations. A compatibility facade MAY re-export or delegate existing behavior during incremental migration, but MUST NOT own new SQL, payload, workflow, or transport implementation, and new callers MUST import the owning module directly.

#### Scenario: Existing caller uses an allowed facade

- **WHEN** an existing caller still imports a symbol through an enumerated compatibility facade
- **THEN** the facade delegates or re-exports the implementation from its named owner without changing observable behavior

#### Scenario: New behavior targets a compatibility module

- **WHEN** a change attempts to add SQL, payload, workflow, or transport implementation to a compatibility facade or retained catch-all module
- **THEN** the architecture contract rejects the placement and directs the responsibility to its named owner

### Requirement: Catch-all enforcement preserves only a reviewed legacy baseline

Architecture tests SHALL inspect the named backend and frontend catch-all modules for SQL, payload, workflow, and transport implementation. Existing implementation MAY remain through an explicit reviewed baseline so migration can proceed incrementally, but new or materially changed classified implementation MUST be rejected. Removing legacy implementation and shrinking the baseline SHALL remain valid.

#### Scenario: Existing baseline remains during incremental migration

- **WHEN** the architecture contract inspects unchanged classified implementation represented by the reviewed legacy baseline
- **THEN** the contract permits it without requiring a broad extraction

#### Scenario: New monolithic implementation is introduced

- **WHEN** a catch-all module contains classified implementation that is not represented by the reviewed baseline
- **THEN** the architecture test fails with a diagnostic containing category, path, and current source line

#### Scenario: Legacy responsibility is extracted

- **WHEN** implementation moves from a catch-all module to its named owner and the corresponding baseline entry is removed
- **THEN** the architecture contract passes without requiring replacement compatibility implementation

### Requirement: Bounded-context dependencies point inward

Within each bounded context, APIs and runtime composition SHALL invoke services; services SHALL coordinate client and repository ports; clients, repositories, and templates SHALL depend only on allowed lower-level configuration and domain types; domain modules SHALL remain framework-independent; and cross-context coordination SHALL reside in an explicitly named service rather than importing another context's API or concrete repository.

#### Scenario: Architecture dependencies are checked across contexts

- **WHEN** architecture tests inspect imports for patient, order, FHIR, GDT, OIE, dcm4chee, and lab control-plane modules
- **THEN** dependencies follow the published direction and no lower layer imports an API module or unrelated concrete repository
