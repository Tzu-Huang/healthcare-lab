# healthcare-lab-typed-application-architecture Specification

## Purpose
TBD - created by archiving change typed-application-modules. Update Purpose after archive.
## Requirements
### Requirement: Typed application modules own distinct responsibilities

Healthcare Lab SHALL provide typed backend modules for API handling, services, external clients, runtime components, repositories, domain rules, templates, mappers, configuration, and application assembly, with project guidance that identifies the correct destination for each responsibility.

#### Scenario: Contributor places new backend behavior

- **WHEN** a contributor consults the project architecture guidance for a route, workflow, protocol integration, runtime listener, persistence operation, domain rule, generated template, or reusable boundary projection
- **THEN** the guidance identifies a responsibility-specific module that does not require adding the implementation to `app.py`, the general-purpose `DemoStore`, or a persistence repository that does not own that responsibility

### Requirement: Module dependencies follow the declared direction

API modules SHALL map HTTP input and output through services; services SHALL coordinate clients and repositories without Flask request dependencies; clients SHALL remain independent of Flask and SQLite; repositories SHALL remain independent of HTTP response and presentation implementation; templates and mappers SHALL remain pure; and domain modules SHALL remain framework-independent. Repositories MAY invoke domain validators, template builders, or mapper projectors needed by a persistence operation without owning those implementations.

#### Scenario: Architecture dependencies are verified

- **WHEN** the architecture contract tests inspect imports and boundary modules
- **THEN** lower-level client, repository, template, mapper, and domain modules do not depend on Flask request handling or higher-level API modules
- **AND** mapper modules do not depend on SQLite connection APIs or repository implementations

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

Automated tests SHALL be organized by API, service, client, runtime, repository, domain, template, integration, compatibility, or E2E responsibility as applicable, while retaining the existing regression assertions. Each responsibility SHALL have a named owner, reusable setup SHALL remain separate from behavior assertions, and focused suites SHALL be independently runnable.

#### Scenario: Contributor locates coverage for a module

- **WHEN** a contributor changes a responsibility-specific production module
- **THEN** the corresponding focused tests are available in the matching responsibility-oriented test package
- **AND** the test owner is recorded in the project assertion-ownership inventory

#### Scenario: Shared setup is extracted

- **WHEN** multiple responsibility suites require the same disposable database, application factory, or external-service fake
- **THEN** the setup is reusable without moving feature assertions into the helper or a new catch-all test module

#### Scenario: Responsibility suite runs independently

- **WHEN** a focused verification command runs for one responsibility
- **THEN** that suite executes without importing unrelated live services, committed databases, or another feature's private test state

#### Scenario: Existing catch-all coverage is reorganized

- **WHEN** assertions move out of a broad integration or store test file
- **THEN** every retained assertion has a named new owner before the old location is removed
- **AND** test-ID and collection-count comparison explains intentional additions or removals

### Requirement: Future frontend work has modular destinations
Project architecture guidance SHALL direct ZAC-50 and later frontend behavior to categorized core, API, view, component, and state JavaScript modules; layered base, layout, component, and view CSS directories; and feature-owned Flask template destinations rather than extending the monolithic `app.js`, `styles.css`, or `index.html` files. The guidance SHALL define dependency direction, thin compatibility entrypoints, matching production/test feature names, and the milestone at which OIE and Settings destinations are ready for ZAC-50 without requiring a frontend framework or build system.

#### Scenario: ZAC-50 planning selects frontend destinations
- **WHEN** the Settings workspace work is planned or implemented
- **THEN** its API access, views, components, state, styles, markup, and focused verification each have a documented modular destination
- **AND** new Settings business behavior is not added to a legacy catch-all entrypoint

#### Scenario: Frontend production and test ownership are coordinated
- **WHEN** ZAC-63 extracts a feature and ZAC-64 reorganizes the related tests
- **THEN** architecture guidance identifies matching feature owners, allowed compatibility seams, assertion-migration responsibility, and the focused verification command required before cleanup

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

