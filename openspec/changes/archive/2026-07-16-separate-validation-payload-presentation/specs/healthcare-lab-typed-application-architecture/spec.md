## ADDED Requirements

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

## MODIFIED Requirements

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

### Requirement: OIE result persistence has a dedicated owner

Healthcare Lab SHALL provide OIE repositories that own settings and inbound result persistence, including error records, duplicate message-control detection, and persisted matching references. OIE validation and row presentation SHALL reside in pure domain or mapper owners, and OIE services and runtime listeners SHALL depend on narrow OIE ports.

#### Scenario: Inbound OIE result is persisted

- **WHEN** the OIE listener accepts a valid, duplicate, unmatched, or invalid result message
- **THEN** the OIE result repository preserves the current record, matching, duplicate, error, and response semantics without SQL in `DemoStore`
- **AND** it invokes pure validation or presentation collaborators rather than implementing those responsibilities

#### Scenario: OIE workbench crosses bounded contexts

- **WHEN** the OIE workbench combines patient, order, and OIE result data
- **THEN** a service coordinates the required narrow ports and the OIE repository remains limited to OIE-owned persistence

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
