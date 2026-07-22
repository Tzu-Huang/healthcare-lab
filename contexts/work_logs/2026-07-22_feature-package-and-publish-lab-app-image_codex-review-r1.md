---
reviewer: codex
mode: initial
round: 1
branch: feature/package-and-publish-lab-app-image
base: main
reviewed_head: 88896952043e90273fb6f05babbd3eab8cca70b0
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
| --- | --- | --- | --- |
| REV-001 | P1 | open | `.github/workflows/container-image.yml:76` and `:115` make a failed post-push visibility step unrecoverable. |
| REV-002 | P2 | open | `.github/workflows/container-image.yml:76` and `:95` do not reject a non-SemVer stable Release before publishing moving tags. |

## New blocking findings

### [P1][REV-001] Post-push visibility call makes publication fail and cannot be rerun

- Location: `.github/workflows/container-image.yml:76-85`, `:103-121`.
- Impact: every publish job runs `gh api --method PATCH /user/packages/container/healthcare-lab` after pushing the image. GitHub's Packages REST endpoint catalog provides get/delete/restore operations for an authenticated user's package, but no package-update `PATCH` endpoint, so this step is not a supported way to set visibility. If it fails, the image tags have already moved; rerunning the same Release then fails earlier because the immutable version tag now exists. The workflow can leave `v1.0.0` published but the required job failed and cannot converge through a normal rerun.
- Evidence: the workflow's push is at lines 103-113 and the unsupported visibility mutation is at lines 115-121; the unconditional existing-tag rejection is at lines 76-85. GitHub documents that workflow reruns use the same `GITHUB_SHA` and `GITHUB_REF`, so the second run addresses the same tag.
- Classification: initial blocking correctness/release-operability finding.
- Required resolution: use a supported public-visibility contract (including repository-inherited visibility where applicable), verify anonymous accessibility without an unsupported mutation, and make same-release reruns idempotent when an existing immutable tag already points to the reviewed Release commit while still rejecting a different commit.

### [P2][REV-002] Non-SemVer stable Releases can update `latest`

- Location: `.github/workflows/container-image.yml:76-98`.
- Impact: any published, non-prerelease GitHub Release enters the publish job. For a tag such as `release-one`, the metadata action cannot derive the three SemVer aliases, but the raw `latest` and SHA rules remain enabled, so the workflow can move `latest` without publishing the required semantic-version tags. This violates the explicit stable-release requirement and the design decision to fail closed on malformed versions.
- Evidence: the only pre-publish guard checks whether the raw tag already exists; no SemVer validation precedes metadata generation, while `latest` is enabled solely by `github.event_name == 'release'`.
- Classification: explicit-acceptance P2 blocker.
- Required resolution: validate the Release tag against the accepted stable SemVer form before any registry mutation, fail closed when invalid, and add a policy test proving malformed stable Release tags cannot publish `latest` or any image tag.

## Follow-up findings

- The Docker base image and Python dependency ranges remain floating inputs for a future rebuild. The immutable published digest limits user-facing drift, but a later hardening change could pin the base digest and lock transitive Python dependencies for byte-for-byte rebuildability. This is a non-blocking P2 follow-up because the accepted requirement pins the Compose image matrix, not every build dependency.

## Verification and residual risk

- Reviewed `main...88896952043e90273fb6f05babbd3eab8cca70b0`, the OpenSpec requirement/design/task artifacts, Dockerfile, Compose, workflow policy tests, operator docs, and verification devlog.
- Verification Round 3 passed 605 tests, compile/diff/Compose/OpenSpec checks, exact-HEAD image inspection, isolated Compose health/listener/static/SQLite checks, and replacement persistence.
- No live GHCR package existed in this review session, so registry publication was assessed from workflow control flow and GitHub's official package/re-run contracts rather than by mutating the public registry.
- `docs/handbook/` remains user-owned, untracked, and explicitly outside this review scope.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-22_feature-package-and-publish-lab-app-image_codex-review-r1.md" REV-001 REV-002`

Reason: two blocking publication-workflow findings remain.
