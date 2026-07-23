---
change: provision-missing-managed-channels-on-startup
date: 2026-07-23
---

# Development Log

## Context

ZAC-67 adds bounded, idempotent startup provisioning for the two canonical Healthcare Lab-managed OIE Channels.

## Implementation

- Added validated bootstrap configuration, canonical mapping seeding, guarded asynchronous coordination, eager production startup, containerized Channel templates, and deployment documentation.
- Preserved existing, stopped, drifted, conflicted, and external Channels without mutation.

## Decisions

- Startup provisioning is limited to `create-missing` and can be disabled with `off`.
- Mutation stops after uncertain mutation or persistence failure, and audit evidence remains secret-safe.

## Validation Plan

- Run focused bootstrap/settings/lifecycle/runtime tests and the complete regression suite.
- Compile Python sources, validate the OpenSpec change strictly, validate Compose configuration, and run `git diff --check`.
- Confirm clean, restart, and partial isolated Compose scenarios for the canonical Channel pair.

## Follow-ups

- Complete initial code review after verification.

## Verification

### Round 1 (2026-07-23 09:25:21 +08:00)

- Tested head: `9f4e75e19dcac0e97a6ed7dd5dcaa34ab9e9a9e0`
- Status: `pass`
- Checks: PASS — focused bootstrap/settings/lifecycle/runtime unittest selection (77 tests); PASS — complete unittest discovery (624 tests) after one isolated Chromium `ERR_NETWORK_CHANGED` retry, with the failed test passing alone and the clean full rerun passing; PASS — `python -m compileall -q app.py backend tests`; PASS — `openspec validate provision-missing-managed-channels-on-startup --strict`; PASS — `docker compose --env-file .env -f deploy/docker-compose.yml config --quiet`; PASS — `git diff --check`; PASS — operator-reported isolated live Compose acceptance at the tested HEAD covered clean creation/start of both Channels, restart ID retention with zero mutations, and partial recreation of only the deleted Channel, followed by cleanup while preserving the existing lab stack; PASS — pre-check product state was clean and post-check state contains only this workflow devlog.
- Unresolved failures: none.
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-23 09:28:18 +08:00)

- Source: `contexts/work_logs/2026-07-23_feature-ZAC-67_provision-missing-managed-channels-on-startup_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `9f4e75e19dcac0e97a6ed7dd5dcaa34ab9e9a9e0`
- Transitions: `REV-001 open`
- Open blockers: `REV-001`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-23_feature-ZAC-67_provision-missing-managed-channels-on-startup_codex-review-r1.md"`

## Verification

### Round 2 (2026-07-23 09:36:13 +08:00)

- Tested head: `aea0a410baf3491af50b2f4531f0a9f2649f6a98`
- Status: `pass`
- Checks: PASS — focused bootstrap/lifecycle/repository/runtime unittest selection (50 tests), including durable no-op, blocker, timeout, and audit-failure outcomes; PASS — complete unittest discovery (626 tests); PASS — `python -m compileall -q app.py backend tests`; PASS — `openspec validate provision-missing-managed-channels-on-startup --strict`; PASS — `docker compose --env-file .env -f deploy/docker-compose.yml config --quiet`; PASS — `git diff --check`; PASS — prior isolated live Compose acceptance remains applicable to the unchanged create/deploy mutation path, while the fix delta's durable SQLite audit behavior is covered by focused repository and coordinator tests; PASS — pre/post product state remained clean and only the existing review workflow artifact was dirty.
- Unresolved failures: none.
- Next action: `/dev-review`

## Code Review

### Round 2 (2026-07-23 09:38:07 +08:00)

- Source: `contexts/work_logs/2026-07-23_feature-ZAC-67_provision-missing-managed-channels-on-startup_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `aea0a410baf3491af50b2f4531f0a9f2649f6a98`
- Transitions: `REV-001 resolved`
- Open blockers: none
- Follow-ups: none
- Next action: commit only the review/devlog workflow records, then run `/dev-done`
