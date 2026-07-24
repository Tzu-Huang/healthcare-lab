## MODIFIED Requirements

### Requirement: Compose consumes the packaged image
The supported Docker Compose deployment SHALL use the published `lab-app` image by default, preserve documented ports and persistent storage, provide safe local interpolation defaults, and SHALL NOT require a repository-root `.env`, mount the repository as application source, or install dependencies in its startup command.

#### Scenario: Start the complete lab from release assets without an env file
- **WHEN** an operator obtains the release deployment files and runs the documented Compose startup command without creating a repository-root `.env`
- **THEN** Compose renders successfully, pulls the versioned `lab-app` image, and starts it with the existing lab network, persistent storage, GDT bridge, and service integration contracts

#### Scenario: Apply an advanced deployment override
- **WHEN** an operator supplies a documented image, host-published port, bind-mount, database credential, or security-hardening override
- **THEN** Compose applies that override without requiring application-level integration settings to remain in the deployment file

#### Scenario: Use the trusted Docker control integration
- **WHEN** the release Compose configuration mounts the Docker socket for dashboard control features
- **THEN** the deployment documentation identifies the host-control privilege and limits the supported deployment boundary to a trusted local or internal lab

## ADDED Requirements

### Requirement: Supported wrapper is deterministic with or without env overrides
The supported deployment wrapper SHALL run start, status, inspect, restart, smoke, logs, and stop actions using the same absolute Compose file, SHALL pass the repository-root `.env` only when it exists, and MUST NOT print environment values or secrets.

#### Scenario: Wrapper starts a clean checkout
- **WHEN** the repository-root `.env` does not exist and the operator runs the wrapper start action
- **THEN** the wrapper invokes Compose without an `--env-file` argument and the stack uses checked-in safe local defaults

#### Scenario: Wrapper uses an existing override file
- **WHEN** a repository-root `.env` exists and the operator runs a supported wrapper action
- **THEN** the wrapper passes that exact file as an explicit interpolation source and preserves supported advanced overrides

#### Scenario: Wrapper reports a failure
- **WHEN** Docker Compose returns a non-zero result
- **THEN** the wrapper reports the bounded action and exit status without printing secret values or the contents of the override file

### Requirement: Supported mutable directories require no YAML editing
The supported deployment flow SHALL provision or validate the known application instance and GDT bridge directory contract before startup without editing Compose YAML, and SHALL preserve their contents across compatible container recreation.

#### Scenario: Default GDT directory is absent
- **WHEN** an operator starts a clean checkout using the default repository-local GDT bind path
- **THEN** the supported flow creates the required bounded directory contract and Compose can mount it without manual YAML edits

#### Scenario: Application container is recreated
- **WHEN** the operator recreates `lab-app` while retaining its instance volume and configured GDT mount
- **THEN** persisted typed Settings and GDT bridge content remain available to the replacement container

#### Scenario: Unsafe path is supplied
- **WHEN** an advanced bind-mount override resolves to an empty, root, or otherwise unsupported broad target
- **THEN** provisioning fails with bounded guidance and performs no recursive creation, deletion, or movement
