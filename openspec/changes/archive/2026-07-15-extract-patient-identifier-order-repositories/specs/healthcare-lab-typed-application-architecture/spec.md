## ADDED Requirements

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
