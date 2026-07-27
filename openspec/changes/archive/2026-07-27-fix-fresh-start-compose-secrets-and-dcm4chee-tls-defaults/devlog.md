---
change: fix-fresh-start-compose-secrets-and-dcm4chee-tls-defaults
date: 2026-07-27
---

## Context

ZAC-79 fixes clean Docker startup without optional integration credentials,
aligns local dcm4chee TLS defaults, and adds an immutable release-image
readiness smoke contract.

## Implementation

- Replaced mandatory environment-backed Compose secret sources with optional
  file-backed sources and a tracked empty source.
- Aligned local dcm4chee TLS verification with disabled TLS.
- Added clean-start, bootstrap, Compose render, and release workflow contracts.
- Recorded an isolated disposable local-image startup.

## Decisions

- Missing optional credential files represent unconfigured Settings secrets.
- Stable image tags remain immutable and are not invented before publication.
- The local disposable run does not substitute for the pending release-image
  gate.

## Validation Plan

- Run the complete Python test discovery suite.
- Run compile, OpenSpec strict validation, and diff-hygiene checks.
- Preserve the immutable release publication and ZAC-78 fresh-install gate as
  required incomplete checks until a new image exists.

## Follow-ups

- Align configuration ownership with the new `*_FILE` deployment keys.
- Publish and select a verified immutable semantic-version image.
- Re-run the ZAC-78 fresh-install gate against that image.

## Verification

### Round 1 (2026-07-27 10:00 Asia/Taipei)

- Tested head: `e280131d3b797a8c3cfc46943aa81e005eabdc9f`
- Status: `fail`
- Checks: `python -m unittest discover -s tests` — fail (846 tests, 2 failures, 1 skip); `python -m py_compile backend/config.py backend/domain/integration_settings.py` — pass; `openspec validate fix-fresh-start-compose-secrets-and-dcm4chee-tls-defaults --strict` — pass; `git diff --check` — pass; immutable SemVer image publication/default selection — required skip; ZAC-78 release-image fresh-install gate — required skip
- Unresolved failures: configuration ownership still requires raw secret environment keys and does not recognize `MEDPLUM_CLIENT_SECRET_FILE`, `OPENEMR_DB_PASSWORD_FILE`, `DCM4CHEE_PASSWORD_FILE`, `DCM4CHEE_TOKEN_FILE`, or `DCM4CHEE_CLIENT_SECRET_FILE`; required release-image tasks 3.1, 3.2, and 4.3 remain incomplete
- Next action: `/dev-fix "configuration ownership contract does not recognize optional secret-file deployment keys"`

### Round 2 (2026-07-27 10:08 Asia/Taipei)

- Tested head: `cfa664b6ea1b85486bdd379b7b3f8e2314526cad`
- Status: `incomplete`
- Checks: `python -m unittest discover -s tests` — pass (847 tests, 1 skip); `python -m py_compile backend/config.py backend/configuration_ownership.py backend/domain/integration_settings.py tests/test_configuration_ownership.py` — pass; `openspec validate fix-fresh-start-compose-secrets-and-dcm4chee-tls-defaults --strict` — pass; `git diff --check` — pass; post-check product worktree — clean; immutable SemVer image publication/default selection — required skip; ZAC-78 release-image fresh-install gate — required skip
- Unresolved failures: no automated test failures; required tasks 3.1, 3.2, and 4.3 remain incomplete because no new immutable semantic-version image has been published and selected
- Next action: `/dev-fix "required immutable release image and ZAC-78 fresh-install gate remain incomplete"`

### Round 3 (2026-07-27 15:14 Asia/Taipei)

- Tested head: `7b896652b20f3fb4719fa96334ff2d05d1c9e747`
- Status: `pass`
- Checks: `python -m unittest discover -s tests` — pass (873 tests, 1 skip; repeated after an initial 124-second runner timeout); `python -m py_compile backend/config.py backend/configuration_ownership.py backend/domain/integration_settings.py tests/test_configuration_ownership.py tests/test_deploy_compose_contract.py tests/test_container_release_contract.py tests/test_container_workflow_contract.py tests/test_zac78_settings_release_verification.py` — pass; `openspec validate fix-fresh-start-compose-secrets-and-dcm4chee-tls-defaults --strict` — pass; `git diff --check` — pass; post-check product worktree — clean; immutable SemVer publication/default selection — pass (`ghcr.io/tzu-huang/healthcare-lab:1.1.1`, revision `54e60d0e69d25c256474d9d0a5c790b1d9b7599e`); ZAC-78 isolated release-image fresh-install gate — pass (`docs/settings-release-image-evidence-zac78-20260727.md`: healthy stack, readiness HTTP 200, Medplum `needs-setup`, dcm4chee `tlsEnabled: false` / `tlsVerify: false`)
- Unresolved failures: none
- Next action: `/dev-review`

### Round 4 (2026-07-27 15:42 Asia/Taipei)

- Tested head: `37f31500d869a13c7c957e56aa7aa8c0c7600c62`
- Status: `pass`
- Checks: `python -m unittest discover -s tests` — pass (873 tests, 1 non-required skip); `python -m py_compile backend/config.py backend/configuration_ownership.py backend/domain/integration_settings.py tests/test_container_release_contract.py tests/test_zac78_settings_release_verification.py` — pass; `openspec validate fix-fresh-start-compose-secrets-and-dcm4chee-tls-defaults --strict` — pass; `python -m zipfile -t` for both handbook Word editions — pass; handbook Markdown/DOCX TLS drift regression — pass within the full suite; `git diff --check` — pass; post-check product worktree — clean; all OpenSpec implementation and acceptance tasks — checked
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-27 15:20 Asia/Taipei)

- Source: `contexts/work_logs/2026-07-27_main_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `7b896652b20f3fb4719fa96334ff2d05d1c9e747`
- Transitions: `REV-001 open; REV-002 open; REV-003 open`
- Open blockers: `REV-001`, `REV-002`, `REV-003`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-27_main_codex-review-r1.md"`

### Round 2 (2026-07-27 15:45 Asia/Taipei)

- Source: `contexts/work_logs/2026-07-27_fix-ZAC-79_fix-fresh-start-compose-secrets-and-dcm4chee-tls-defaults_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `37f31500d869a13c7c957e56aa7aa8c0c7600c62`
- Transitions: `REV-001 resolved; REV-002 resolved; REV-003 resolved`
- Open blockers: none
- Follow-ups: none
- Next action: `/dev-done`
