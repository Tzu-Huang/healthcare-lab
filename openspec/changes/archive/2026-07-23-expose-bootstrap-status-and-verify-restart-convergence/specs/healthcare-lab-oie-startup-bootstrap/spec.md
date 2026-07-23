## ADDED Requirements

### Requirement: Bootstrap run state is durable and secret-safe

Healthcare Lab SHALL persist and expose the latest bootstrap run as bounded operational evidence containing mode, trigger, runtime state, started and completed timestamps, attempts, overall outcome, safe error category, recovery guidance code, and one outcome for each canonical logical type. It MUST NOT persist or expose credentials, session material, complete Channel payloads, HL7 content, PHI, or arbitrary upstream error text.

#### Scenario: Bootstrap is waiting for OIE

- **WHEN** an enabled bootstrap run has started but OIE readiness has not yet succeeded or timed out
- **THEN** status reports the run as running with its start time and bounded attempt evidence
- **AND** both canonical logical types remain represented without fabricating successful outcomes

#### Scenario: Bootstrap completes

- **WHEN** reconciliation reaches a bounded outcome for both canonical logical types
- **THEN** the completed run and both per-logical-type outcomes are stored with a completion timestamp
- **AND** the latest completed evidence remains queryable after application restart

#### Scenario: A prior process ended during bootstrap

- **WHEN** application startup finds a latest run that was not completed by the process that created it
- **THEN** status reports that run as interrupted rather than currently running

#### Scenario: Sensitive upstream failure occurs

- **WHEN** readiness or reconciliation fails with an exception containing sensitive or PHI-bearing content
- **THEN** status and persisted evidence contain only an allowlisted category and guidance code

### Requirement: Bootstrap status reads are side-effect free

Healthcare Lab SHALL expose bootstrap status without performing OIE inspection, readiness checks, lifecycle preview, Channel mutation, or bootstrap Retry.

#### Scenario: Browser repeatedly refreshes Settings

- **WHEN** an operator repeatedly reads Settings, bootstrap status, managed inventory, or Runtime Diagnostics
- **THEN** no bootstrap run or OIE Channel mutation is initiated by those reads

### Requirement: Bootstrap Retry is explicit, guarded, and single-run

Healthcare Lab SHALL provide an explicit asynchronous Retry command that reuses the same bounded create-missing and safe-recovery workflow as startup, SHALL allow at most one bootstrap run in a process, and MUST NOT force changes to drifted, external, or conflicted Channels.

#### Scenario: Recoverable readiness failure is retried

- **WHEN** the latest bootstrap result has an allowlisted recoverable readiness or timeout category and mode is enabled
- **THEN** Retry starts one new run with trigger `retry`
- **AND** it applies the same per-logical-type lifecycle guards as startup

#### Scenario: Retry is requested while a run is active

- **WHEN** startup or Retry bootstrap is already running
- **THEN** the command returns a stable conflict and does not start another worker

#### Scenario: Retry is requested for an ownership blocker

- **WHEN** the latest result is blocked by drift, external ownership, or conflict without a recoverable infrastructure failure
- **THEN** Retry is rejected with bounded recovery guidance
- **AND** no lifecycle mutation occurs

#### Scenario: Bootstrap mode is off

- **WHEN** an operator requests Retry while bootstrap mode is `off`
- **THEN** the command reports that bootstrap is disabled and performs no readiness check or mutation