Healthcare Lab SHALL provide OIE repositories that own settings and inbound result persistence, including error records, duplicate message-control detection, and persisted matching references. OIE validation and row presentation SHALL reside in pure domain or mapper owners, and OIE services and runtime listeners SHALL depend on narrow OIE ports.

#### Scenario: Inbound OIE result is persisted

- **WHEN** the OIE listener accepts a valid, duplicate, unmatched, or invalid result message
- **THEN** the OIE result repository preserves the current record, matching, duplicate, error, and response semantics without SQL in `DemoStore`
- **AND** it invokes pure validation or presentation collaborators rather than implementing those responsibilities

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

Healthcare Lab SHALL provide a patient repository that owns local patient-record SQL through the shared SQLite connection factory and application write lock. Patient row presentation SHALL reside in a pure mapper, and Patient workflow services MUST depend on narrow patient and explicit protocol-coordination ports rather than requiring `DemoStore`.

#### Scenario: Patient workflow creates and reads patients

- **WHEN** a patient workflow creates, lists, or reads a local Patient
- **THEN** patient-record persistence is performed by the patient repository without SQL in `DemoStore`
- **AND** the repository invokes the Patient mapper so the API projection and protocol filtering remain compatible

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

Healthcare Lab SHALL provide an order repository that owns generic local order SQL, protocol-filtered reads, identifier finalization, and send-result updates through the shared SQLite connection factory and application write lock. Order row presentation SHALL reside in a pure mapper, and Order workflow services MUST depend on narrow order and explicit protocol-coordination ports rather than requiring `DemoStore`.

#### Scenario: Generic order is created

- **WHEN** a workflow creates a local Order
- **THEN** the order repository inserts and finalizes the record in one transaction
- **AND** local and placer order identifiers retain their row-ID-derived format and collision safety

#### Scenario: Order send result is recorded

- **WHEN** a send attempt records an ACK or transport error for an Order
- **THEN** the order repository owns the update SQL and invokes the Order mapper for the returned projection
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

Healthcare Lab SHALL separate dcm4chee patient-sync, MWL, and result persistence into dedicated repositories using the shared SQLite connection factory and application write lock. Each repository SHALL own the SQL for its ledger, SHALL invoke pure DICOM mappers for row presentation, and SHALL NOT depend on `DemoStore`.

#### Scenario: Patient sync is persisted

- **WHEN** a Patient sync mapping or attempt is created, read, retried, or completed
- **THEN** the patient-sync repository performs the persistence operation and invokes the Patient-sync mapper
- **AND** existing status, ACK, error, retry, timestamp, and projection behavior is preserved

#### Scenario: MWL state is persisted

- **WHEN** an MWL mapping, create/readback attempt, or verification result is recorded or queried
- **THEN** the MWL repository performs the persistence operation and invokes the MWL mapper
- **AND** stable identifiers, retry behavior, and verification projections remain compatible

#### Scenario: Result state is persisted

- **WHEN** a DICOM result, reconciliation diagnostic, duplicate candidate, refresh run, or refresh snapshot is recorded or queried
- **THEN** the result repository performs the persistence operation and invokes the Result mapper
- **AND** reconciliation precedence, refresh visibility, generation ordering, and duplicate behavior remain compatible

### Requirement: dcm4chee repository boundaries exclude protocol and workflow behavior

DICOM payload construction, response parsing, UID and identifier rules, retry/status policy, row presentation, and cross-context fixture, evidence, simulated-return, and refresh coordination SHALL reside in framework-independent domain, template, mapper, or explicit service modules rather than dcm4chee repositories.

#### Scenario: Repository implementation is inspected

- **WHEN** architecture checks inspect the dcm4chee repositories
- **THEN** repository modules contain persistence behavior and calls to injected pure collaborators only
- **AND** they do not perform HTTP/MLLP transport, construct ADT/MWL payloads, parse transport response bodies, implement row presentation, or orchestrate patient/order workflows

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

