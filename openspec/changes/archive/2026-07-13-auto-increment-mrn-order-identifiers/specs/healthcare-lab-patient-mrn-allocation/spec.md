## ADDED Requirements

### Requirement: Patient creation allocates a sequential demo MRN

Healthcare Lab SHALL allocate a persistent local MRN when Patient creation does not provide one.

#### Scenario: Patient is created without an MRN

- **WHEN** a valid Patient creation request omits MRN or supplies a blank MRN
- **THEN** Healthcare Lab allocates the next available identifier using the format `MRN-` followed by a minimum of six decimal digits
- **AND** the first identifier in a newly created demo database is `MRN-000001`
- **AND** the allocated MRN is stored before any protocol payload or downstream synchronization resource is created

#### Scenario: Automatic allocation survives restart and deletion

- **WHEN** one or more automatic MRNs have been allocated
- **AND** the application restarts or an earlier Patient is deleted
- **THEN** the next automatic MRN is greater than every value previously issued by the local sequence
- **AND** Healthcare Lab does not reuse a deleted Patient's MRN

#### Scenario: Automatic allocation encounters a manually used candidate

- **WHEN** the next sequential MRN is already assigned to an existing Patient
- **THEN** Healthcare Lab skips that value
- **AND** it allocates the next unused sequential MRN

### Requirement: Patient creation supports explicit unique MRNs

Healthcare Lab SHALL retain explicit MRN entry for integration testing and SHALL reject newly requested duplicate local MRNs.

#### Scenario: Patient is created with an unused explicit MRN

- **WHEN** a valid Patient creation request supplies a non-blank MRN that does not exactly match an existing local Patient MRN
- **THEN** Healthcare Lab preserves the trimmed supplied value
- **AND** it creates the Patient without consuming or replacing that value with an automatic MRN

#### Scenario: Patient is created with a duplicate explicit MRN

- **WHEN** a Patient creation request supplies an MRN that exactly matches an existing local Patient MRN
- **THEN** Healthcare Lab rejects the request with a validation error identifying the duplicate MRN
- **AND** it does not create a Patient record, protocol payload, or downstream synchronization attempt

### Requirement: Generated MRNs propagate through Patient and Order workflows

Healthcare Lab SHALL use an automatically allocated MRN everywhere the equivalent explicitly supplied Patient MRN is used.

#### Scenario: Protocol Patient payload is created from an automatic MRN

- **WHEN** Healthcare Lab creates a Patient with an automatically allocated MRN
- **THEN** its persisted protocol-specific Patient payload contains that MRN in the protocol's Patient identifier field
- **AND** the Patient API and Patient list return the allocated value

#### Scenario: Order is created for a Patient with an automatic MRN

- **WHEN** an Order is created for a Patient whose MRN was automatically allocated
- **THEN** the Order snapshots that same MRN
- **AND** an HL7 v2.5.1 Order emits it in `PID-3`
- **AND** Healthcare Lab does not allocate a new MRN for the Order

### Requirement: Patient preview does not predict automatic MRNs

Healthcare Lab SHALL distinguish an unallocated automatic MRN from a persisted identifier.

#### Scenario: User applies the Patient demo preset

- **WHEN** the demo preset leaves the MRN input blank
- **THEN** the Patient preview displays `Generated on create` for MRN
- **AND** the browser does not predict or reserve the next sequential value

#### Scenario: Automatically numbered Patient is created

- **WHEN** Patient creation succeeds with an automatically allocated MRN
- **THEN** the created Patient summary and persisted payload display the allocated MRN
