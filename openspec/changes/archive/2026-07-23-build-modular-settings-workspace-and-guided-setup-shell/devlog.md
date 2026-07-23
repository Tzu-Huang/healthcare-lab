---
change: build-modular-settings-workspace-and-guided-setup-shell
date: 2026-07-23
---

# Development Log

## Context

ZAC-72 replaces the OIE-only Settings presentation with a modular integration
workspace, secret-safe readiness aggregation, guided setup, and bounded
diagnostic orchestration. OpenEMR is intentionally absent from every Settings
registration and extension contract.

## Implementation

- Added closed readiness domain, service, provider registry, API, and runtime
  composition for Medplum, OIE, optional integrations, and deployment.
- Added the accessible Settings shell, Overview readiness cards, guided resume,
  activation-impact labels, Advanced disclosures, and Run all checks.
- Extracted existing OIE Settings behavior into an integration-owned module
  while retaining its public APIs and lifecycle safeguards.
- Documented the frontend registration and readiness-provider contracts.

## Decisions

- Readiness GET operations use persisted intent and bounded local state without
  initiating network probes; explicit checks run through POST.
- GDT Bridge, dcm4chee, and AP / External Devices remain optional disabled
  placeholders until their owning tickets add persisted enablement.
- OpenEMR receives no Settings navigation, readiness provider, diagnostic
  registration, guided setup step, or extension point.

## Validation Plan

- Run backend, integration, and frontend responsibility suites against one
  committed HEAD.
- Run Python compilation, JavaScript syntax checks, architecture contracts,
  diff hygiene, and strict OpenSpec validation.
- Require a clean worktree before and after automated checks.

## Follow-ups

- Later integration tickets provide their own section, readiness provider, and
  bounded diagnostics through the documented contracts.

## Verification

### Round 1 (2026-07-23 13:25 Asia/Taipei)

- Tested head: `2dfd36232405fb6f518f5eb106ac37c7aea06194`
- Status: `pass`
- Checks: PASS — backend/API/domain/service/repository/runtime/template/support/tools and top-level contract suites (`496/496`); PASS — integration suite (`138/138`); PASS — frontend and controlled browser suite (`92/92`); PASS — Python compilation; PASS — JavaScript syntax for all changed Settings modules; PASS — `git diff --check`; PASS — strict OpenSpec validation.
- Unresolved failures: none
- Next action: `/dev-review`

### Round 2 (2026-07-23 13:28 Asia/Taipei)

- Tested head: `28a4445856588bcaa37c982c8d62faa6fed69f05`
- Status: `fail`
- Checks: FAIL — `python -m unittest discover -s tests -t .` (`701` tests, `700` passed, `1` failed); PASS — `python -m compileall -q app.py backend tests`; PASS — `node --check` for every file under `frontend/static/js`; PASS — `git diff --check`; PASS — `openspec validate build-modular-settings-workspace-and-guided-setup-shell --strict`.
- Unresolved failures: `tests.test_zac64_ownership.Zac64OwnershipContractTests.test_owner_inventory_is_complete_and_aggregate_libraries_are_removed` rejects the unregistered `test_fresh_settings_readiness_requires_operator_setup` ownership entry.
- Next action: `/dev-fix "register the fresh settings readiness integration test in the ZAC-64 ownership inventory"`

### Round 3 (2026-07-23 13:33 Asia/Taipei)

- Tested head: `ba0f9ba74a9e160baa1547afac6b04353c68256a`
- Status: `pass`
- Checks: PASS — `python -m unittest discover -s tests -t .` (`701/701`); PASS — `python -m compileall -q app.py backend tests`; PASS — `node --check` for every file under `frontend/static/js`; PASS — `git diff --check`; PASS — `openspec validate build-modular-settings-workspace-and-guided-setup-shell --strict`.
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-23 13:38 Asia/Taipei)

- Source: `contexts/work_logs/2026-07-23_feature-ZAC-72_build-modular-settings-workspace-and-guided-setup-shell_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `2dfd36232405fb6f518f5eb106ac37c7aea06194`
- Transitions: `REV-001 open; REV-002 open; REV-003 open`
- Open blockers: `REV-001, REV-002, REV-003`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-23_feature-ZAC-72_build-modular-settings-workspace-and-guided-setup-shell_codex-review-r1.md"`

### Round 2 (2026-07-23 13:36 Asia/Taipei)

- Source: `contexts/work_logs/2026-07-23_feature-ZAC-72_build-modular-settings-workspace-and-guided-setup-shell_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `ba0f9ba74a9e160baa1547afac6b04353c68256a`
- Transitions: `REV-001 resolved; REV-002 resolved; REV-003 resolved`
- Open blockers: `none`
- Follow-ups: `none`
- Next action: commit only the review workflow records, then run `/dev-done`