### Requirement: FHIR workflow persistence has a dedicated ledger owner

Healthcare Lab SHALL provide a FHIR ledger repository that owns SQL for local FHIR workflow records and sync attempts through the shared SQLite connection factory and application write lock. FHIR row presentation SHALL reside in a pure mapper, and Patient/Order enrichment SHALL consume narrow FHIR ledger batch-loading capabilities rather than querying FHIR tables independently.

#### Scenario: FHIR workflow state is persisted

- **WHEN** a FHIR workflow record is created, updated, queried, ordered, marked syncing, marked successful or failed, or receives a sync attempt
- **THEN** the FHIR ledger repository performs the FHIR-table persistence and invokes the FHIR mapper
- **AND** identifier, dependency, retry, audit, OperationOutcome, Medplum reference, timestamp, and projection behavior remains compatible

#### Scenario: Patient or order projection includes FHIR state

- **WHEN** patient or order records are enriched with related FHIR workflow state
- **THEN** the enrichment obtains batch data through the FHIR ledger owner and presentation through the FHIR mapper
- **AND** no second module issues independent SQL against the FHIR ledger tables

### Requirement: FHIR ledger boundaries exclude transport, payload rules, and generic order ownership

FHIR validation, deterministic identifier/resource construction, Medplum transport, and cross-ledger order coordination SHALL reside in framework-independent domain/template modules, clients, or explicit services rather than the FHIR ledger repository. The existing order repository SHALL remain the sole SQL owner of generic local order records.

#### Scenario: FHIR-mode order is created

- **WHEN** a FHIR-mode ECG order requires a synced Patient reference, a local order anchor, and a ServiceRequest ledger record
- **THEN** a named coordinator uses narrow FHIR and order capabilities
- **AND** `local_order_records` SQL remains with the order owner while FHIR ledger SQL remains with the FHIR owner
- **AND** synced-Patient requirements, local-order persistence, ServiceRequest content, and sync-failure behavior remain compatible

#### Scenario: Medplum synchronization executes

- **WHEN** a FHIR workflow record is synchronized or previewed through Medplum
- **THEN** HTTP authorization, request construction, transport, response handling, and live-resource reads remain in client/service collaborators
- **AND** the FHIR ledger repository only persists normalized workflow and audit state

### Requirement: GDT workflow persistence has a cohesive repository owner

Healthcare Lab SHALL provide a GDT workflow repository that owns SQL for GDT patient contexts, orders, messages, attachments, and workflow events through the shared SQLite connection factory and application write lock. GDT validation, outbound construction, persistence preparation, and row presentation SHALL reside in pure domain, template, or mapper owners, while transactionally coupled context, order, message, attachment, matching, and event writes remain atomic.

#### Scenario: GDT order workflow is persisted

- **WHEN** a GDT order is created, exported, listed, or displayed in the workbench
- **THEN** the GDT workflow repository performs the GDT-table persistence and invokes the owning pure collaborators
- **AND** patient snapshots, local identifiers, status, messages, events, timestamps, and projections remain compatible

#### Scenario: GDT result is matched and persisted

- **WHEN** a normalized GDT result is imported with an exact match, no match, or ambiguous available context
- **THEN** the GDT workflow repository preserves the existing matching precedence and unmatched-result behavior
- **AND** canonical messages, attachments, order updates, and lifecycle events commit together or roll back together

### Requirement: GDT repository boundaries exclude raw protocol and bridge runtime behavior

GDT raw parsing, rendering, character encoding, `6302` construction, `6310` interpretation, persistence preparation, row presentation, bridge filesystem operations, file disposition, and watcher lifecycle SHALL reside in domain, template, mapper, service, or runtime modules rather than the GDT workflow repository. GDT bridge directory readiness validation MAY remain in its approved health/infrastructure boundary.

#### Scenario: GDT message enters persistence

