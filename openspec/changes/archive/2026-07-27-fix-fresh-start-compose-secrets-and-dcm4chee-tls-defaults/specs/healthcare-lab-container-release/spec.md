## MODIFIED Requirements

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
