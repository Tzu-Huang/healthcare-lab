## MODIFIED Requirements

### Requirement: Readiness is bounded and secret-safe
Healthcare Lab SHALL expose overall and per-section readiness using only `ready`, `needs-setup`, `degraded`, `disabled`, and `restart-required`, derived from persisted configuration and bounded diagnostics rather than field presence alone, SHALL preserve required integration verification semantics across application restart and compatible container recreation, and responses MUST contain no secrets or PHI.

#### Scenario: Configured integration is healthy
- **WHEN** required persisted configuration is valid and its bounded checks succeed for the current configuration revision
- **THEN** the readiness provider returns `ready` with bounded explanatory metadata

#### Scenario: Required Medplum verification failed
- **WHEN** the persisted Medplum configuration is valid but its matching latest bounded verification failed
- **THEN** the readiness provider returns `degraded`
- **AND** overall guided setup does not report complete

#### Scenario: Required Medplum verification is missing or stale
- **WHEN** the persisted Medplum configuration has no bounded verification for its current revision
- **THEN** the readiness provider returns `needs-setup`
- **AND** directs the operator to run the explicit bounded check

#### Scenario: Saved intent is not effective
- **WHEN** valid persisted configuration requires an application restart or container recreation before becoming effective
- **THEN** the provider returns `restart-required` and identifies the required activation class without exposing saved values

#### Scenario: Readiness response is inspected for sensitive data
- **WHEN** readiness is requested after secrets or patient data exist in local storage
- **THEN** neither secret values nor PHI appear in the response, summaries, errors, diagnostic evidence, configuration revisions, or persisted verification state