- **WHEN** an outbound order or inbound result requires persistence
- **THEN** the repository receives validated normalized values or output from injected pure collaborators
- **AND** deterministic GDT text, supported fields, validation errors, encoding behavior, attachment interpretation, and returned projections remain compatible

#### Scenario: Bridge file is processed

- **WHEN** the GDT bridge discovers, claims, imports, archives, deletes, or rejects a file
- **THEN** filesystem and watcher behavior remains in the GDT service/runtime layer
- **AND** the repository is used only for resulting normalized workflow persistence

### Requirement: FHIR and GDT services use narrow capabilities

FHIR, GDT, patient, and order workflow services SHALL receive only their declared ledger, core-record, transport, runtime, and coordination capabilities instead of the general `DemoStore` facade or an arbitrarily forwarding wrapper. Cross-ledger work SHALL use explicitly named coordinators assembled in the application composition root.

#### Scenario: Application composition is inspected

- **WHEN** the composition root constructs FHIR, GDT, patient, and order workflows
- **THEN** each workflow receives only explicit cohesive capabilities
- **AND** repositories do not import `DemoStore`, API modules, or unrelated concrete repositories

### Requirement: FHIR and GDT extraction preserves compatibility and autonomous safety

Healthcare Lab SHALL retain only mechanical `DemoStore` delegates needed by existing callers and SHALL verify the extraction using disposable databases and external-service doubles. Unattended implementation MUST stop before schema or stored-data changes, real database or live-service access, public behavior changes, architecture-baseline expansion, new dependencies, unsafe dirty-worktree overlap, or unrelated scope expansion.

#### Scenario: Existing caller uses a compatibility method

- **WHEN** an existing caller invokes a retained FHIR or GDT method through `DemoStore`
- **THEN** the facade delegates to the owning repository, pure collaborator, or named coordinator
- **AND** it contains no replacement SQL, payload, parsing, transport, filesystem, or workflow implementation

#### Scenario: Autonomous implementation encounters routine friction

- **WHEN** implementation encounters a directly caused test failure, import cycle, typing issue, fixture update, composition mismatch, or internal naming decision
- **THEN** it resolves the issue within the approved scope and reruns the nearest focused verification
- **AND** it does not weaken tests, regenerate baseline exceptions, use live resources, or broaden the feature contract

#### Scenario: Autonomous implementation reaches a protected boundary

- **WHEN** completion is proven to require a prohibited schema/data mutation, real database or live-service access, public contract change, baseline exception, new dependency, unrelated extraction, or unsafe overlapping user change
- **THEN** implementation stops before performing that action and reports the evidence and smallest required user decision
- **AND** it does not bypass the boundary by changing tests, allowlists, proposal requirements, or compatibility semantics

#### Scenario: Extraction verification runs

- **WHEN** focused and full automated verification execute
- **THEN** only disposable SQLite databases and external-service doubles are used
- **AND** FHIR state/order semantics and GDT matching/events/attachments remain compatible
- **AND** extracted architecture-baseline entries are removed without adding or refreshing replacement exceptions

### Requirement: Reusable boundary presentation has mapper ownership

Healthcare Lab SHALL place reusable persistence-row and upstream-shape presentation in framework- and persistence-independent bounded-context mapper modules. Mapper modules MUST NOT execute SQL, manage transactions, depend on Flask, or import repositories, services, clients, runtime modules, or application composition.

#### Scenario: Repository returns an existing projection

- **WHEN** a repository reads Patient, Order, FHIR, GDT, OIE, Lab, or dcm4chee persistence rows
- **THEN** it invokes the owning mapper to produce the established projection
- **AND** the mapper can be tested without SQLite, Flask, or an external service

#### Scenario: Architecture dependencies are inspected

- **WHEN** architecture tests inspect mapper and repository imports
- **THEN** mappers depend only on allowed mapper and domain modules
- **AND** repositories may invoke mappers without owning presentation implementation

### Requirement: Pure responsibilities have one implementation owner

