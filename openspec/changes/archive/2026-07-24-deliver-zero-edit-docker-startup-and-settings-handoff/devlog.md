---
change: deliver-zero-edit-docker-startup-and-settings-handoff
date: 2026-07-24
---

## Context

ZAC-77 removes the mandatory repository-root `.env` from the supported local
Docker start and hands incomplete application configuration to persisted,
typed Settings.

## Implementation

- Removed blanket Compose env-file injection while retaining pinned local
  defaults and an explicit one-time legacy bootstrap allowlist.
- Made the PowerShell wrapper deterministic with optional `.env` handling and
  bounded GDT host-directory provisioning.
- Preserved typed-profile precedence, secret-safe migration evidence, and data
  persistence across dependency/container recreation.
- Added a non-blocking Dashboard readiness notice that opens the authoritative
  Settings section.
- Reworked the deployment template and operator documentation around normal
  Settings setup versus Advanced deployment overrides.

## Decisions

- Dashboard guidance is explicit rather than an unconditional redirect.
- Persisted typed profiles remain authoritative after create-only environment
  bootstrap.
- dcm4chee internal HL7 configuration and host publication use distinct keys.
- The web application does not edit Compose or gain arbitrary Docker authority.

## Validation Plan

- Run focused deployment, wrapper, migration, ownership, Settings, and frontend
  contracts.
- Run the complete repository unittest suite.
- Check Python compilation, changed JavaScript syntax, clean and overridden
  Compose rendering, secret-canary behavior, strict OpenSpec validation, and
  Git diff hygiene.

## Follow-ups

- Initial code review is required before workflow closure.

## Verification

### Round 1 (2026-07-24 10:56:37 +08:00)

- Tested head: `c0cfdf1c1b89ab81a136b3e38a77677813f1a8b2`
- Status: `pass`
- Checks: `python -m unittest tests.test_deploy_compose_contract tests.test_deploy_wrapper_contract tests.test_configuration_ownership tests.services.test_integration_settings tests.frontend.test_dashboard_settings_handoff tests.frontend.test_frontend_characterization tests.frontend.test_settings_workspace` — pass, 61 tests; `python -m unittest discover -s tests -v` — pass, 836 tests with one non-required Windows symlink-capability skip; `python -m compileall -q app.py backend` — pass; `node --check` for changed navigation/application/dashboard/settings modules — pass; Compose clean/override rendering and secret-canary contracts — pass in the focused suite; `openspec validate deliver-zero-edit-docker-startup-and-settings-handoff --type change --strict --no-interactive` — pass; `git diff --check` — pass.
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review

### Round 2 (2026-07-24 11:24:19 +08:00)

- Source: `contexts/work_logs/2026-07-24_feature-ZAC-77_deliver-zero-edit-docker-startup-and-settings-handoff_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `45c18151133027d97afb31b62bd5648523fd1784`
- Transitions: `REV-001 resolved; REV-002 resolved; REV-003 resolved`
- Open blockers: none.
- Follow-ups: none.
- Next action: `git add -- contexts/work_logs/2026-07-24_feature-ZAC-77_deliver-zero-edit-docker-startup-and-settings-handoff_codex-review-r1.md contexts/work_logs/2026-07-24_feature-ZAC-77_deliver-zero-edit-docker-startup-and-settings-handoff_codex-review-r2.md && git commit -m "docs(ZAC-77): record closure review"`; then `/dev-done`.
## Code Review

### Round 1 (2026-07-24 11:00:12 +08:00)

- Source: `contexts/work_logs/2026-07-24_feature-ZAC-77_deliver-zero-edit-docker-startup-and-settings-handoff_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `c0cfdf1c1b89ab81a136b3e38a77677813f1a8b2`
- Transitions: `REV-001 open; REV-002 open; REV-003 open`
- Open blockers:
  - `REV-001`: Compose configuration output exposes interpolated application secrets.
  - `REV-002`: A supported relative GDT host path is interpreted as an undefined named volume.
  - `REV-003`: dcm4chee legacy secrets are discarded before settings bootstrap.
- Follow-ups: None.
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-24_feature-ZAC-77_deliver-zero-edit-docker-startup-and-settings-handoff_codex-review-r1.md"`

### Round 2 (2026-07-24 11:14:48 +08:00)

- Tested head: `f71b240c176364aacf454cc491a928d882cd83bf`
- Status: `fail`
- Checks: focused deployment/wrapper/ownership/settings/frontend suite — fail, 64 tests with one ownership-contract failure; `python -m unittest discover -s tests -v` — fail, 840 tests with one ownership-contract failure and one non-required Windows symlink-capability skip; `python -m compileall -q app.py backend` and `node --check` for changed JavaScript — pass; clean Compose render with a `MEDPLUM_CLIENT_SECRET` canary absent from stdout/stderr — pass; `openspec validate deliver-zero-edit-docker-startup-and-settings-handoff --type change --strict --no-interactive` — pass; `git diff --check` — pass.
- Unresolved failures: `tests.test_configuration_ownership.ConfigurationOwnershipContractTests.test_every_declared_environment_and_compose_key_has_exactly_one_owner` does not recognize `DCM4CHEE_PASSWORD`, `DCM4CHEE_TOKEN`, and `DCM4CHEE_CLIENT_SECRET` after those keys moved from Compose interpolation to top-level Docker secret `environment` declarations.
- Next action: `/dev-fix "configuration ownership scanner does not recognize Docker secret environment keys"`

## Verification

### Round 3 (2026-07-24 11:22:04 +08:00)

- Tested head: `45c18151133027d97afb31b62bd5648523fd1784`
- Status: `pass`
- Checks: focused deployment/wrapper/ownership/settings/frontend suite — pass, 65 tests; `python -m unittest discover -s tests -v` — pass, 841 tests with one non-required Windows symlink-capability skip; `python -m compileall -q app.py backend` and `node --check` for changed JavaScript — pass; clean Compose render with a `MEDPLUM_CLIENT_SECRET` canary absent from stdout/stderr and relative GDT override rendered as a bind mount — pass; `openspec validate deliver-zero-edit-docker-startup-and-settings-handoff --type change --strict --no-interactive` — pass; `git diff --check` — pass.
- Unresolved failures: none.
- Next action: `/dev-review`
