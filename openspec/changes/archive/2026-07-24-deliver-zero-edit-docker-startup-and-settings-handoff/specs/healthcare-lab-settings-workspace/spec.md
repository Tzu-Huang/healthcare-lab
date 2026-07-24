## ADDED Requirements

### Requirement: Dashboard hands incomplete setup to authoritative Settings readiness

Healthcare Lab SHALL evaluate the existing secret-safe Settings readiness projection when the Dashboard opens and SHALL present an accessible setup notice when any required section is incomplete, without blocking Dashboard use or maintaining a separate wizard cursor.

#### Scenario: Fresh instance requires application setup

- **WHEN** the Dashboard opens and readiness reports one or more required sections as incomplete
- **THEN** the Dashboard visibly explains that application setup remains
- **AND** provides an action derived from `nextAction` that opens Settings at the owning section

#### Scenario: Required setup is complete

- **WHEN** the Dashboard opens and readiness reports overall setup complete
- **THEN** no incomplete-setup notice is shown
- **AND** optional disabled integrations do not cause the notice to appear

#### Scenario: Readiness is temporarily unavailable

- **WHEN** the Dashboard cannot obtain readiness
- **THEN** service-health content remains usable
- **AND** any bounded recovery message exposes no secrets, PHI, raw upstream payload, or submitted setting value

#### Scenario: Operator follows the setup action

- **WHEN** the operator activates the Dashboard setup action
- **THEN** the application navigates through its registered view activation contract to Settings
- **AND** the guided flow derives its next step from current readiness rather than browser storage or a stale Dashboard snapshot
