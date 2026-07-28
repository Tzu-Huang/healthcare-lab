## MODIFIED Requirements

### Requirement: Supported wrapper is deterministic with or without env overrides

The supported deployment wrapper SHALL run start, status, inspect, restart, smoke, logs, stop, and bounded GDT host-controller lifecycle actions using the same absolute Compose file, SHALL apply documented precedence across process environment, repository-root `.env`, controller-owned deployment state, and checked-in defaults, and MUST NOT print environment values, controller authorization values, or secrets.

#### Scenario: Wrapper starts a clean checkout

- **WHEN** neither the repository-root `.env` nor controller-owned GDT deployment state exists and the operator runs the wrapper start action
- **THEN** the stack uses checked-in safe local defaults
- **AND** the wrapper starts or confirms one owned localhost GDT controller

#### Scenario: Wrapper uses controller-owned GDT state

- **WHEN** a controller-owned GDT host root exists without a higher-precedence override
- **THEN** the wrapper supplies that exact validated root to Compose
- **AND** compatible `lab-app` recreation preserves the selected bridge data

#### Scenario: Wrapper uses an existing advanced override

- **WHEN** a repository-root `.env` or process environment defines a supported higher-precedence override
- **THEN** the wrapper applies that override
- **AND** reports its ownership class without exposing its value in logs

#### Scenario: Wrapper reports a failure

- **WHEN** Docker Compose or controller lifecycle returns a non-zero result
- **THEN** the wrapper reports the bounded action and exit status without printing secret values, authorization values, or override-file contents

### Requirement: Supported mutable directories require no YAML editing

The supported deployment flow SHALL provision or validate the known application instance and GDT bridge directory contract from defaults, advanced overrides, or controller-owned host state before startup without editing Compose YAML, and SHALL preserve their contents across compatible container recreation.

#### Scenario: Default GDT directory is absent

- **WHEN** an operator starts a clean checkout using the default repository-local GDT bind path
- **THEN** the supported flow creates the required bounded directory contract and Compose can mount it without manual YAML or `.env` edits

#### Scenario: UI-selected GDT directory is absent

- **WHEN** the bounded host controller applies a valid missing dedicated GDT root
- **THEN** it creates the required bounded directory contract
- **AND** recreates only `lab-app` with that bind source
- **AND** persists the selection for later supported wrapper starts

#### Scenario: Application container is recreated

- **WHEN** the operator or controller recreates `lab-app` while retaining its instance volume and configured GDT mount
- **THEN** persisted typed Settings and GDT bridge content remain available to the replacement container

#### Scenario: Unsafe path is supplied

- **WHEN** a default, advanced, or UI-selected bind-mount source resolves to an empty, root, traversing, repository-owned, deployment-owned, or otherwise unsupported broad target
- **THEN** provisioning fails with bounded guidance
- **AND** performs no recursive creation, deletion, or movement
