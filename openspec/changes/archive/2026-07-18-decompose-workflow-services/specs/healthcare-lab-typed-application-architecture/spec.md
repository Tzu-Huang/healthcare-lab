## ADDED Requirements

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
