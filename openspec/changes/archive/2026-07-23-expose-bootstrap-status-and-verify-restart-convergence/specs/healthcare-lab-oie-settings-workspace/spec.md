## ADDED Requirements

### Requirement: Settings always presents canonical managed templates

Settings SHALL present both approved managed templates from canonical application intent even before an OIE Channel mapping exists or when live inventory cannot be read. The workspace SHALL distinguish missing, created, unchanged, recovered, drifted, external, conflict, and inventory-unavailable states without initiating mutation.

#### Scenario: No managed mappings exist

- **WHEN** Settings loads before either canonical Channel has a persisted OIE identity
- **THEN** it displays both approved template cards with missing state and their expected routes

#### Scenario: Live inventory fails

- **WHEN** OIE managed Channel inspection is unavailable
- **THEN** Settings keeps both approved template cards visible
- **AND** displays a concrete bounded inventory error instead of an empty managed section

#### Scenario: Browser refreshes inventory

- **WHEN** an operator refreshes Settings or managed inventory
- **THEN** the application performs no create, update, deploy, undeploy, delete, recover, or bootstrap Retry mutation

### Requirement: Settings exposes bootstrap state and explicit Retry

Settings SHALL display bootstrap mode, runtime state, timing, attempt evidence, overall outcome, per-logical-type results, and bounded recovery guidance separately from HLAB listener state. It SHALL enable explicit Retry only when the backend reports Retry as eligible.

#### Scenario: Bootstrap is in progress

- **WHEN** Settings observes a running bootstrap
- **THEN** it displays waiting or reconciliation progress and disables duplicate Retry

#### Scenario: Bootstrap timed out recoverably

- **WHEN** status reports an allowlisted recoverable timeout or readiness failure
- **THEN** Settings displays the safe recovery guidance and enables Retry

#### Scenario: Bootstrap is blocked by ownership

- **WHEN** a logical type is drifted, external, or conflicted
- **THEN** Settings displays the blocker separately from recoverable readiness failures
- **AND** it does not offer a force-update or automatic drift-remediation action
