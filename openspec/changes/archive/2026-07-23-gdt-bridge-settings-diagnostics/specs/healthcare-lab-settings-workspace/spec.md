## ADDED Requirements

### Requirement: Settings aggregates GDT-owned readiness and diagnostics

Healthcare Lab SHALL register the GDT Bridge module's readiness and bounded diagnostic provider with the Settings workspace without moving GDT-specific logic into the shell.

#### Scenario: Run all checks includes enabled GDT
- **WHEN** an operator runs all checks while GDT Bridge is enabled
- **THEN** the shell delegates to the GDT-owned diagnostic provider
- **AND** renders its bounded path, permission, probe, and watcher outcomes with recovery guidance

#### Scenario: Saved GDT intent is not yet effective
- **WHEN** the GDT profile is valid but the watcher requires a restart before using it
- **THEN** GDT readiness reports `restart-required`
- **AND** the Settings workspace preserves that state and its bounded activation guidance
