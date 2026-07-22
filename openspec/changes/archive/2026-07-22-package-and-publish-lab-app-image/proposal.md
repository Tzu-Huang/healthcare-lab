## Why

Healthcare Lab is deployable through Docker Compose, but `lab-app` still mounts the repository and installs dependencies at container startup, so another user cannot pull a versioned, reproducible application image. The first supported Docker release should publish the working application as `v1.0.0` and establish predictable image updates for `main` and future GitHub Releases.

## What Changes

- Package `lab-app` as a self-contained Linux container image that runs the Flask application behind a production WSGI server without mounting source code or installing dependencies at startup.
- Publish a public `linux/amd64` image at `ghcr.io/tzu-huang/healthcare-lab` after verification succeeds.
- Publish mutable `edge` and immutable commit-SHA tags from pushes to `main`; pull requests build and test without publishing.
- Publish immutable semantic-version tags plus the moving `latest` tag only when a non-prerelease GitHub Release is published, beginning with `v1.0.0`.
- Update the Compose runtime to consume the packaged image while preserving instance data, the external GDT bridge, environment configuration, and the existing trusted-lab Docker socket integration.
- Pin third-party Compose images to explicit versions and document image acquisition, supported platform, persistence, upgrades, rollback, and the Docker socket trust boundary.

## Capabilities

### New Capabilities

- `healthcare-lab-container-release`: Defines the packaged `lab-app` runtime, Compose consumption contract, GHCR publication triggers and tags, release verification, persistence, and operator-facing deployment guidance.

### Modified Capabilities

None.

## Impact

- Container build inputs: a new Dockerfile, build context exclusions, production WSGI dependency and entrypoint.
- Deployment: `deploy/docker-compose.yml`, `.env.example`, deployment documentation, pinned third-party image references, persistent mounts, and the documented Docker socket security boundary.
- Automation: GitHub Actions for pull-request validation, `main` edge publication, and GitHub Release semantic-version publication to public GHCR.
- Verification: container build and smoke coverage, Compose contract tests, tag-policy checks, and a clean-environment deployment exercise for `linux/amd64`.
- Release operations: creation of the `v1.0.0` Git tag and published GitHub Release remains a release-stage action after implementation, verification, and approval; proposal creation does not publish it.
