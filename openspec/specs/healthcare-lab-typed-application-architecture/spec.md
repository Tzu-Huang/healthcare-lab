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

### Requirement: Lab control-plane persistence has a dedicated owner

Healthcare Lab SHALL provide a lab control-plane repository that owns lab server registry, persisted health state, and operation history through the shared SQLite connection factory and application write lock. Lab workflow services SHALL depend on a narrow lab repository port rather than requiring `DemoStore` for these operations.

#### Scenario: Lab workflow uses extracted persistence

- **WHEN** a lab workflow lists or updates servers, persists health, or records operation history
- **THEN** the operation is performed by the lab repository using the shared SQLite owner and not by SQL in `DemoStore`

#### Scenario: Concurrent lab writes share coordination

- **WHEN** a legacy `DemoStore` caller and a directly composed lab repository write to the same database
- **THEN** both writes use the same reentrant application lock and retain existing transaction behavior

### Requirement: OIE result persistence has a dedicated owner

Healthcare Lab SHALL provide OIE repositories that own settings and inbound result persistence, including error records, duplicate message-control detection, persisted matching references, and result row mapping. OIE services and runtime listeners SHALL depend on narrow OIE ports for these operations.

#### Scenario: Inbound OIE result is persisted

- **WHEN** the OIE listener accepts a valid, duplicate, unmatched, or invalid result message
- **THEN** the OIE result repository preserves the current record, matching, duplicate, error, and response semantics without SQL in `DemoStore`

#### Scenario: OIE workbench crosses bounded contexts

- **WHEN** the OIE workbench combines patient, order, and OIE result data
- **THEN** a service coordinates the required narrow ports and the OIE repository remains limited to OIE-owned persistence

### Requirement: OpenEMR external query ownership is separate from SQLite persistence

Healthcare Lab SHALL isolate OpenEMR MariaDB connection and procedure-order query behavior in a dedicated external adapter. OpenEMR row normalization and conversion to the existing GDT order projection SHALL remain framework-independent, and no OpenEMR SQL SHALL be owned by a SQLite repository or `DemoStore`.

#### Scenario: Query configured OpenEMR procedure orders

- **WHEN** the application lists or verifies configured OpenEMR ECG procedure orders
- **THEN** the external adapter executes the MariaDB query and returns the same order and verification projections as before extraction

#### Scenario: OpenEMR schema is unavailable

- **WHEN** the configured MariaDB reports a supported missing procedure-order table condition
- **THEN** the adapter preserves the existing empty-list or degraded verification behavior without changing SQLite state

### Requirement: Extracted boundaries retain compatibility-only DemoStore seams

`DemoStore` SHALL expose only explicit delegation for retained lab and OIE methods needed by existing callers. New composition and service code MUST use the owning repository or external adapter directly, and architecture enforcement SHALL remove the extracted implementation from the reviewed legacy baseline without adding replacement exceptions.

#### Scenario: Existing caller uses DemoStore

- **WHEN** an existing caller invokes a retained lab or OIE persistence method on `DemoStore`
- **THEN** `DemoStore` delegates to the owning repository and returns the existing result shape and errors

#### Scenario: Architecture contract inspects extraction

- **WHEN** architecture tests inspect `lab_store.py` and the responsibility-specific modules
- **THEN** extracted SQL and OpenEMR query implementation are absent from `lab_store.py`, lower layers follow the declared dependency direction, and no new legacy-baseline exception is required

### Requirement: Repository extraction verification is isolated and behavior-preserving

Automated verification SHALL cover the extracted repositories, external adapter, domain mapping, service ports, compatibility delegates, and architecture boundaries using disposable SQLite databases and external-service test doubles.

#### Scenario: Run extraction verification

- **WHEN** focused and full automated tests execute
- **THEN** no repository `instance/*.db` or live OpenEMR/OIE service is accessed and existing APIs, stored data semantics, and startup behavior remain compatible

### Requirement: Patient persistence has dedicated repository ownership

