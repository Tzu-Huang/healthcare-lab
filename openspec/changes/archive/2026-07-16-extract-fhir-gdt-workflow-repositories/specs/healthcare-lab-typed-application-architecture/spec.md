## ADDED Requirements

### Requirement: FHIR workflow persistence has a dedicated ledger owner

Healthcare Lab SHALL provide a FHIR ledger repository that owns SQL and row projections for local FHIR workflow records and sync attempts through the shared SQLite connection factory and application write lock. Patient/order enrichment SHALL consume narrow FHIR ledger batch-loading capabilities rather than querying FHIR tables independently.

#### Scenario: FHIR workflow state is persisted

- **WHEN** a FHIR workflow record is created, updated, queried, ordered, marked syncing, marked successful or failed, or receives a sync attempt
- **THEN** the FHIR ledger repository performs the FHIR-table persistence and projection
- **AND** identifier, dependency, retry, audit, OperationOutcome, Medplum reference, and timestamp behavior remains compatible

#### Scenario: Patient or order projection includes FHIR state

- **WHEN** patient or order records are enriched with related FHIR workflow state
- **THEN** the enrichment obtains batch data and projections from the FHIR ledger owner
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

Healthcare Lab SHALL provide a GDT workflow repository that owns SQL and row projections for GDT patient contexts, orders, messages, attachments, and workflow events through the shared SQLite connection factory and application write lock. Transactionally coupled context, order, message, attachment, matching, and event writes SHALL remain atomic.

#### Scenario: GDT order workflow is persisted

- **WHEN** a GDT order is created, exported, listed, or displayed in the workbench
- **THEN** the GDT workflow repository performs the GDT-table persistence and projection
- **AND** patient snapshots, local identifiers, status, messages, events, and timestamps remain compatible

#### Scenario: GDT result is matched and persisted

- **WHEN** a normalized GDT result is imported with an exact match, no match, or ambiguous available context
- **THEN** the GDT workflow repository preserves the existing matching precedence and unmatched-result behavior
- **AND** canonical messages, attachments, order updates, and lifecycle events commit together or roll back together

### Requirement: GDT repository boundaries exclude raw protocol and bridge runtime behavior

GDT raw parsing, rendering, character encoding, 6302 construction, 6310 interpretation, bridge filesystem operations, file disposition, and watcher lifecycle SHALL reside in adapters/templates, services, or runtime modules rather than the GDT workflow repository.

#### Scenario: GDT message enters persistence

- **WHEN** an outbound order or inbound result requires persistence
- **THEN** the repository receives validated normalized values or output from an injected pure collaborator
- **AND** deterministic GDT text, supported fields, validation errors, encoding behavior, and attachment interpretation remain compatible

#### Scenario: Bridge file is processed

- **WHEN** the GDT bridge discovers, claims, imports, archives, deletes, or rejects a file
- **THEN** filesystem and watcher behavior remains in the GDT service/runtime layer
- **AND** the repository is used only for the resulting normalized workflow persistence

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
