## ADDED Requirements

### Requirement: Settings presents layered runtime diagnostics

The Settings workspace SHALL present Management API, HLAB listener, managed Channel deployment, port-contract, and destination delivery checks separately with bounded state and recovery guidance.

#### Scenario: Operator diagnoses failed result delivery
- **WHEN** runtime diagnostics identify one or more failures
- **THEN** Settings labels each affected layer and displays its safe actionable guidance
- **AND** distinguishes unavailable queue statistics from a verified zero queue

#### Scenario: Port configuration requires coordinated work
- **WHEN** a diagnostic or saved change affects a Channel endpoint, process listener, or host-published port
- **THEN** Settings identifies whether Apply/Redeploy, listener Retry/restart, or container recreation is required
- **AND** does not perform those coordinated operations implicitly