Healthcare Lab SHALL provide a patient repository that owns local patient-record SQL and row projection through the shared SQLite connection factory and application write lock. Patient workflow services MUST depend on narrow patient and explicit protocol-coordination ports rather than requiring `DemoStore`.

#### Scenario: Patient workflow creates and reads patients

- **WHEN** a patient workflow creates, lists, or reads a local Patient
- **THEN** patient-record persistence is performed by the patient repository without SQL in `DemoStore`
- **AND** the API projection and protocol filtering remain compatible

#### Scenario: Patient service dependencies are inspected

- **WHEN** application composition constructs the Patient workflow service
- **THEN** the service receives only its declared patient and protocol-coordination collaborators
- **AND** it does not receive the general `DemoStore` facade

### Requirement: Identifier allocation remains transaction-safe

Healthcare Lab SHALL isolate local identifier-sequence SQL behind a dedicated persistence boundary while preserving the existing application lock and transaction semantics. Patient MRN allocation, collision checking, and patient insertion MUST remain one atomic write operation.

#### Scenario: Automatic MRN allocation shares the patient transaction

- **WHEN** Patient creation omits an MRN
- **THEN** the allocator advances the persistent sequence and skips occupied candidates using the Patient creation connection and lock
- **AND** the Patient row is inserted before that transaction commits

#### Scenario: Patient creation rolls back

- **WHEN** Patient creation fails after identifier selection but before successful completion
- **THEN** no partial Patient row or independently committed identifier reservation is exposed
- **AND** the database remains usable for a later allocation attempt

#### Scenario: Existing database contains historical duplicate identifiers

- **WHEN** an existing database is opened during or after the extraction
- **THEN** startup does not add a uniqueness constraint, renumber records, or delete historical rows
- **AND** new automatic and explicit identifier collision behavior remains compatible

### Requirement: Generic order persistence has dedicated repository ownership

Healthcare Lab SHALL provide an order repository that owns generic local order SQL, protocol-filtered reads, row projection, identifier finalization, and send-result updates through the shared SQLite connection factory and application write lock. Order workflow services MUST depend on narrow order and explicit protocol-coordination ports rather than requiring `DemoStore`.

#### Scenario: Generic order is created

- **WHEN** a workflow creates a local Order
- **THEN** the order repository inserts and finalizes the record in one transaction
- **AND** local and placer order identifiers retain their row-ID-derived format and collision safety

#### Scenario: Order send result is recorded

- **WHEN** a send attempt records an ACK or transport error for an Order
- **THEN** the order repository owns the update SQL
- **AND** status, ACK fields, transport error, sent timestamp, updated timestamp, and returned projection remain compatible

#### Scenario: Order service dependencies are inspected

- **WHEN** application composition constructs the Order workflow service
- **THEN** the service receives only its declared order and protocol-coordination collaborators
- **AND** it does not receive the general `DemoStore` facade

### Requirement: Patient and order rules are separate from persistence

Patient and order validation, normalization, and identifier-format rules SHALL reside in framework-independent domain modules. HL7, FHIR, GDT, and DICOM patient/order payload generation SHALL reside in template modules independent of Flask and SQLite, while repository modules SHALL own SQL without implementing protocol payload rules.

#### Scenario: Patient or order input is validated

- **WHEN** a Patient or Order creation request is processed
- **THEN** validation and normalization use the matching domain implementation
- **AND** validation messages and accepted values remain compatible

#### Scenario: Protocol payload is generated during an atomic write

- **WHEN** payload generation requires an assigned Patient or Order record identifier
- **THEN** the repository may invoke an injected pure template collaborator inside its transaction
- **AND** the template implementation does not execute SQL or depend on Flask

### Requirement: Patient and order extraction preserves compatibility

Healthcare Lab SHALL retain only explicit compatibility delegation for existing patient and order `DemoStore` methods and SHALL verify the extraction using disposable SQLite databases and external-service doubles. Extracted architecture baseline entries MUST be removed without adding or refreshing exceptions for replacement implementation.

#### Scenario: Existing caller uses a retained DemoStore method

