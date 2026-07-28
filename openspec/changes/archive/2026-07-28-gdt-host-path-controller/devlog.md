---
change: gdt-host-path-controller
date: 2026-07-28
---

## Context

Healthcare Lab now lets a local Windows operator select one dedicated GDT host folder from the GDT console while retaining `/data/gdt-bridge` as the fixed container-visible path.

## Implementation

- Added bounded host-path policy, provisioning, precedence, and controller-owned state.
- Added a loopback PowerShell controller with strict origin/token checks and serialized asynchronous apply operations.
- Added wrapper-managed controller lifecycle and isolated `lab-app` recreation.
- Replaced separate editable inbox/outbox paths with one host root and derived paths.
- Added controller, wrapper, Compose, backend, frontend, and security-negative coverage.

## Decisions

- Deployment-owned host paths remain separate from typed GDT protocol and watcher settings.
- The browser talks to a loopback-only controller; `lab-app` does not recreate itself through the Docker socket.
- Advanced process and `.env` overrides retain higher precedence and are never silently overwritten.

## Validation Plan

- Run the complete Python suite, Python compilation, frontend JavaScript syntax checks, Compose rendering, OpenSpec strict validation, and diff hygiene.
- Verify path change, controller restart, conflict, failure, retry, rollback, retention, and cleanup in an isolated Docker Desktop Compose project.

## Follow-ups

- Resolve any quality-gate findings before initial code review.

## Verification

### Round 1 (2026-07-28 16:34:00 +08:00)

- Tested head: `4e2989e44bf7f202c578de63779b1ae6d3b9dffc`
- Status: `fail`
- Checks:
  - `python -m unittest -q` — **fail**; 951 tests ran with 1 failure and 1 skip. `tests.test_configuration_ownership.ConfigurationOwnershipContractTests.test_every_declared_environment_and_compose_key_has_exactly_one_owner` reports that `GDT_HOST_CONTROLLER_URL` has no configuration ownership entry.
  - `python -m compileall -q app.py backend tests` — **pass**.
  - `node --check frontend/static/js/api/gdt.js`, `frontend/static/js/views/gdt.js`, and `frontend/static/js/settings/gdt-bridge.js` — **pass**.
  - `docker compose -f deploy/docker-compose.yml config --quiet` — **pass**.
  - `openspec validate gdt-host-path-controller --strict` — **pass**.
  - `git diff main...HEAD --check` — **pass**.
  - Isolated Docker Desktop controller matrix — **pass**; valid path changes, controller restart, advanced-override conflict, failed apply, retry, rollback, retained bind content, isolated cleanup, and unchanged original `interoperability-lab` identity/bind were confirmed during apply.
  - Pre/post product state — **pass**; tested HEAD remained unchanged and the worktree was clean before checks.
- Unresolved failures: add exactly one ownership entry for `GDT_HOST_CONTROLLER_URL` and rerun verification.
- Next action: `/dev-fix "register GDT_HOST_CONTROLLER_URL in configuration ownership"`

### Round 2 (2026-07-28 16:41:00 +08:00)

- Tested head: `da26161e8365aff528f835665afbb7e49b0f24c5`
- Status: `pass`
- Checks:
  - `python -m unittest -q` — **pass**; 951 tests passed with 1 non-required platform/local-fixture skip.
  - `python -m compileall -q app.py backend tests` — **pass**.
  - `node --check frontend/static/js/api/gdt.js`, `frontend/static/js/views/gdt.js`, and `frontend/static/js/settings/gdt-bridge.js` — **pass**.
  - `docker compose -f deploy/docker-compose.yml config --quiet` — **pass**.
  - `openspec validate gdt-host-path-controller --strict` — **pass**.
  - `git diff main...HEAD --check` — **pass**.
  - Isolated Docker Desktop controller matrix — **pass**; the previously completed path-change, controller-restart, conflict, failure, retry, rollback, retention, cleanup, and original-lab isolation evidence remains applicable because the post-fix product change only registers configuration ownership and updates its documentation.
  - Pre/post product state — **pass**; tested HEAD remained `da26161e8365aff528f835665afbb7e49b0f24c5`, with only this ignored OpenSpec devlog workflow record updated after checks.
- Unresolved failures: none.
- Next action: `/dev-review`

### Round 3 (2026-07-28 16:51:00 +08:00)

- Tested head: `f97a6b55b6842f60f3935fb5d52ae3d00f46f346`
- Status: `pass`
- Checks:
  - `python -m unittest -q` — **pass**; 955 tests passed with 1 non-required platform/local-fixture skip. The first invocation exceeded the runner's 120-second limit without an assertion failure; the completed rerun passed in 221 seconds.
  - Focused GDT controller/wrapper regressions — **pass** within the full suite; coverage includes installation-scoped controller identity, stale PID rejection, deployment verification contract, and stage-specific failure evidence.
  - `python -m compileall -q app.py backend tests` — **pass**.
  - `node --check frontend/static/js/api/gdt.js`, `frontend/static/js/views/gdt.js`, and `frontend/static/js/settings/gdt-bridge.js` — **pass**.
  - `docker compose -f deploy/docker-compose.yml config --quiet` — **pass**.
  - `openspec validate gdt-host-path-controller --strict` — **pass**.
  - `git diff main...HEAD --check` — **pass**.
  - Isolated Docker Desktop matrix — **pass** from the earlier same-change verification for path change, controller restart, conflict, failure, retry, rollback, retention, cleanup, and original-lab isolation; Round 3 reverified the changed verification, ownership, and failure-state contracts through focused regressions.
  - Pre/post product state — **pass**; tested product HEAD remained unchanged, with only ignored workflow records updated.
- Unresolved failures: none.
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-28 16:44:00 +08:00)

- Source: `contexts/work_logs/2026-07-28_feature-gdt-host-path-controller_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `da26161e8365aff528f835665afbb7e49b0f24c5`
- Transitions: `REV-001 open; REV-002 open; REV-003 open`
- Open blockers: `REV-001`, `REV-002`, `REV-003`
- Follow-ups: local HTTP connection read-deadline hardening
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-28_feature-gdt-host-path-controller_codex-review-r1.md"`

### Round 2 (2026-07-28 16:53:00 +08:00)

- Source: `contexts/work_logs/2026-07-28_feature-gdt-host-path-controller_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `f97a6b55b6842f60f3935fb5d52ae3d00f46f346`
- Transitions: `REV-001 resolved; REV-002 resolved; REV-003 resolved`
- Open blockers: `none`
- Follow-ups: add a per-connection read deadline to the loopback HTTP parser
- Next action: `/dev-done`
