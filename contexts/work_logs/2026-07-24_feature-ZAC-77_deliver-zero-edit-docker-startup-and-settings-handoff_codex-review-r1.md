---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-77_deliver-zero-edit-docker-startup-and-settings-handoff
base: main
reviewed_head: c0cfdf1c1b89ab81a136b3e38a77677813f1a8b2
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Summary |
| --- | --- | --- | --- |
| REV-001 | P1 | open | Compose configuration output exposes interpolated application secrets. |
| REV-002 | P1 | open | A supported relative GDT host path is interpreted as an undefined named volume. |
| REV-003 | P1 | open | dcm4chee legacy secrets are discarded before settings bootstrap. |

## New blocking findings

### [P1][REV-001] Compose configuration output exposes application secrets

- Evidence: `deploy/docker-compose.yml:30` maps `MEDPLUM_CLIENT_SECRET` directly into the service environment. Running `docker compose --env-file .env.example -f deploy/docker-compose.yml config` with `MEDPLUM_CLIENT_SECRET=review-secret-canary-ZAC-77` prints `MEDPLUM_CLIENT_SECRET: review-secret-canary-ZAC-77`.
- Impact: The proposal's secret-safe handoff contract is violated by a routine diagnostic command, allowing credentials to leak into terminals, logs, CI output, or support bundles.
- Classification: initial-review blocking finding.
- Required resolution: avoid placing legacy secret values in a Compose-rendered service environment, using a bootstrap mechanism whose rendered configuration does not contain secret material. Extend the contract test to assert the canary is absent from both stdout and stderr and from any generated diagnostic evidence.

### [P1][REV-002] Relative GDT host-path overrides do not produce a valid bind mount

- Evidence: `deploy/lab.ps1:75-100` accepts a relative `GDT_BRIDGE_HOST_PATH` and resolves/creates it from the repository root, while `deploy/docker-compose.yml:98` passes the original value through short volume syntax. With `GDT_BRIDGE_HOST_PATH=exchange/clinic-a`, `docker compose --env-file .env.example -f deploy/docker-compose.yml config` fails with `service "lab-app" refers to undefined volume exchange/clinic-a: invalid compose project`.
- Impact: An override explicitly accepted by the wrapper and covered as supported cannot start the stack. The wrapper and Compose also disagree about the base directory for relative paths.
- Classification: initial-review blocking finding.
- Required resolution: pass the same normalized absolute directory that the wrapper validates and creates to Compose, or explicitly reject relative paths. Add an integration test that exercises the wrapper-derived value through actual Compose configuration.

### [P1][REV-003] dcm4chee legacy secret values never reach settings bootstrap

- Evidence: `deploy/docker-compose.yml:88-90` forwards `DCM4CHEE_PASSWORD`, `DCM4CHEE_TOKEN`, and `DCM4CHEE_CLIENT_SECRET`; `backend/services/integration_settings.py:343-345` expects those configuration keys. However, `backend/config.py:384` and the surrounding dcm4chee configuration block load only non-secret fields and omit all three secret keys.
- Impact: Existing installations lose their dcm4chee credentials during migration, so the promised zero-edit legacy-to-settings handoff is incomplete and authenticated integrations can fail after upgrade.
- Classification: initial-review blocking finding.
- Required resolution: load these secret values into the internal application configuration without exposing them in public projections, and add end-to-end tests covering environment input through persisted secret bootstrap while retaining boolean-only public secret indicators.

## Follow-up findings

None.

## Verification and residual risk

The pinned commit previously passed the automated verification round (836 tests passed, with one non-required Windows symlink test skipped), focused tests, syntax checks, OpenSpec validation, and diff checks. This review additionally reproduced the Compose secret disclosure and relative-volume failure directly. The current tests do not cover the affected security and wrapper-to-Compose integration paths, and the dcm4chee secret configuration chain is incomplete in source.

No product code was changed during this review.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-24_feature-ZAC-77_deliver-zero-edit-docker-startup-and-settings-handoff_codex-review-r1.md"`

Reason: three P1 blocking findings remain.
