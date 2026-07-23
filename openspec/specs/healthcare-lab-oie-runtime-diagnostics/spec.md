# healthcare-lab-oie-runtime-diagnostics Specification

## Purpose
TBD - created by archiving change expose-bootstrap-status-and-verify-restart-convergence. Update Purpose after archive.
## Requirements
### Requirement: Runtime diagnostics expose bootstrap independently

Healthcare Lab SHALL include bootstrap as an independent Runtime Diagnostics layer sourced from secret-safe bootstrap status, without conflating it with HLAB listener auto-start, managed Channel deployment, or destination delivery health.

#### Scenario: Bootstrap completed successfully

- **WHEN** the latest enabled bootstrap run completed with successful or no-op convergence for both canonical logical types
- **THEN** the bootstrap diagnostic reports healthy with its bounded observation time and outcome evidence

#### Scenario: Bootstrap is running

- **WHEN** bootstrap is waiting or reconciling
- **THEN** the bootstrap diagnostic reports running without claiming that Channel deployment or HLAB listener delivery is healthy

#### Scenario: Bootstrap timed out or was blocked

- **WHEN** the latest run timed out, partially failed, was interrupted, or encountered an ownership blocker
- **THEN** the bootstrap diagnostic reports the distinct bounded category and actionable allowlisted guidance
- **AND** the other diagnostic layers continue to report their own results

#### Scenario: Bootstrap status is unavailable

- **WHEN** bootstrap operational evidence cannot be read
- **THEN** the bootstrap diagnostic reports unavailable without triggering bootstrap or OIE inspection for that layer
