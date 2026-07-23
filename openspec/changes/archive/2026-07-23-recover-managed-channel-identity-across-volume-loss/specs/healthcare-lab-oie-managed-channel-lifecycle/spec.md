## ADDED Requirements

### Requirement: Unmapped managed identity recovery requires unique complete evidence

Healthcare Lab SHALL classify an unmapped live Channel as recoverable only when exactly one Channel carries the exact expected Healthcare Lab marker and logical type, its complete owned payload is parseable, its identity is internally consistent, and its route is not owned by another Channel. Healthcare Lab MUST NOT infer ownership from Channel name alone.

#### Scenario: One valid marked Channel is recoverable

- **WHEN** a logical type has empty mapped identity and exactly one live Channel has its exact valid marker, logical type, parseable payload, and exclusively owned listener route
- **THEN** lifecycle reconciliation exposes that Channel as recoverable with its exact ID, name, revision, and current deployment state

#### Scenario: Duplicate ownership markers block recovery

- **WHEN** more than one live Channel carries the expected marker for one logical type
- **THEN** reconciliation classifies the identity as conflicted and permits no adoption or Channel mutation

#### Scenario: Malformed or mismatched identity blocks recovery

- **WHEN** a candidate payload is malformed, cannot normalize, has an unexpected logical type or template version, or contradicts a retained mapped identity
- **THEN** reconciliation classifies the identity as conflicted and permits no recovery or Channel mutation

#### Scenario: Same-name external Channel blocks recovery

- **WHEN** a Channel shares the canonical display name but lacks the exact expected ownership evidence
- **THEN** reconciliation does not adopt or mutate it and blocks ambiguous recovery for that logical type

#### Scenario: Route ownership conflict blocks recovery

- **WHEN** another live Channel owns or ambiguously claims the candidate's required listener route
- **THEN** reconciliation blocks recovery and leaves every involved Channel unchanged

### Requirement: Rebinding preserves recovered Channel state

Healthcare Lab SHALL revalidate a recoverable Channel immediately before binding and SHALL preserve all live Channel configuration and deployment state during identity recovery.

#### Scenario: Recovered Channel is deliberately stopped

- **WHEN** the uniquely recoverable Channel is stopped or undeployed
- **THEN** recovery persists its identity without deploying, redeploying, updating, undeploying, or deleting it

#### Scenario: Recovery evidence becomes stale

- **WHEN** candidate identity, revision, uniqueness, payload validity, or route ownership changes before binding
- **THEN** recovery fails closed without persisting the stale mapping or mutating an OIE Channel
