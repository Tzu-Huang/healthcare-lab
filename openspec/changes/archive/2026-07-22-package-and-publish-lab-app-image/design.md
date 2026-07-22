## Context

The current Compose service uses `python:3.11-slim`, bind-mounts the repository at `/workspace`, installs `requirements.txt` on every start, and runs `python app.py`. That is convenient for development but is not a downloadable release artifact. The complete lab also depends on independently maintained OIE, Medplum, PostgreSQL, Redis, dcm4chee, and LDAP images, so the project needs to package only its owned application while retaining Compose as the integration boundary.

The first supported release is `v1.0.0`, distributed as a public GHCR image for `linux/amd64`. It targets Docker on a local machine or trusted internal network. The dashboard currently mounts `/var/run/docker.sock` to inspect and control lab containers; that trust boundary remains explicit rather than being redesigned in this release.

## Goals / Non-Goals

**Goals:**

- Produce a self-contained, versioned `lab-app` image that starts quickly and predictably.
- Make Docker Compose the only supported end-user startup path.
- Separate continuously updated `main` images from immutable stable release images.
- Preserve external configuration, SQLite instance data, and GDT bridge data across upgrades.
- Make `v1.0.0` reproducible by pinning the complete verified image set and documenting operation and rollback.

**Non-Goals:**

- Combining third-party services into the `lab-app` image.
- Supporting direct host Python installation as a release path.
- Claiming `linux/arm64`, Apple Silicon, public-Internet, multi-replica, or regulated production-healthcare support.
- Adding application authentication, TLS termination, a reverse proxy, or a replacement for Docker socket access.
- Publishing the GitHub Release during proposal or implementation stages.

## Decisions

### Build one owned application image and retain Compose orchestration

A root Dockerfile will copy only required application/runtime files, install pinned Python dependencies during build, and expose the existing application and listener ports. Compose will continue to run each third-party component from its upstream image.

Building one monolithic image was rejected because it would duplicate upstream lifecycle and persistence responsibilities. Continuing the source bind mount was rejected because it makes the release depend on a checkout and permits host files to change the running version.

### Run the Flask application behind a production WSGI server

The image will use a Linux-compatible production WSGI server with a configuration compatible with the application's runtime ownership constraints. The user still invokes only Docker Compose; the WSGI server is an internal image detail. Worker/thread settings must not create multiple owners for the OIE result-listener socket.

Keeping the Flask development server was rejected because `v1.0.0` is the supported deployable baseline. Introducing a reverse proxy was deferred because TLS and public ingress are outside the trusted-lab scope.

### Keep mutable state and secrets out of image layers

`.dockerignore` will exclude `.env`, `.git`, `.venv`, caches, local instance content, temporary artifacts, and other non-runtime files. Compose will retain named storage for the application instance and a configurable bind mount for the GDT bridge. Configuration and credentials remain operator-supplied environment data.

Baking defaults or instance data into the image was rejected because it risks secret/data disclosure and prevents safe replacement of the container.

### Separate edge and stable publication policies

A verification workflow will build on pull requests without pushing. Successful `main` pushes will publish `edge` and a commit-derived tag. A stable GitHub Release publication will derive semantic-version aliases and update `latest`; draft and prerelease events will not move stable tags. Workflow permissions will be least-privilege, with package write access only in publishing jobs.

Updating `v1.0.0` on every `main` push was rejected because semantic-version tags must identify a reproducible artifact. Publishing from unverified pull requests was rejected because it exposes untrusted or failing builds.

### Build release tags from the release commit

Stable publication will build from the Git ref associated with the published GitHub Release and attach OCI source, revision, and version labels. Commit-SHA tags provide traceability between edge and release builds. The release workflow must fail closed when the version is malformed or verification fails.

Retagging an arbitrary existing `edge` image was rejected because the moving tag can race with release creation and obscure the exact source commit.

### Guarantee amd64 and pin the integrated stack

The initial build and documentation guarantee only `linux/amd64`, matching the currently verified Docker Desktop environment and avoiding unsupported claims about upstream ARM images. Compose defaults will replace unbounded third-party `latest` references with explicit verified versions; operators may still override image variables deliberately.

Publishing a multi-architecture `lab-app` alone was rejected for `v1.0.0` because it would imply a complete-lab capability that upstream services may not provide.

### Preserve Docker socket integration with an explicit warning

The current socket mount remains for dashboard control behavior. Release documentation will state that this grants the application powerful host Docker access and that the supported boundary is a trusted local/internal lab. A socket proxy or separate management agent is deferred to a later security change.

Removing the socket now was rejected because it would remove existing dashboard operations. Treating the mount as ordinary storage was rejected because users need an explicit security decision.

## Risks / Trade-offs

- [A production WSGI worker model starts duplicate background listeners] → Select and test a single-process configuration compatible with the documented listener ownership constraint.
- [A public image accidentally contains secrets or local healthcare data] → Use strict build-context exclusions and inspect the built image/context in verification.
- [A moving tag is mistaken for a stable release] → Document `edge` as mutable and keep semantic-version tags immutable.
- [A third-party pinned image becomes unavailable] → Record the verified version matrix and allow deliberate environment overrides without changing release defaults.
- [Docker socket compromise controls the host daemon] → Limit the supported trust boundary, document the privilege prominently, and defer public-network claims.
- [SQLite schema changes make rollback unsafe] → Require backup and rollback guidance and validate migrations separately from image replacement.

## Migration Plan

1. Add the container build inputs and production WSGI startup, then prove the image starts and passes a health smoke check on `linux/amd64`.
2. Update Compose to use the packaged image without the source mount/startup install while preserving the existing volumes, environment, ports, network, and Docker socket behavior.
3. Pin and verify third-party image versions and add operator documentation for a clean deployment, backup, upgrade, rollback, and the trust boundary.
4. Add pull-request, `main`, and stable-release automation; initially validate publishing against non-stable tags or workflow simulation without moving `latest`.
5. After `/dev-test`, `/dev-review`, and `/dev-done` approval, create and publish GitHub Release `v1.0.0`; verify all public tags resolve to the release commit and perform a clean Compose smoke test.
6. Rollback selects the previous immutable application tag and restores a compatible instance backup if a schema migration prevents application-only rollback.

## Open Questions

None. The release is public, Docker-only, `linux/amd64`, limited to a trusted local/internal lab, and keeps the existing Docker socket integration with an explicit warning.
