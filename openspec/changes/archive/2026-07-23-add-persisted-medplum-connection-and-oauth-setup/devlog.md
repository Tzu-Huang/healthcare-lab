---
change: add-persisted-medplum-connection-and-oauth-setup
date: 2026-07-23
---

# Devlog

## Context

ZAC-73 adds a canonical, persisted Medplum connection profile and OAuth setup across backend configuration, runtime authentication, diagnostics, and the settings UI.

## Implementation

- Added persisted Medplum profile evolution and migration support.
- Added runtime OAuth authentication and connection diagnostics.
- Added API and settings UI support for configuring and testing the connection.
- Added health, smoke-test, and inventory projections for operational visibility.

## Decisions

- Use one connection timeout across runtime and diagnostics behavior.
- Save configuration before running a connection test.
- Keep access tokens in memory rather than persisting them.
- Expose a bounded inventory projection instead of raw remote resources.

## Validation Plan

- Run focused backend, frontend, architecture, and static checks.
- Validate the OpenSpec change.
- Run the complete Python unittest suite against one committed product state.

## Follow-ups

- Run the initial closure code review for the verified commit.

## Verification

### Round 1 (2026-07-23 14:12 +08:00)

- Tested head: `947ecb8bdba16c26389a8279f6de922427d685bf`
- Status: `pass`
- Checks:
  - Focused backend suites — pass (78 tests)
  - Frontend JavaScript syntax and focused frontend suites — pass (18 tests)
  - OpenSpec validation, Python compilation, architecture suites, and diff checks — pass (58 tests)
  - Full `python -m unittest` suite — pass (717 tests)
- Unresolved failures: none
- Next action: `/dev-review`

### Round 2 (2026-07-23 14:21 +08:00)

- Tested head: `619da5819bd099c42b435c2595bed945fff4dabf`
- Status: `fail`
- Checks:
  - `openspec validate add-persisted-medplum-connection-and-oauth-setup` — pass
  - JavaScript syntax, Python compilation, and `git diff --check` — pass
  - `python -m unittest` — fail (720 tests run; 4 failures)
  - Focused failure reproduction for order, cross-feature, and ownership contracts — fail (3 failures reproduced)
- Unresolved failures: order and cross-feature integration tests still expect upstream FHIR body details removed by `REV-001`; the ZAC-64 ownership inventory still references the renamed FHIR privacy regression test; one additional full-suite failure requires confirmation during the fix.
- Next action: `/dev-fix "Update remaining regression contracts for bounded Medplum failures and restore the full suite"`

### Round 3 (2026-07-23 14:30 +08:00)

- Tested head: `e17182172d047123f83d169ed7c4adda8f255fdd`
- Status: `pass`
- Checks:
  - `openspec validate add-persisted-medplum-connection-and-oauth-setup` — pass
  - JavaScript syntax, Python compilation, and `git diff --check` — pass
  - `python -m unittest` — pass (720 tests)
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-23 14:12 +08:00)

- Source: `contexts/work_logs/2026-07-23_feature-ZAC-73_add-persisted-medplum-connection-and-oauth-setup_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `947ecb8bdba16c26389a8279f6de922427d685bf`
- Transitions: none
- Open blockers: `REV-001`, `REV-002`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-23_feature-ZAC-73_add-persisted-medplum-connection-and-oauth-setup_codex-review-r1.md"`

### Round 2 (2026-07-23 14:31 +08:00)

- Source: `contexts/work_logs/2026-07-23_feature-ZAC-73_add-persisted-medplum-connection-and-oauth-setup_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `e17182172d047123f83d169ed7c4adda8f255fdd`
- Transitions: `REV-001 resolved; REV-002 resolved`
- Open blockers: none
- Follow-ups: none
- Next action: commit only the review and devlog workflow records, then run `/dev-done`