Validation and normalization SHALL reside in domain modules, outbound HL7, FHIR, GDT, and DICOM payload construction SHALL reside in template modules, and reusable row or boundary presentation SHALL reside in mapper modules. A compatibility module MAY delegate or re-export an implementation temporarily, but MUST document the implementation owner and retained callers and MUST NOT duplicate the implementation.

#### Scenario: Pure rule or payload implementation is inspected

- **WHEN** architecture checks inspect repositories, templates, domains, mappers, and compatibility modules
- **THEN** each validation rule, protocol builder, and reusable projector has one implementation owner
- **AND** repositories contain only persistence behavior and calls to pure collaborators required by their transaction

#### Scenario: Existing compatibility caller remains

- **WHEN** an existing caller imports a retained validation, builder, or projector through `DemoStore` or another enumerated compatibility module
- **THEN** the compatibility path delegates or re-exports the owning implementation without changing behavior
- **AND** its owner and retained caller are documented for later removal

### Requirement: Typed boundaries remain behavior-compatible

Healthcare Lab SHALL add typed boundary models only where collaborator shapes are reused or ambiguous, and those types MUST preserve the existing runtime dictionary, persisted JSON, generated payload, and public API representations.

#### Scenario: Typed collaborator seam is introduced

- **WHEN** a validation, template, mapper, or repository boundary receives a new `TypedDict`, dataclass, or Protocol annotation
- **THEN** existing callers receive the same runtime values and JSON-compatible shapes
- **AND** no new serialization framework or public migration is required

### Requirement: Behavior-preserving refactors support bounded autonomous execution

Unattended or YOLO-mode implementation MAY resolve routine, directly caused internal failures within the approved change scope, but MUST stop before schema or stored-data mutation, real database or live-service access, public contract change, architecture-baseline or allowlist expansion, dependency installation, destructive operations, unsafe dirty-worktree overlap, or unrelated scope expansion. Verification and closure review remain mandatory.

#### Scenario: Autonomous implementation encounters routine friction

- **WHEN** implementation encounters a directly caused test failure, import cycle, typing issue, fixture update, composition mismatch, or internal naming decision
- **THEN** it resolves the issue within the approved design and reruns the nearest focused verification
- **AND** it preserves the approved contract and stop conditions

#### Scenario: Autonomous implementation reaches a protected boundary

- **WHEN** completion appears to require a prohibited mutation, live resource, public behavior change, baseline exception, dependency, destructive action, unrelated refactor, or unsafe overlap
- **THEN** implementation stops before performing the action and reports the evidence and smallest required user decision
- **AND** it does not bypass the boundary by weakening tests, changing expected compatibility behavior, refreshing fingerprints, or broadening allowlists

#### Scenario: Autonomous implementation reaches a quality gate

- **WHEN** the in-scope implementation appears complete
- **THEN** focused and full verification and an independent closure review still run
- **AND** YOLO mode does not convert skipped or failed evidence into approval

### Requirement: Workflow services have focused use-case ownership

Healthcare Lab workflow services SHALL each own one cohesive application use case. Lab coordination SHALL distinguish dashboard, health, operations, smoke, and resource/status responsibilities; FHIR coordination SHALL distinguish sync, inventory/query, preview, DiagnosticReport, and retry/status responsibilities; Order/dcm4chee coordination SHALL distinguish patient, MWL, verification, result-refresh, and evidence/simulated-return responsibilities. Patient and GDT coordination MUST be split where separate responsibilities have independent callers or collaborator sets and MUST NOT be split into behavior-free forwarding wrappers.

#### Scenario: Service responsibilities are inspected

- **WHEN** an engineer inspects a workflow service and its focused tests
- **THEN** the service has one named use-case responsibility and coordinates only collaborators needed for that responsibility
- **AND** it does not combine unrelated workflow decisions or exist only to forward an unchanged broad argument set

#### Scenario: Patient or GDT workflow is reviewed

