## MODIFIED Requirements

### Requirement: YOLO-resistant mutation boundaries fail closed

Healthcare Lab MUST provide no force, wildcard, bulk, skip-preview, automatic-adoption, or revision-override path for managed Channel mutations, and SHALL revalidate ownership and live state immediately before every mutation. Automatic startup mutation is limited to guarded single-target creation and deployment of Channels classified as missing when explicit `create-missing` bootstrap mode is enabled.

#### Scenario: Caller requests a force or override operation

- **WHEN** a caller attempts to bypass conflict, ownership, preview, or revision protection
- **THEN** Healthcare Lab rejects the request
- **AND** never calls OIE with `override=true`

#### Scenario: Caller attempts bulk mutation

- **WHEN** a request contains multiple targets, a wildcard, or an OIE redeploy-all request
- **THEN** Healthcare Lab rejects or does not expose the operation
- **AND** no managed or external Channel is mutated

#### Scenario: Application starts with bootstrap disabled

- **WHEN** Healthcare Lab starts or reloads configuration with bootstrap mode `off`
- **THEN** it does not create, update, deploy, undeploy, delete, or adopt any OIE Channel automatically

#### Scenario: Application starts with create-missing bootstrap

- **WHEN** Healthcare Lab starts with bootstrap mode `create-missing`
- **THEN** it may create and deploy only an exact managed Channel freshly classified as `Missing` through state-bound guarded operations
- **AND** it does not update, adopt, redeploy, undeploy, or delete any existing Channel

#### Scenario: Destructive confirmation does not match

- **WHEN** delete confirmation does not exactly match the targeted logical type
- **THEN** Healthcare Lab rejects deletion before calling OIE

#### Scenario: Target changes after confirmation

- **WHEN** ownership, Channel ID, revision, or classification changes between confirmation and execution
- **THEN** Healthcare Lab fails closed and returns a fresh-preview requirement
