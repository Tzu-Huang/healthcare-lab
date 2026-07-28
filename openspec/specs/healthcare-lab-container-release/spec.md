# healthcare-lab-container-release Specification

## Purpose
TBD - created by archiving change package-and-publish-lab-app-image. Update Purpose after archive.
## Requirements
### Requirement: Self-contained lab-app image
The project SHALL provide a `linux/amd64` container image that contains the tracked `lab-app` source and installed runtime dependencies, starts the application through a production WSGI server, and does not require a source-code mount or dependency installation during container startup.

#### Scenario: Start a pulled image
- **WHEN** an operator starts a published image with the required environment and persistent mounts
- **THEN** the Healthcare Lab HTTP application becomes healthy without cloning the repository into the container or installing Python packages at startup

#### Scenario: Exclude local and secret content
- **WHEN** the image build context is assembled
- **THEN** Git metadata, virtual environments, caches, local `.env` files, instance data, and other local runtime artifacts are excluded from the image

### Requirement: Persistent runtime data remains external
The packaged runtime SHALL keep mutable instance data and the GDT bridge outside the image and SHALL preserve those mounts across image replacement.

#### Scenario: Upgrade the application image
- **WHEN** an operator replaces a running `lab-app` container with a newer compatible image while retaining the documented mounts
- **THEN** the application reuses the existing instance database and GDT bridge content rather than initializing them inside the image layer

### Requirement: Compose consumes the packaged image
The supported Docker Compose deployment SHALL use a published `lab-app` image that implements the documented guided Settings readiness API by default, preserve documented ports and persistent storage, provide safe local interpolation defaults, and SHALL NOT require a repository-root `.env`, optional application integration secret variables, a repository source mount, or dependency installation in its startup command.

#### Scenario: Start the complete lab from release assets without an env file
- **WHEN** an operator obtains the release deployment files and runs the documented Compose startup command without creating a repository-root `.env` or defining optional application integration credentials
- **THEN** Compose renders successfully, pulls the versioned `lab-app` image, and starts it with the existing lab network, persistent storage, GDT bridge, and service integration contracts
- **AND** the application readiness API reports missing required credentials as secret-safe `needs-setup` instead of a Compose interpolation or container-startup failure

#### Scenario: Default image exposes guided readiness
- **WHEN** the default versioned `lab-app` image becomes healthy
- **THEN** `GET /api/settings/readiness` returns the documented stable readiness envelope
- **AND** the image behavior agrees with the release handbook bundled with the deployment files

#### Scenario: Apply an advanced deployment override
- **WHEN** an operator supplies a documented image, host-published port, bind-mount, database credential, or security-hardening override
- **THEN** Compose applies that override without requiring application-level integration settings to remain in the deployment file

#### Scenario: Use the trusted Docker control integration
- **WHEN** the release Compose configuration mounts the Docker socket for dashboard control features
- **THEN** the deployment documentation identifies the host-control privilege and limits the supported deployment boundary to a trusted local or internal lab

### Requirement: Main branch image publication
The repository automation SHALL verify pull requests without publishing images and SHALL publish `edge` plus a commit-SHA traceability tag only after a push to `main` passes required tests and image validation.

#### Scenario: Validate a pull request
- **WHEN** a pull request changes application, container, deployment, or workflow inputs
- **THEN** automation runs the required tests and builds the image without authenticating to or publishing into GHCR

#### Scenario: Publish a successful main build
- **WHEN** a commit is pushed to `main` and all required verification succeeds
- **THEN** GHCR receives an updated `edge` tag and an immutable tag identifying that commit

#### Scenario: Reject a failed main build
- **WHEN** required verification fails for a `main` commit
- **THEN** automation does not update any published image tag

### Requirement: Stable release image publication
The repository automation SHALL publish public semantic-version image tags from a non-prerelease GitHub Release only after verification succeeds. A `v1.0.0` release SHALL publish `1.0.0`, `1.0`, `1`, `latest`, and the commit-SHA tag, while the immutable `1.0.0` tag SHALL never be repointed by later `main` pushes.

#### Scenario: Publish v1.0.0
- **WHEN** GitHub Release `v1.0.0` is published as a stable release and verification succeeds
- **THEN** the image is publicly pullable from `ghcr.io/tzu-huang/healthcare-lab` using `1.0.0`, `1.0`, `1`, `latest`, and the release commit-SHA tag

#### Scenario: Push main after v1.0.0
- **WHEN** a later commit is pushed to `main`
- **THEN** automation may update `edge` but does not change the image referenced by `1.0.0`

#### Scenario: Draft or prerelease does not move latest
- **WHEN** a GitHub Release is a draft, remains unpublished, or is marked as a prerelease
- **THEN** automation does not update the stable `latest` tag

### Requirement: Reproducible release composition
The `v1.0.0` deployment SHALL pin all third-party Compose images to explicit versions and SHALL document the verified component versions, supported `linux/amd64` platform, configuration, startup, health check, data backup, upgrade, and rollback procedures.

#### Scenario: Recreate the v1.0.0 lab
- **WHEN** an operator deploys the `v1.0.0` release files at a later date
- **THEN** Compose selects the documented application and third-party image versions rather than an unbounded `latest` dependency

#### Scenario: Roll back lab-app
- **WHEN** an operator follows the documented rollback procedure while retaining compatible persistent data
- **THEN** Compose can select the previous semantic-version image without changing the immutable release tag

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
