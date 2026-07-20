---
change: modularize-frontend-by-feature
date: 2026-07-19
---

## Context

ZAC-63 modularizes the no-build Flask frontend by shared infrastructure and feature ownership while preserving existing behavior and coordinating assertion ownership with ZAC-64.

## Implementation

- Established native module infrastructure and shared frontend utilities.
- Extracted Settings foundations plus OIE, Dashboard, GDT, and FHIR/Medplum feature modules.
- Retained compatibility entrypoints and reduced reviewed legacy architecture baselines as ownership moved.

## Decisions

- Keep browser-native ES modules without a frontend framework or build step.
- Preserve feature-local inventory, preview, expansion, and request state.
- Complete production extraction and focused assertion ownership in the same increment.

## Validation Plan

- Run the complete Python regression suite.
- Check syntax for every JavaScript module.
- Run strict OpenSpec validation.
- Complete required controlled browser smoke coverage and final assertion-ownership audit before closure.

## Follow-ups

- Finish the remaining Patient, Order, dcm4chee, CSS, template, interaction, cleanup, and documentation tasks.

## Verification

### Round 1 (2026-07-19)

- Tested head: `7cfefff359fbca33ecf0bbe642eba9f507ce7ede`
- Status: `incomplete`
- Checks: `python -m unittest discover -s tests -t .` — pass, 434 tests; recursive `node --check` for `frontend/static/**/*.js` — pass; `openspec validate modularize-frontend-by-feature --strict` — pass; post-check product worktree — clean.
- Unresolved failures: required controlled browser smoke coverage, final test-collection/assertion-ownership audit, and final quality-gate acceptance remain incomplete in `tasks.md`.
- Next action: `/dev-fix "complete required browser smoke coverage and final verification acceptance"`

### Round 2 (2026-07-19)

- Tested head: `fec8c1b5b45cb26cf736c9091ab75c0930edccae`
- Status: `incomplete`
- Checks: `python -m unittest discover -s tests -t .` — pass, 436 tests including controlled headless Chromium OIE interactions; recursive `node --check` for `frontend/static/**/*.js` — pass; `openspec validate modularize-frontend-by-feature --strict` — pass; post-check product worktree — clean.
- Unresolved failures: 19 required implementation and final-acceptance tasks remain incomplete, including Patient, Order, dcm4chee, CSS/template ownership, remaining browser coverage, assertion audit, cleanup, and final quality gate.
- Next action: `/dev-fix "complete remaining required implementation and final-acceptance tasks"`

### Round 3 (2026-07-20 10:18:22 +08:00)

- Tested head: `35a7ceef215dffe0a8d8b76382989df19abbb8bf`
- Status: `incomplete`
- Checks: `python -m unittest discover -s tests -t .` — pass, 461 tests; recursive `node --check` for `frontend/static/**/*.js` — pass; `openspec validate modularize-frontend-by-feature --strict` — pass; post-check product worktree — clean.
- Unresolved failures: 16 required implementation and final-acceptance tasks remain incomplete, including cross-view compatibility, dcm4chee extraction, CSS/template ownership, remaining controlled browser smoke coverage, assertion audit, compatibility cleanup, documentation, and the final quality gate.
- Next action: `/dev-fix "complete remaining ZAC-63 implementation and final-acceptance tasks"`

### Round 4 (2026-07-20 10:22:59 +08:00)

- Tested head: `bf41229541c6225fb41c12dfb93255c216c4d7b8`
- Status: `incomplete`
- Checks: `python -m unittest discover -s tests -t .` — pass, 463 tests including cross-view coordination contracts; recursive `node --check` for `frontend/static/**/*.js` — pass; `openspec validate modularize-frontend-by-feature --strict` — pass; post-check product worktree — clean.
- Unresolved failures: 15 required implementation and final-acceptance tasks remain incomplete, including dcm4chee extraction, shared-component audit, CSS/template ownership, controlled browser smoke coverage, assertion audit, compatibility cleanup, documentation, and the final quality gate.
- Next action: `/dev-fix "complete remaining 15 ZAC-63 implementation and final-acceptance tasks"`

### Round 5 (2026-07-20 11:57:40 +08:00)

