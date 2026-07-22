## 1. Container Runtime

- [x] 1.1 Add focused contract tests for build-context exclusions, required runtime files, production WSGI startup, and the absence of source-mount/startup-install assumptions.
- [x] 1.2 Add the production WSGI dependency and an application entrypoint/configuration that preserves single-process OIE listener ownership.
- [x] 1.3 Add the root Dockerfile and `.dockerignore` for a self-contained, non-root where compatible, `linux/amd64` `lab-app` image with OCI source/revision/version metadata support.
- [x] 1.4 Build the image locally and verify HTTP health, static assets, SQLite initialization/migration, and the OIE result-listener runtime without a repository mount.

## 2. Compose and Persistence

- [x] 2.1 Update Compose contract tests for the published `lab-app` image, removal of the repository bind mount and startup `pip install`, and preservation of ports, environment, network, instance volume, GDT bridge, and Docker socket integration.
- [x] 2.2 Change `deploy/docker-compose.yml` and `.env.example` to select a versioned GHCR image by default while retaining an intentional `LAB_APP_IMAGE` override.
- [x] 2.3 Replace unbounded third-party `latest` defaults with explicit verified versions and record the integrated `v1.0.0` component matrix.
- [x] 2.4 Verify container replacement retains SQLite instance data and GDT bridge content, and record backup/restore evidence needed for upgrade and rollback.

## 3. GitHub Image Automation

- [x] 3.1 Add workflow-policy tests or static checks for pull-request validation, least-privilege permissions, allowed publication events, public GHCR naming, and semantic-version tag derivation.
- [x] 3.2 Add pull-request automation that runs required product tests and builds the `linux/amd64` image without publishing.
- [x] 3.3 Add successful-`main` publication of mutable `edge` and immutable commit-SHA tags, with no tag update after failed verification.
- [x] 3.4 Add stable GitHub Release publication of semantic-version aliases, `latest`, commit-SHA, and OCI metadata while excluding drafts and prereleases from stable publication.
- [x] 3.5 Validate that `v1.0.0` cannot be overwritten by a later `main` build and that publishing jobs use only the package-write permission and credentials they require.

## 4. Operator Documentation

- [x] 4.1 Update the root and deployment README files with the Docker-only installation path, public pull/Compose commands, supported `linux/amd64` platform, configuration, ports, and health verification.
- [x] 4.2 Document persistence, backup, upgrade, rollback, immutable versus moving tags, and the verified third-party version matrix.
- [x] 4.3 Add a prominent trusted-local/internal-lab boundary and Docker socket host-control warning, and state that public-Internet, regulated production, ARM, and multi-replica support are not claimed.
- [x] 4.4 Add `v1.0.0` release notes/checklist covering artifacts, image tags, source revision, clean-environment smoke verification, and post-publication checks without publishing the release during implementation.

## 5. Verification and Release Readiness

- [ ] 5.1 Run focused container, Compose, workflow-policy, persistence, configuration, and application regression tests plus compile/syntax and diff checks.
- [ ] 5.2 Run a clean `linux/amd64` deployment using only release-intended files and pulled/built images, then verify lab-app health and its supported integrations without a source checkout inside the container.
- [ ] 5.3 Inspect the final image and deployment artifacts for `.env`, credentials, Git metadata, local instance data, caches, and other unintended content.
- [ ] 5.4 Validate the OpenSpec change strictly and record the exact commit and verification evidence eligible for the later `v1.0.0` GitHub Release.
