## ADDED Requirements

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
The supported Docker Compose deployment SHALL use the published `lab-app` image by default, preserve environment-based configuration and documented ports, and SHALL NOT mount the repository as the application source or install dependencies in its startup command.

#### Scenario: Start the complete lab from release assets
- **WHEN** an operator obtains the release deployment files, supplies a local `.env`, and starts Docker Compose
- **THEN** Compose pulls the versioned `lab-app` image and starts it with the existing lab network, persistent storage, GDT bridge, and service integration contracts

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
