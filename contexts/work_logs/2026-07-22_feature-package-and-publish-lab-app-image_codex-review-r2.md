---
reviewer: codex
mode: closure
round: 2
branch: feature/package-and-publish-lab-app-image
base: main
reviewed_head: 9a3abf03dad47e6c46fc74d20ceffa486d07ce1d
previous_review: contexts/work_logs/2026-07-22_feature-package-and-publish-lab-app-image_codex-review-r1.md
previous_reviewed_head: 88896952043e90273fb6f05babbd3eab8cca70b0
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
| --- | --- | --- | --- |
| REV-001 | P1 | still-open | `.github/workflows/container-image.yml:69-80` checks repository visibility rather than GHCR package visibility, and `:91-125` skips the entire multi-tag publication whenever only the version tag already matches the commit. |
| REV-002 | P2 | resolved | `.github/workflows/container-image.yml:69-82` rejects non-stable-SemVer Release tags before login or registry mutation; `tests/test_container_workflow_contract.py` asserts the guard ordering and accepted form. |

## New blocking findings

### [P1][REV-001] Public-package preflight and rerun convergence remain incomplete

- Location: `.github/workflows/container-image.yml:69-80`, `:91-125`, `:137-144`.
- Impact: GitHub documents that a linked Container registry package inherits repository access permissions but not repository visibility, and that a newly published personal-account package defaults to private. Therefore `github.event.repository.visibility == public` does not establish that the stable image will be anonymously pullable. The anonymous check happens only after the tags are pushed, so a private package still produces the post-mutation failure pattern this finding required removing. On rerun, the presence of a matching `1.0.0` tag sets `skip_publish=true` for the entire build step. If the first multi-tag push stopped after creating that tag but before one or more of `1.0`, `1`, `latest`, or the SHA tag, the rerun cannot repair the missing aliases.
- Evidence: the release preflight reads only `github.event.repository.visibility`; the same-SHA guard inspects only `${IMAGE_NAME}:${VERSION}`; the build action containing all five release tags is then skipped as a unit. GitHub's package access documentation states that automatic repository inheritance covers access permissions, not visibility, and that first publication for a personal-account package defaults to private.
- Classification: prior blocker still open; the partial-alias behavior is part of the same required rerun-convergence acceptance target.
- Required resolution: establish and document a supported package-public prerequisite before stable tag mutation (for example, publish `edge`, set the GHCR package public in GitHub's package settings, and fail the stable job before login unless an anonymous preflight succeeds). Make same-commit reruns verify every expected release alias and either republish safely to repair missing/mismatched mutable aliases while never repointing an existing immutable version owned by another commit, or fail before mutation with a precise recoverable procedure. Add contract coverage for package visibility being checked before stable mutation and for incomplete same-commit alias recovery.

## Follow-up findings

- Pin the Docker base image digest and transitive Python dependencies in a later reproducible-build hardening change. This remains a non-blocking P2 follow-up outside the accepted release scope.

## Verification and residual risk

- Reviewed the closure delta `88896952043e90273fb6f05babbd3eab8cca70b0..9a3abf03dad47e6c46fc74d20ceffa486d07ce1d`, both prior findings, the workflow contract tests, and Verification Round 4.
- Verification Round 4 passed 606 tests, compile/diff/Compose/OpenSpec checks, exact-HEAD `linux/amd64` image inspection, HTTP/static/listener smoke, and replacement persistence.
- No live GHCR mutation was performed. Package visibility behavior was checked against GitHub's official package access documentation; multi-tag interruption remains a control-flow risk because the workflow treats one existing tag as proof that all aliases exist.
- `docs/handbook/` remains user-owned, untracked, and outside review scope.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-22_feature-package-and-publish-lab-app-image_codex-review-r2.md" REV-001`

Reason: the public-package precondition and interrupted multi-tag rerun path remain blocking.
