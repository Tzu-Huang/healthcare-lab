---
change: package-and-publish-lab-app-image
date: 2026-07-22
---

## Context

Package the owned `lab-app` as the public, Docker-only v1.0.0 runtime and
separate verified `main` edge publication from stable GitHub Release tags.

## Implementation

- Added a self-contained `linux/amd64` Gunicorn image with one worker for OIE
  listener ownership, health check, external instance/GDT storage, and OCI
  metadata.
- Updated Compose to consume the GHCR image, preserve runtime mounts, and pin
  the verified third-party image matrix by digest.
- Added PR verification, `main` edge/SHA publication, stable SemVer/`latest`
  publication, immutable release-tag protection, and public GHCR visibility.
- Added Docker-only operator, persistence, upgrade, rollback, security-boundary,
  and v1.0.0 release-checklist documentation.

## Decisions

- Support `linux/amd64` and trusted local/internal labs for v1.0.0.
- Keep Docker Compose as the end-user entrypoint and third-party-service
  orchestration boundary.
- Retain Docker socket integration with an explicit host-control warning.
- Never allow `main` publication to repoint immutable semantic-version tags.

## Validation Plan

- Run the complete Python suite, compile/diff checks, Compose configuration
  validation, and strict OpenSpec validation against one committed HEAD.
- Build the exact HEAD image for `linux/amd64`, inspect excluded content, then
  run an isolated clean Compose smoke and verify health, static assets, SQLite,
  OIE listener state, and persistence.

## Follow-ups

- Publish `v1.0.0` only after verification and closure review approve the exact
  release commit.

## Verification

### Round 1 (2026-07-22T11:00:13+08:00)

- Tested head: `fd0e38fffe604b41f36c0352ab559469483a66d7`
- Status: `fail`
- Checks:
  - `python -m unittest discover -s tests` — pass; 605 tests in 136.549s.
  - `python -m compileall -q app.py backend tests` — pass.
  - `git diff --check` — pass.
  - `docker compose --env-file .env -f deploy/docker-compose.yml config --quiet` — pass.
  - `openspec validate package-and-publish-lab-app-image --strict` — pass.
  - `docker build --platform linux/amd64 ... -t healthcare-lab:verify-fd0e38f .` — pass; exact tested HEAD image built.
  - Image exclusion inspection — fail; `.env`, `.git`, tests, OpenSpec, and SQLite were absent, but nested `backend/**/__pycache__/*.pyc` files were present.
  - Isolated clean Compose smoke — skipped after the required image-content check failed; required before a passing round.
- Unresolved failures: Docker build context exclusion does not remove nested `__pycache__` directories and `.pyc` files.
- Next action: `/dev-fix "Docker image contains nested backend __pycache__/*.pyc files"`

### Round 2 (2026-07-22T11:10:24+08:00)

- Tested head: `88896952043e90273fb6f05babbd3eab8cca70b0`
- Status: `incomplete`
- Checks:
  - `python -m unittest discover -s tests` — pass; 605 tests in 167.704s.
  - `python -m compileall -q app.py backend tests` — pass.
  - `git diff --check` — pass.
  - `docker compose --env-file .env -f deploy/docker-compose.yml config --quiet` — pass.
  - `openspec validate package-and-publish-lab-app-image --strict` — pass.
  - Exact-HEAD `linux/amd64` image build — pass; OCI revision is `88896952043e90273fb6f05babbd3eab8cca70b0` and command is one-worker Gunicorn.
  - Image exclusion inspection — pass; no `.env`, Git metadata, tests, OpenSpec, SQLite data, `__pycache__`, or `.pyc` content was present.
  - Isolated Compose smoke — pass; healthy container, HTTP/static 200, listener `running` on 6665, SQLite named-volume storage, no `/workspace` source mount, and replacement persistence verified.
  - Disposable Compose container, volume, and GDT test folder cleanup — pass.
  - Post-check worktree attribution — incomplete; untracked `docs/handbook/USER_HANDBOOK.en.md` and `docs/handbook/USER_HANDBOOK.zh-TW.md` appeared during verification and are not part of the tested HEAD.
- Unresolved failures: verification cannot be attributed to a stable product tree while untracked handbook product documentation is present; the files were preserved without modification or deletion.
- Next action: `/dev-fix "untracked docs/handbook files prevent verification attribution to HEAD"`

### Round 3 (2026-07-22T11:17:03+08:00)

