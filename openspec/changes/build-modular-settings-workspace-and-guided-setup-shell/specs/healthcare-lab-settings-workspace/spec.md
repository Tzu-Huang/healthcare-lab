## ADDED Requirements

### Requirement: Settings provides a modular integration workspace
Healthcare Lab SHALL present Settings as an accessible workspace with Overview, Medplum, OIE, GDT Bridge, dcm4chee, AP / External Devices, and Deployment & Diagnostics sections, and MUST NOT present or register OpenEMR.

#### Scenario: User navigates Settings by keyboard
- **WHEN** a user opens Settings and navigates its section controls using a keyboard
- **THEN** focus, selection, section labeling, and responsive content remain perceivable and operable

#### Scenario: OpenEMR is absent
- **WHEN** Settings navigation, readiness registrations, setup steps, and diagnostic registrations are enumerated
- **THEN** none contains an OpenEMR entry or placeholder

### Requirement: Integrations own independent Settings modules
Healthcare Lab SHALL define a shared Settings registration contract under which each integration owns its view, API adapter, state, initialization, and styling, and the shell MUST NOT absorb integration-specific form or diagnostic logic.

#### Scenario: A later integration adds a section
- **WHEN** a supported integration implements the Settings registration contract
- **THEN** the shell can expose and activate it without adding its form state or API calls to a monolithic Settings controller

#### Scenario: OIE moves behind the contract
- **WHEN** the OIE Settings section is activated
- **THEN** existing connection, listener, managed-Channel, preview, and diagnostic safeguards remain functional through the OIE-owned module

### Requirement: Readiness is bounded and secret-safe
Healthcare Lab SHALL expose overall and per-section readiness using only `ready`, `needs-setup`, `degraded`, `disabled`, and `restart-required`, derived from persisted configuration and bounded diagnostics rather than field presence alone, and responses MUST contain no secrets or PHI.

#### Scenario: Configured integration is healthy
- **WHEN** required persisted configuration is valid and its bounded checks succeed
- **THEN** the readiness provider returns `ready` with bounded explanatory metadata

#### Scenario: Saved intent is not effective
- **WHEN** valid persisted configuration requires an application restart or container recreation before becoming effective
- **THEN** the provider returns `restart-required` and identifies the required activation class without exposing saved values

#### Scenario: Readiness response is inspected for sensitive data
- **WHEN** readiness is requested after secrets or patient data exist in local storage
- **THEN** neither secret values nor PHI appear in the response, summaries, errors, or diagnostic evidence

### Requirement: Guided setup resumes from authoritative readiness
Healthcare Lab SHALL open a guided setup flow for a fresh instance, select the next actionable section from current readiness, allow users to leave and resume later, and avoid a separate server-side wizard cursor.

#### Scenario: Fresh instance opens Settings
- **WHEN** a fresh instance has one or more required sections in `needs-setup`
- **THEN** Settings visibly opens guided setup and directs the user to the next required action

#### Scenario: User returns after partial setup
- **WHEN** the user leaves Settings after completing some sections and returns later
- **THEN** the flow resumes from newly aggregated readiness rather than a stale step number

### Requirement: Optional integrations do not block completion
Healthcare Lab SHALL allow GDT Bridge, dcm4chee, and AP / External Devices to be disabled, and overall setup SHALL be complete when required sections are ready and each optional section is either ready or disabled.

#### Scenario: Optional integrations remain disabled
- **WHEN** all required sections are ready and GDT Bridge, dcm4chee, and AP / External Devices are disabled
- **THEN** overall setup reports complete

#### Scenario: Required integration needs setup
- **WHEN** any required section reports `needs-setup`, `degraded`, or `restart-required`
- **THEN** overall setup does not report complete and provides a bounded next action

### Requirement: Settings explains safe configuration and activation impact
Healthcare Lab SHALL show safe local defaults and concise explanations, place expert-only fields behind an accessible Advanced disclosure, and label saved changes as effective immediately, application restart required, or container recreation required.

#### Scenario: User reviews an advanced field
- **WHEN** a section exposes an expert-only setting
- **THEN** the setting is hidden in a keyboard-operable Advanced disclosure with a concise explanation and safe local default

#### Scenario: User saves a setting
- **WHEN** a supported setting mutation succeeds
- **THEN** Settings presents exactly which activation class applies without automatically restarting or recreating anything

### Requirement: Run all checks delegates to registered diagnostics
Healthcare Lab SHALL provide a top-level Run all checks action that invokes bounded diagnostics owned by registered integrations, tolerates unavailable providers, and returns partial secret-safe results.

#### Scenario: Registered checks complete with mixed outcomes
- **WHEN** the user runs all checks and providers return healthy, degraded, disabled, or unavailable results
- **THEN** Settings renders each bounded result and recovery guidance without discarding successful results

#### Scenario: Integration has no diagnostic provider yet
- **WHEN** a registered section does not yet supply bounded diagnostics
- **THEN** Run all checks reports that provider as unavailable or disabled without attempting an invented probe
