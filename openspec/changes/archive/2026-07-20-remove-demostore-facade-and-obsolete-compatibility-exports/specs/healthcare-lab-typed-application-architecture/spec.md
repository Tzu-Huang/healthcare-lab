## ADDED Requirements

### Requirement: Application composition exposes only explicit dependencies

Healthcare Lab SHALL construct the shared database lifecycle, repositories, enrichment loaders, coordinators, and runtime collaborators in a dedicated application-composition owner with explicitly declared typed outputs. The composition result MUST NOT implement business operations, arbitrary forwarding, dynamic attribute lookup, or act as a service locator, and APIs, services, clients, repositories, and runtime components MUST receive only their declared narrow dependencies.

#### Scenario: Application dependencies are assembled

- **WHEN** the Flask application is created for a disposable database
- **THEN** one shared database owner initializes migrations and maintenance and supplies its connection factory and application lock to the named repositories
- **AND** each service, Blueprint, listener, watcher, and coordinator receives only its explicitly consumed collaborators

#### Scenario: Broad replacement container is introduced

- **WHEN** architecture checks inspect application composition and production consumers
- **THEN** they reject business delegates, `__getattr__`, arbitrary forwarding, generic service lookup, or a broad composition object passed into a consumer

### Requirement: DemoStore and its internal compatibility access are removed

Healthcare Lab SHALL NOT contain or import `DemoStore` or `backend.lab_store`, SHALL NOT publish `app.extensions["demo_store"]`, and SHALL NOT replace them with an equivalently broad store, dependency, repository, or service extension. Remaining constants, helpers, repositories, and coordinators MUST be imported from their responsibility-specific owners.

#### Scenario: Production and tests are scanned after cleanup

- **WHEN** verification scans application, backend, and test sources
- **THEN** no `DemoStore`, `backend.lab_store`, or `demo_store` Flask extension reference remains
- **AND** architecture compatibility fingerprints, delegate maps, allowlists, and legacy-baseline entries for the removed facade are absent rather than renamed or refreshed

#### Scenario: Integration test needs application state

- **WHEN** an integration test must prepare or inspect persistence state
- **THEN** it uses public HTTP behavior, a named owner fixture, or explicit focused injection
- **AND** production does not expose a broad container solely for test access

### Requirement: Facade removal preserves supported behavior and data

Removing the internal facade and compatibility exports SHALL preserve HTTP routes, request and response semantics, configuration keys, process startup, SQLite schema and stored rows, migration and maintenance ordering, transaction and lock behavior, protocol payloads, external-integration behavior, and runtime startup/shutdown lifecycle.

#### Scenario: Existing database and application are opened after cleanup

- **WHEN** the application initializes against a disposable database representing supported existing schema state
- **THEN** the same migrations and maintenance run without destructive data changes
- **AND** application creation and focused API/runtime characterization pass without live external services

#### Scenario: Obsolete internal compatibility caller is encountered

- **WHEN** a repository-local test or module still imports `backend.lab_store`, invokes a `DemoStore` delegate, reads the `demo_store` extension, or patches an obsolete compatibility export
- **THEN** the caller migrates to the responsibility owner or explicit injection
- **AND** no shim is introduced unless a separately approved public compatibility contract is identified

## MODIFIED Requirements

### Requirement: Process entrypoint remains thin

`app.py` SHALL contain only the supported process entrypoint wiring, while `backend/app_factory.py` SHALL own Flask application creation, explicit dependency assembly, Blueprint registration, and configured runtime startup. Test-only whole-module aliases and obsolete compatibility exports MUST NOT be retained as part of the process-entrypoint contract.

#### Scenario: Entrypoint contract is tested

- **WHEN** architecture and startup checks inspect and import `app.py`
- **THEN** it exposes the documented application entrypoint required by deployment
- **AND** it contains no route implementations, SQL operations, external protocol implementations, listener or watcher class implementations, workflow orchestration, whole-module aliasing for patch compatibility, or obsolete helper re-exports

### Requirement: Compatibility facades are explicit migration seams

Healthcare Lab SHALL enumerate any remaining compatibility facades and their owning destinations. A retained facade MUST have an identified current consumer and removal boundary, MUST delegate or re-export only the named implementation, and MUST NOT own new SQL, payload, workflow, transport, composition, or generic dependency-access behavior. `DemoStore`, `backend.lab_store`, and the `demo_store` Flask extension MUST NOT appear in that enumeration.

#### Scenario: Existing caller uses a remaining allowed facade

- **WHEN** an identified caller imports a symbol through an enumerated compatibility facade that remains outside the ZAC-65 removal set
- **THEN** the facade delegates or re-exports the implementation from its named owner without changing observable behavior
- **AND** its owner, consumer, and removal boundary are documented

#### Scenario: Removed or new facade is referenced

- **WHEN** code imports `backend.lab_store`, accesses the `demo_store` Flask extension, introduces a generic forwarding facade, or adds a caller to another compatibility module
- **THEN** the architecture contract rejects it and directs the caller to the responsibility-specific owner

### Requirement: Composition remains compact and compatible

Application assembly SHALL explicitly construct and register services and runtime collaborators without implementing workflow decisions or publishing a broad service locator. Existing routes, supported narrow extension keys, Blueprint inputs, runtime callback seams, startup and shutdown order, public responses, errors, persistence semantics, and external integration behavior MUST remain compatible; the internal `demo_store` extension key and test-only patch/import paths are explicitly removed from compatibility scope.

#### Scenario: Application composition is updated

- **WHEN** explicit application dependencies replace `DemoStore` in `backend/app_factory.py`
- **THEN** the composition root performs only construction, dependency assembly, registration, and configured startup
- **AND** API, runtime, persistence, and process-entrypoint characterization passes without a broad replacement container

#### Scenario: Runtime object requires Flask lifecycle lookup

- **WHEN** a listener, watcher, or configured runtime service must be retrieved through Flask lifecycle state
- **THEN** it uses an existing narrow, purpose-named extension key
- **AND** no `demo_store`, `dependencies`, `repositories`, `services`, or equivalent broad extension is introduced

## REMOVED Requirements

### Requirement: Extracted boundaries retain compatibility-only DemoStore seams

**Reason**: All prerequisite bounded-context and test migrations are complete, and ZAC-65 intentionally deletes the internal `DemoStore` facade and `backend.lab_store` module.

**Migration**: Import the responsibility-specific repository, domain, template, mapper, client, service, coordinator, or configuration owner directly. Integration tests use HTTP, named owner fixtures, or explicit focused injection.