- **WHEN** an existing caller invokes a retained patient or order method through `DemoStore`
- **THEN** the facade delegates to the owning repository or explicit coordinator
- **AND** it preserves the existing return shape and errors without owning SQL, validation, payload, or workflow implementation

#### Scenario: Extraction verification runs

- **WHEN** focused and full verification execute
- **THEN** Patient and Order API shapes, protocol filters, identifier behavior, deterministic payload content, stored-data semantics, and transaction behavior remain compatible
- **AND** no real `instance/*.db` or live external service is accessed

#### Scenario: Architecture contract inspects the extraction

- **WHEN** architecture tests inspect `lab_store.py`, patient/order modules, and the reviewed legacy baseline
- **THEN** extracted implementation is absent from `DemoStore`, dependency direction is preserved, and no replacement baseline exception is required

### Requirement: dcm4chee persistence has three dedicated owners

Healthcare Lab SHALL separate dcm4chee patient-sync, MWL, and result persistence into dedicated repositories using the shared SQLite connection factory and application write lock. Each repository SHALL own the SQL and row projections for its ledger and SHALL NOT depend on `DemoStore`.

#### Scenario: Patient sync is persisted

- **WHEN** a Patient sync mapping or attempt is created, read, retried, or completed
- **THEN** the patient-sync repository performs the persistence operation
- **AND** existing status, ACK, error, retry, timestamp, and projection behavior is preserved

#### Scenario: MWL state is persisted

- **WHEN** an MWL mapping, create/readback attempt, or verification result is recorded or queried
- **THEN** the MWL repository performs the persistence operation
- **AND** stable identifiers, retry behavior, and verification projections remain compatible

#### Scenario: Result state is persisted

- **WHEN** a DICOM result, reconciliation diagnostic, duplicate candidate, refresh run, or refresh snapshot is recorded or queried
- **THEN** the result repository performs the persistence operation
- **AND** reconciliation precedence, refresh visibility, generation ordering, and duplicate behavior remain compatible

### Requirement: dcm4chee repository boundaries exclude protocol and workflow behavior

DICOM payload construction, response parsing, UID and identifier rules, retry/status policy, and cross-context fixture, evidence, simulated-return, and refresh coordination SHALL reside in framework-independent domain/template modules or explicit services rather than dcm4chee repositories.

#### Scenario: Repository implementation is inspected

- **WHEN** architecture checks inspect the dcm4chee repositories
- **THEN** repository modules contain persistence and row-projection behavior only
- **AND** they do not perform HTTP/MLLP transport, construct ADT/MWL payloads, parse transport response bodies, or orchestrate patient/order workflows

### Requirement: dcm4chee services use narrow capability ports

Patient, order, and dcm4chee workflow services SHALL receive explicit patient-sync, MWL, result, and other required bounded-context capabilities instead of the general `DemoStore` facade or an arbitrarily forwarding wrapper.

#### Scenario: Application composition is inspected

- **WHEN** the composition root constructs patient, order, and dcm4chee workflows
- **THEN** each workflow receives only its declared ledger and coordination capabilities
- **AND** cross-ledger work is performed by an explicit service or named coordinator

### Requirement: dcm4chee extraction preserves compatibility and autonomous safety

Healthcare Lab SHALL retain only mechanical `DemoStore` delegates needed by existing callers and SHALL verify the extraction using disposable databases and external-service doubles. Unattended implementation MUST stop before destructive data changes, live-service access, public compatibility changes, architecture-baseline expansion, new dependencies, or unrelated scope expansion.

#### Scenario: Existing caller uses a compatibility method

- **WHEN** an existing caller invokes a retained dcm4chee method on `DemoStore`
- **THEN** the facade delegates to the owning repository, pure helper, or explicit coordinator
- **AND** it contains no replacement SQL, payload, parsing, or workflow implementation

#### Scenario: Extraction verification runs

- **WHEN** focused and full automated verification execute
- **THEN** only disposable databases and external-service doubles are used
- **AND** retry, reconciliation, duplicate, refresh, backfill, API, payload, and stored-data semantics remain compatible
- **AND** extracted architecture-baseline entries are removed without adding or refreshing replacement exceptions