- **WHEN** the caller and collaborator inventory shows independently meaningful Patient or GDT use cases
- **THEN** those use cases have separate service owners with preserved ordering and behavior
- **AND** cohesive transaction or runtime responsibilities are not fragmented solely to reduce file size

### Requirement: Workflow service ports are narrow and typed

Each workflow service SHALL receive explicit consumer-owned Protocols or typed callables containing only the operations it consumes. Service ports MUST use concrete parameters and return types and MUST NOT use a general `DemoStore`, an unrelated concrete repository, arbitrary forwarding, generic variadic arguments, or bare `Any` returns.

#### Scenario: Service signatures are inspected

- **WHEN** architecture and focused service tests inspect a workflow service and its collaborators
- **THEN** every collaborator exposes only a cohesive consumed capability with concrete signatures
- **AND** no service relies on `*args`, `**kwargs`, dynamic `__getattr__`, a general store facade, or an unrelated concrete implementation

#### Scenario: Cross-context work is required

- **WHEN** one use case must coordinate records or transports from multiple bounded contexts
- **THEN** application composition provides an explicitly named coordinator or narrow capabilities
- **AND** the service does not import another context's API or concrete repository

### Requirement: Service decomposition preserves layer direction

Decomposed services SHALL remain independent of Flask request or response objects, SQL and transaction implementation, concrete stores and repositories, runtime listener or watcher implementation, outbound protocol construction, and reusable row presentation. Those responsibilities MUST remain with API, repository, runtime, template, domain, mapper, client, or composition owners according to the published architecture.

#### Scenario: Decomposed modules are scanned

- **WHEN** architecture tests inspect imports and classified implementation in new or changed service modules
- **THEN** the modules contain workflow coordination only and depend inward through allowed typed capabilities
- **AND** no Flask handling, SQL, concrete runtime lifecycle, payload-builder, or reusable projector implementation has moved into services

### Requirement: Composition remains compact and compatible

Application assembly SHALL explicitly construct and register decomposed services without implementing workflow decisions. Existing routes, extension keys, Blueprint inputs, callback seams, runtime startup and shutdown order, public responses, errors, persistence semantics, and external integration behavior MUST remain compatible.

#### Scenario: Application composition is updated

- **WHEN** decomposed services replace an oversized workflow in `backend/app_factory.py`
- **THEN** the composition root performs only explicit construction, dependency assembly, registration, and configured startup
- **AND** existing API and runtime characterization passes without consumer migration

#### Scenario: ZAC-46 integration baseline is present

- **WHEN** ZAC-62 product implementation begins or updates application composition
- **THEN** ZAC-46 has been merged and the ZAC-62 branch has been updated from that mainline
- **AND** the persisted OIE management client and settings composition introduced by ZAC-46 remains registered and covered by characterization

### Requirement: Service decomposition is verified incrementally and safely

Healthcare Lab SHALL characterize each affected workflow before movement and verify each bounded-context extraction with focused service, composition, API/runtime, architecture, and regression tests. Verification MUST use disposable databases and external-service doubles; architecture legacy baselines MAY shrink but MUST NOT grow, and tests or allowlists MUST NOT be weakened to accommodate the refactor.

#### Scenario: A bounded-context service is decomposed

- **WHEN** implementation moves Lab, FHIR, Order/dcm4chee, Patient, or GDT coordination
- **THEN** focused tests preserve collaborator calls, ordering, partial-failure behavior, errors, callbacks, and returned projections
- **AND** integration and architecture verification confirms unchanged public, persistence, startup, and runtime behavior

#### Scenario: Parallel or out-of-scope work is encountered

- **WHEN** implementation would require changing ZAC-46 OIE client/settings responsibilities, ZAC-47 channel domain/templates, frontend modularization, broad test-file organization, facade removal, schema/data, public contracts, live services, dependencies, or architecture exceptions
- **THEN** implementation stops before that action and reports the smallest required scope or integration decision
