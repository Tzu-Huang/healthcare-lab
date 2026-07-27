## ADDED Requirements

### Requirement: Fresh installation is verified as an operator journey

Healthcare Lab SHALL provide reproducible verification that a supported
disposable environment with no repository-root `.env`, application database,
or prior named volumes can start through the documented wrapper and complete
required browser-based Settings setup without an undocumented manual edit.

#### Scenario: Clean deployment reaches guided setup
- **WHEN** the supported stack starts with safe defaults and fresh persistent storage
- **THEN** the application becomes available and secret-safe readiness identifies the next required Settings action
- **AND** built-in OIE and dcm4chee defaults are represented accurately

#### Scenario: Operator completes required and optional setup
- **WHEN** the operator configures Medplum through Settings and either configures or explicitly disables GDT and AP profiles
- **THEN** bounded checks report outcomes for the owning integration
- **AND** overall setup completes only under the documented readiness rules

#### Scenario: Completed setup survives replacement
- **WHEN** the application restarts and its container is recreated while documented persistent storage is retained
- **THEN** setup completion, persisted non-secret values, and secret configured states remain authoritative

### Requirement: Legacy upgrade preserves one-time migration precedence

Healthcare Lab SHALL verify upgrade from a versioned representative legacy
database plus eligible environment values without deleting persistent volumes,
and SHALL prove that legacy bootstrap occurs only for missing typed profiles.

#### Scenario: Representative legacy installation upgrades
- **WHEN** the current application initializes the canonical legacy fixture with eligible legacy environment values
- **THEN** schema and profile migrations complete atomically
- **AND** secrets remain configured without appearing in output or evidence
- **AND** effective values follow the documented precedence contract

#### Scenario: Migrated setting is changed in Settings
- **WHEN** the operator changes a migrated value through the UI and starts the application again with the old environment value still present
- **THEN** the persisted operator value remains effective
- **AND** environment bootstrap does not overwrite, merge, clear, or reseed the profile

### Requirement: Failure and authority boundaries are verified safely

The release gate SHALL exercise the documented Settings failure matrix and
SHALL require every result to identify a bounded owning layer and recovery
action without exposing credentials, PHI, raw healthcare messages, FHIR
resource bodies, or arbitrary upstream responses.

#### Scenario: Integration failures are exercised
- **WHEN** verification supplies a wrong Medplum secret, unreachable FHIR URL, missing GDT directory, unwritable bridge, unreachable dcm4chee endpoint, invalid AE title, AP or OIE drift, or partial service availability
- **THEN** each failure is classified independently with bounded recovery guidance
- **AND** successful independent checks remain visible

#### Scenario: Sensitive canaries are inspected
- **WHEN** API responses, UI output, wrapper output, logs selected for evidence, and generated evidence are scanned
- **THEN** no configured secret, authorization material, PHI canary, raw message, or FHIR body is present

#### Scenario: Web configuration authority is inspected
- **WHEN** Settings and Deployment & Diagnostics capabilities are exercised
- **THEN** Settings cannot rewrite Compose or invoke arbitrary Docker operations
- **AND** any supported Dashboard container control remains limited to its separately documented trusted-lab contract

### Requirement: Operator handbooks match the released workflow

Healthcare Lab SHALL publish English and Traditional Chinese handbook editions
whose commands, UI labels, configuration ownership, and activation guidance
agree with the verified release behavior.

#### Scenario: First-time operator follows Quick Start
- **WHEN** an operator follows either handbook from a clean supported deployment
- **THEN** the normal path uses one documented Docker start command followed by browser-based guided Settings setup
- **AND** no `.env`, Compose YAML, or undocumented file edit is required

#### Scenario: Operator configures Medplum
- **WHEN** an operator follows the Medplum setup instructions
- **THEN** the handbook explains how to create a ClientApplication and maps the exact client ID and secret fields into Settings without containing real credentials
- **AND** it distinguishes internal FHIR traffic from the browser-facing URL

#### Scenario: Operator distinguishes Settings from deployment overrides
- **WHEN** an operator reviews configuration, GDT paths, activation, secret rotation, backup, restore, upgrade, or recreation guidance
- **THEN** normal Settings fields are separate from Advanced deployment overrides
- **AND** Windows host paths are distinguished from container paths
- **AND** restart and recreation semantics are stated for each setting category

#### Scenario: Published handbook editions are compared
- **WHEN** Markdown and generated Word editions in both languages are prepared for closure
- **THEN** their stable commands, UI labels, configuration facts, and safety guidance agree
- **AND** every screenshot contains only synthetic data and no credentials

### Requirement: Closure evidence is reproducible and defect-aware

The release gate SHALL record the exact tested commit, supported environment,
automated suite results, disposable live matrix outcomes, and any precise
environment-dependent skip, and MUST NOT treat an untracked product defect as a
passing verification result.

#### Scenario: Verification completes
- **WHEN** unit, integration, frontend, Compose contract, migration, and required live checks pass
- **THEN** a dated synthetic evidence record identifies the tested commit and bounded outcomes
- **AND** ZAC-78 can proceed to closure review

#### Scenario: Environment prevents a live check
- **WHEN** a required external condition cannot be obtained without mutating an owned environment
- **THEN** evidence names the exact unmet condition and affected scenarios
- **AND** does not claim those scenarios passed

#### Scenario: Verification discovers a product defect
- **WHEN** implemented behavior reproducibly violates an acceptance scenario
- **THEN** the finding is linked to a separate defect issue with reproduction evidence
- **AND** closure remains blocked when the defect prevents the required operator journey
