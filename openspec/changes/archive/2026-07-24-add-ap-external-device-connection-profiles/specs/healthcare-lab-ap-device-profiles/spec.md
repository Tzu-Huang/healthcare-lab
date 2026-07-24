## ADDED Requirements

### Requirement: Operators manage multiple AP and external-device profiles
The system SHALL persist multiple named device profiles containing enabled state, environment, default selection, supported protocol sections, and allowlisted descriptive metadata.

#### Scenario: Create profiles for one environment
- **WHEN** an operator creates multiple uniquely named profiles in the same environment
- **THEN** the system persists each profile independently and returns stable identifiers

#### Scenario: Duplicate profile name
- **WHEN** an operator submits a profile name that conflicts after normalization
- **THEN** the system rejects the mutation with a stable field-level duplicate-name error

### Requirement: Each environment has at most one enabled default AP
The system MUST enforce default selection atomically and SHALL resolve only an enabled default profile as effective for an environment.

#### Scenario: Select a new default
- **WHEN** an operator selects an enabled profile as the default for an environment
- **THEN** the system atomically removes the previous default selection and resolves the new profile

#### Scenario: Disabled default cannot resolve
- **WHEN** the selected default is disabled
- **THEN** the environment has no effective AP and readiness reports `needs-setup`

### Requirement: Enabled protocol sections are complete and valid
The system SHALL validate HL7/MLLP host, port, application and facility identities; GDT sender/receiver identity and Bridge association; and DICOM AE title, endpoint, MWL identity, and result-delivery role whenever the corresponding section is enabled.

#### Scenario: Incomplete enabled section
- **WHEN** an enabled protocol section omits a required value
- **THEN** the system rejects the complete mutation with stable field-level errors and preserves the prior profile

#### Scenario: Disabled test section
- **WHEN** a protocol section is disabled and contains incomplete non-sensitive test metadata
- **THEN** the system may preserve it but excludes it from effective projections and readiness requirements

### Requirement: Effective AP configuration is resolved once per operation
Application services SHALL resolve an immutable device snapshot for an explicit environment and expose narrow HL7, GDT, and DICOM projections to consumers.

#### Scenario: Profile changes during an operation
- **WHEN** an operator saves a profile after a workflow operation has resolved its device snapshot
- **THEN** the in-flight operation retains its snapshot and subsequent operations receive the new effective values

### Requirement: Device connectivity diagnostics are bounded and protocol-safe
The system SHALL run independent timeout-bounded connectivity checks and SHALL distinguish transport reachability from protocol success.

#### Scenario: One protocol times out
- **WHEN** one enabled protocol check times out while other checks complete
- **THEN** the diagnostic response preserves all partial results using allowlisted states and codes

#### Scenario: TCP endpoint accepts a connection
- **WHEN** a TCP check connects without completing a protocol exchange
- **THEN** the system reports `transport-reachable` and does not claim HL7 or DICOM success

### Requirement: Last observed interaction is metadata-only
The system MUST restrict device interaction observations to profile identity, protocol, direction, timestamp, outcome code, and bounded non-clinical correlation metadata.

#### Scenario: Safe interaction projection
- **WHEN** an interaction is observed for a configured device
- **THEN** Settings may display its protocol, direction, timestamp, and outcome without raw payload or clinical identifiers

#### Scenario: Sensitive observation input
- **WHEN** a caller attempts to record raw HL7, GDT, DICOM, Patient, or Order content
- **THEN** the system rejects or discards that content and does not expose it through APIs, audits, logs, or diagnostics
