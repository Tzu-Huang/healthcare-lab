## Why

Healthcare Lab currently resolves runtime integration configuration from competing sources including process environment, Flask configuration, Lab Server inventory, and the dedicated OIE settings tables. Adding more Settings UI fields before establishing one typed ownership and persistence contract would make restart behavior ambiguous, expose secrets to inconsistent handling, and allow later integrations to bypass validation and auditing.

## What Changes

- Publish a complete configuration ownership matrix for Medplum, OIE, GDT, dcm4chee, OpenEMR, AP-facing routes, and deployment infrastructure, classifying every setting as deployment-only, runtime persisted, secret, or derived/default.
- Add a shared persisted-settings repository and service boundary for named, integration-specific typed profiles without introducing an arbitrary key-value store.
- Add typed public projections, field validation, atomic profile mutation, and stable validation/error shapes suitable for later Settings APIs.
- Define write-only secret semantics: reads expose configured state only, omitted or blank replacement preserves the saved secret, replacement accepts a non-blank value, and removal requires an explicit operation.
- Seed a missing persisted profile once from eligible environment values and safe local defaults, while never overwriting an existing operator-managed profile on restart.
- Provide request-context-independent effective configuration readers so runtime consumers can migrate away from direct environment, Flask request, and raw SQL access.
- Record secret-safe mutation audits containing only allowlisted profile identity, operation, field names, outcome, and timestamps.
- Adapt the existing OIE settings profile through the shared boundary while preserving its current schema, managed-Channel mappings, audit controls, and lifecycle safety.

## Capabilities

### New Capabilities

- `healthcare-lab-typed-integration-settings`: Defines configuration ownership, typed profile persistence, environment bootstrap, effective configuration reads, secret mutation semantics, stable API projections/errors, atomic validation, and value-free auditing.

### Modified Capabilities

- `healthcare-lab-oie-settings-profile`: Requires the existing OIE profile to participate in the shared typed settings boundary without weakening its specialized persistence, secret protection, or managed-Channel contracts.

## Impact

The change affects application configuration and composition, ordered SQLite migrations, settings repositories and services, typed API/domain projections, OIE settings adaptation, integration runtime consumers, configuration documentation, and unit/repository/integration tests. It introduces no generic settings bag, does not redesign the Settings page, does not add integration-specific forms, and does not edit Compose configuration or restart containers.
