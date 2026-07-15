## ADDED Requirements

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