- Tested head: `88896952043e90273fb6f05babbd3eab8cca70b0`
- Status: `pass`
- Checks:
  - Preflight attribution — pass; the user explicitly excluded and retained untracked `docs/handbook/` files outside this change, while `devlog.md` is the workflow record.
  - `python -m unittest discover -s tests` — pass; 605 tests in 179.886s.
  - `python -m compileall -q app.py backend tests` — pass.
  - `git diff --check` — pass.
  - `docker compose --env-file .env -f deploy/docker-compose.yml config --quiet` — pass.
  - `openspec validate package-and-publish-lab-app-image --strict` — pass.
  - Exact-HEAD image identity and content — pass; `linux/amd64`, one-worker Gunicorn, OCI revision `88896952043e90273fb6f05babbd3eab8cca70b0`, and no `.env`, Git metadata, tests, OpenSpec, SQLite data, `__pycache__`, or `.pyc` content.
  - Isolated Compose smoke — pass; healthy container, HTTP/static 200, listener `running` on 6665, SQLite named-volume storage, no `/workspace` source mount, and replacement persistence verified.
  - Disposable Compose container, named volume, and GDT verification folder cleanup — pass.
- Unresolved failures: none.
- Next action: `/dev-review`

### Round 4 (2026-07-22T11:30:51+08:00)

- Tested head: `9a3abf03dad47e6c46fc74d20ceffa486d07ce1d`
- Status: `pass`
- Checks:
  - Preflight and post-check attribution — pass; only the existing review/devlog workflow records and user-excluded untracked `docs/handbook/` remain outside the tested product state, and `HEAD` stayed pinned.
  - `python -m unittest discover -s tests` — pass; 606 tests in 165.416s, including the release workflow regression contracts.
  - `python -m compileall -q app.py backend tests` — pass.
  - `git diff --check` — pass.
  - `docker compose --env-file .env -f deploy/docker-compose.yml config --quiet` — pass.
  - `openspec validate package-and-publish-lab-app-image --strict` — pass.
  - Exact-HEAD image build and inspection — pass; `linux/amd64`, OCI revision `9a3abf03dad47e6c46fc74d20ceffa486d07ce1d`, one-worker Gunicorn, and no `.env`, Git metadata, tests, OpenSpec, `__pycache__`, or `.pyc` content.
  - Isolated runtime smoke — pass; healthy container, HTTP/static 200, OIE listener accepted connections on 6665, named-volume data survived container replacement, and disposable container/volumes were cleaned up.
- Unresolved failures: none.
- Next action: `/dev-review`

### Round 5 (2026-07-22T11:41:05+08:00)

- Tested head: `5629853e576ae343da7406b33e30a46f7e171b71`
- Status: `pass`
- Checks:
  - Preflight and post-check attribution — pass; only the existing review/devlog workflow records and user-excluded untracked `docs/handbook/` remain outside the tested product state, and `HEAD` stayed pinned.
  - `python -m unittest discover -s tests` — pass; 607 tests in 152.786s, including public-package preflight and same-commit alias-repair contracts.
  - `python -m compileall -q app.py backend tests` — pass.
  - `git diff --check` — pass.
  - `docker compose --env-file .env -f deploy/docker-compose.yml config --quiet` — pass.
  - `openspec validate package-and-publish-lab-app-image --strict` — pass.
  - Exact-HEAD image build and inspection — pass; `linux/amd64`, OCI revision `5629853e576ae343da7406b33e30a46f7e171b71`, one-worker Gunicorn, and no `.env`, Git metadata, tests, OpenSpec, `__pycache__`, or `.pyc` content.
  - Isolated runtime smoke — pass; healthy container, HTTP/static 200, OIE listener accepted connections on 6665, named-volume data survived container replacement, and disposable container/volumes were cleaned up.
- Unresolved failures: none.
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-22T11:19:43+08:00)

- Source: `contexts/work_logs/2026-07-22_feature-package-and-publish-lab-app-image_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `88896952043e90273fb6f05babbd3eab8cca70b0`
- Transitions: `REV-001 open; REV-002 open`
- Open blockers: `REV-001`, `REV-002`
- Follow-ups: pin the Docker base digest and transitive Python dependencies in a later reproducible-build hardening change
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-22_feature-package-and-publish-lab-app-image_codex-review-r1.md" REV-001 REV-002`

### Round 2 (2026-07-22T11:35:00+08:00)

- Source: `contexts/work_logs/2026-07-22_feature-package-and-publish-lab-app-image_codex-review-r2.md`
- Mode: `closure`
- Verdict: `changes-requested`
- Reviewed head: `9a3abf03dad47e6c46fc74d20ceffa486d07ce1d`
- Transitions: `REV-001 still-open; REV-002 resolved`
- Open blockers: `REV-001`
- Follow-ups: pin the Docker base image digest and transitive Python dependencies in a later reproducible-build hardening change
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-22_feature-package-and-publish-lab-app-image_codex-review-r2.md" REV-001`

### Round 3 (2026-07-22T11:44:00+08:00)

- Source: `contexts/work_logs/2026-07-22_feature-package-and-publish-lab-app-image_codex-review-r3.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `5629853e576ae343da7406b33e30a46f7e171b71`
- Transitions: `REV-001 resolved; REV-002 resolved`
- Open blockers: `none`
- Follow-ups: pin the Docker base image digest and transitive Python dependencies in a later reproducible-build hardening change
- Next action: commit only the review and devlog workflow records, then run `/dev-done`
