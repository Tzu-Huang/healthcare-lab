## MODIFIED Requirements

### Requirement: Patient creation allocates a sequential demo MRN

Healthcare Lab SHALL allocate one globally unique, persistent canonical MRN from a shared sequence when Patient creation does not provide one, regardless of Patient mode.

#### Scenario: Patient is created without an MRN

- **WHEN** a valid HL7 v2, FHIR, GDT, or DICOM Patient creation request omits MRN or supplies a blank MRN
- **THEN** Healthcare Lab allocates the next available identifier using the format `MRN-` followed by a minimum of six decimal digits
- **AND** the first identifier in a newly created demo database is `MRN-000001`
- **AND** the allocated MRN is stored before any protocol payload or downstream synchronization resource is created

#### Scenario: Server-specific inventory contains sequence gaps

- **WHEN** Patients in different modes consume values from the shared MRN sequence
- **THEN** each server-specific Patient inventory displays the canonical MRNs assigned to its Patients
- **AND** gaps caused by Patients assigned to other modes are accepted
- **AND** Healthcare Lab does not allocate a separate sequence per server

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

Healthcare Lab SHALL retain explicit canonical MRN entry for deterministic integration testing and SHALL reject invalid or duplicate MRNs before Patient side effects occur.

#### Scenario: Patient is created with an unused explicit MRN

- **WHEN** a valid Patient creation request supplies a non-blank value that becomes `MRN-` followed by at least six decimal digits after trimming and uppercasing
- **AND** the normalized value is not assigned to an existing local Patient
- **THEN** Healthcare Lab stores the normalized supplied value
- **AND** it creates the Patient without consuming or replacing that value with an automatic MRN

#### Scenario: Patient supplies a noncanonical explicit MRN

- **WHEN** a new Patient creation request supplies an explicit MRN that does not match `MRN-` followed by at least six decimal digits after normalization
- **THEN** Healthcare Lab rejects the request with a canonical-format validation error
- **AND** it does not create a Patient record, protocol payload, or downstream synchronization attempt

#### Scenario: Patient is created with a duplicate explicit MRN

- **WHEN** a Patient creation request supplies an MRN whose normalized value matches an existing local Patient MRN
- **THEN** Healthcare Lab rejects the request with a validation error identifying the duplicate MRN
- **AND** it does not create a Patient record, protocol payload, or downstream synchronization attempt

### Requirement: Generated MRNs propagate through Patient and Order workflows

Healthcare Lab SHALL use the canonical Patient MRN in each protocol's patient-identity field and SHALL keep protocol-specific technical identifiers distinct from MRN.

#### Scenario: HL7 v2 Patient or Order payload is created

- **WHEN** Healthcare Lab creates an HL7 v2 Patient or Order payload
- **THEN** its `PID-3` carries the canonical Patient MRN
- **AND** the assigning authority remains distinct from the MRN value

#### Scenario: FHIR Patient resource is created or displayed

- **WHEN** Healthcare Lab creates or displays a FHIR Patient
- **THEN** the canonical MRN is selected from the MRN identifier system rather than from identifier list position
- **AND** the deterministic FHIR workflow identifier and Medplum resource id or reference remain separately labelled identities

#### Scenario: GDT Patient or new GDT Order payload is created

- **WHEN** Healthcare Lab creates a GDT Patient payload or emits a new GDT Order payload
- **THEN** GDT field `3000` carries the canonical Patient MRN
- **AND** a generated `GDT-PAT-*` workflow identifier is not displayed or interpreted as MRN

#### Scenario: DICOM Patient or MWL payload is created

- **WHEN** Healthcare Lab creates a DICOM Patient or dcm4chee MWL payload
- **THEN** DICOM Patient ID carries the canonical Patient MRN
- **AND** Patient ID issuer, accession numbers, and DICOM UIDs remain separately labelled identities

#### Scenario: Order is created for a Patient

- **WHEN** an Order is created for a Patient whose MRN was automatically or explicitly assigned
- **THEN** the Order snapshots that same canonical MRN
- **AND** Healthcare Lab does not allocate a new MRN for the Order

## ADDED Requirements

### Requirement: Canonical MRN uniqueness is enforced by persistence

Healthcare Lab SHALL enforce normalized MRN uniqueness in SQLite as well as in Patient creation validation.

#### Scenario: Concurrent or alternate write attempts reuse an MRN

- **WHEN** more than one write path attempts to persist the same normalized MRN for different Patients
- **THEN** the database accepts at most one Patient row with that MRN
- **AND** Healthcare Lab reports the rejected write as a duplicate MRN validation failure

#### Scenario: Existing database contains normalized duplicate MRNs

- **WHEN** schema migration detects existing MRNs that collide after canonical normalization
- **THEN** migration stops before installing or claiming the uniqueness constraint
- **AND** diagnostics identify the conflicting rows and values for explicit operator resolution
- **AND** Healthcare Lab does not silently merge Patients or assign replacement MRNs

#### Scenario: Existing database contains a unique nonconforming MRN

- **WHEN** schema migration encounters a unique stored MRN that cannot be converted to canonical format without changing external identity
- **THEN** Healthcare Lab preserves that legacy Patient MRN
- **AND** newly created Patients remain subject to canonical format validation

### Requirement: MRN labels identify only canonical Patient MRNs

Healthcare Lab SHALL use the label `MRN` only for the Patient's canonical MRN in Patient, Order, OIE, Medplum, GDT, and dcm4chee views.

#### Scenario: Console displays multiple patient-related identifiers

- **WHEN** a server console displays the canonical MRN and one or more protocol-specific identifiers
- **THEN** the canonical value is displayed under `MRN`
- **AND** each other identifier is displayed under a protocol-accurate label
- **AND** the MRN display does not fall back to a Medplum reference, GDT workflow identifier, DICOM issuer, or DICOM UID