- Tested head: `79fba5064af0fc99be0902e887204cf9f9f966f5`
- Status: `pass`
- Checks: `python -m unittest discover -s tests -t .` — pass, 478 tests; `python -m unittest discover -s tests/frontend -t .` — pass, 71 focused frontend/browser tests; `python -m unittest tests.integration.test_app` — pass, 125 Flask integration tests; `python -m unittest tests.test_architecture_contract` — pass, 49 architecture tests; recursive `node --check` — pass, 31 JavaScript files; `openspec validate modularize-frontend-by-feature --strict` — pass; `git diff --check` and post-check product worktree — pass/clean.
- Manual boundary: live Medplum authentication, dcm4chee DICOMweb/MWL, OIE MLLP sockets, and GDT watcher filesystem interoperability remain optional deployment-specific verification documented in `docs/frontend-module-map.md`; no required acceptance check was skipped.
- Unresolved failures: none.
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-20 12:01:03 +08:00)

- Source: `openspec/changes/modularize-frontend-by-feature/review/2026-07-20_feature-ZAC-63_modularize-frontend-by-feature_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `79fba5064af0fc99be0902e887204cf9f9f966f5`
- Transitions: `REV-001 open; REV-002 open; REV-003 open; REV-004 open`
- Open blockers: `REV-001`, `REV-002`, `REV-003`, `REV-004`
- Follow-ups: keep shrinking feature-specific Order/dcm4chee/GDT behavior from `views/application.js` rather than adding new coordinator branches.
- Next action: `/dev-fix --review "openspec/changes/modularize-frontend-by-feature/review/2026-07-20_feature-ZAC-63_modularize-frontend-by-feature_codex-review-r1.md"`

### Round 6 (2026-07-20 13:02:00 +08:00)

- Tested head: `cdee0324bf1094cfdd5edf8f8044153938c77957`
- Status: `fail`
- Checks: `python -m unittest discover -s tests -t .` — fail (481 passed, 3 failures in 484 tests); `python -m unittest discover -s tests/frontend -t .` — fail (76 passed, 1 failure in 77 tests); `python -m unittest tests.integration.test_app` — fail (123 passed, 2 failures in 125 tests); `python -m unittest tests.test_architecture_contract` — pass (49 tests); `python -m compileall -q backend tests` — pass; recursive `node --check` for `frontend/static/**/*.js` — pass (31 files); `openspec validate modularize-frontend-by-feature --strict` — pass; `git diff --check` — pass; post-check product state remained clean and only workflow records were dirty.
- Unresolved failures: update the FHIR bootstrap characterization for the idempotent initializer seam; update the Flask integration stylesheet helper to aggregate all feature-owned CSS files so feature selectors remain covered.
- Next action: `/dev-fix "fix the FHIR bootstrap characterization and Flask integration CSS aggregation failures"`

### Round 7 (2026-07-20 13:13:40 +08:00)

- Tested head: `48efb67d87c4cdf8953bae5d47b3afeebf45205c`
- Status: `pass`
- Checks: `python -m unittest discover -s tests -t .` — pass (484 tests); `python -m unittest discover -s tests/frontend -t .` — pass (77 tests); `python -m unittest tests.integration.test_app` — pass (125 tests); `python -m unittest tests.test_architecture_contract` — pass (49 tests); `python -m compileall -q backend tests` — pass; recursive `node --check` for `frontend/static/**/*.js` — pass (31 files); `openspec validate modularize-frontend-by-feature --strict` — pass; `git diff --check` — pass; post-check product state remained clean and only workflow records were dirty.
- Unresolved failures: none. Live Medplum authentication, dcm4chee DICOMweb/MWL, OIE MLLP sockets, and GDT watcher filesystem interoperability remain optional deployment-specific checks documented in `docs/frontend-module-map.md`; no required acceptance check was skipped.
- Next action: `/dev-review`

## Code Review

### Round 2 (2026-07-20 13:16:00 +08:00)

- Source: `openspec/changes/modularize-frontend-by-feature/review/2026-07-20_feature-ZAC-63_modularize-frontend-by-feature_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `48efb67d87c4cdf8953bae5d47b3afeebf45205c`
- Transitions: `REV-001 resolved; REV-002 resolved; REV-003 resolved; REV-004 resolved`
- Open blockers: `none`
- Follow-ups: retain the application coordinator as a named module while continuing to shrink feature-specific coordination in later work.
- Next action: commit only the review/devlog workflow records, then run `/dev-done`
