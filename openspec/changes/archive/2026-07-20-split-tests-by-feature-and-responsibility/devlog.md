---
change: split-tests-by-feature-and-responsibility
date: 2026-07-20
---

# ZAC-64 Development Log

## Context

The mainline baseline at `ecc21ec1bd4a7664206fd234d27149a61746b688` collected
484 tests while 125 integration methods and 27 mixed store methods remained in
two broad responsibility locations. The ZAC-63 record of 478 was a prior
discovery snapshot rather than the final baseline.

## Implementation

- Added `docs/test-ownership-map.md` with the pinned baseline, counting command,
  feature ownership matrix, focused commands, and ZAC-65 compatibility handoff.
- Added `tests/support/` for disposable Flask/store setup and deterministic HTTP,
  database, Docker, and external-service doubles, with four support contracts.
- Renamed the broad files to non-discoverable case libraries and registered every
  legacy method in focused application-shell, feature API, cross-feature,
  repository, and compatibility suites.
- Preserved the ZAC-63 frontend test locations and did not change production code.

## Decisions

- Assertions stay in owner suites; registration libraries retain only the source
  method bodies needed for an auditable incremental migration.
- Compatibility coverage remains explicit in `test_compatibility.py` for the
  ZAC-65 `DemoStore` cleanup boundary.
- The final collection increase is intentional and limited to support-contract
  characterization; the original 125 + 27 methods remain covered one-for-one.

## Validation Plan

Run the focused integration, repository, support, and frontend commands, then
the full unittest discovery, architecture contract, Python compilation, diff
check, and strict OpenSpec validation.

## Follow-ups

- `/dev-test` should verify the committed state independently before closure
  review.
- `/dev-review` should inspect the ownership map and the retained compatibility
  boundary before `/dev-done`.

## Verification

### Round 1 (2026-07-20 14:06 Asia/Taipei)

- Tested head: `3698ff72e90acc9182a7cc585cd7e783d46016fe`
- Status: `pass`
- Checks: `python -m unittest discover -s tests -t .` (488/488); integration discovery (125/125); repository discovery (95/95); support contracts (4/4); frontend discovery (77/77); architecture contract (49/49); `python -m py_compile` (pass); `git diff --check` (pass); `openspec validate split-tests-by-feature-and-responsibility --strict` (valid).
- Unresolved failures: none.
- Next action: `/dev-test ZAC-64`

### Round 2 (2026-07-20 14:14 Asia/Taipei)

- Tested head: `e22df47efde0b91383aeca642ac237ffa849fdbf`
- Status: `pass`
- Checks: clean worktree before and after verification (pass); `python -m unittest tests.support.test_contracts` (4/4); `python -m unittest discover -s tests/integration -t .` (125/125); `python -m unittest discover -s tests/repositories -t .` (95/95); `python -m unittest discover -s tests/frontend -t .` (77/77); `python -m unittest tests.test_architecture_contract` (49/49); `python -m unittest discover -s tests -t .` (488/488); `python -m py_compile` focused product/test paths (pass); `git diff --check HEAD^ HEAD` (pass); `openspec validate split-tests-by-feature-and-responsibility --strict` (valid).
- Skipped: configured build quality command (none configured); live Medplum/dcm4chee/OIE/GDT external-runtime checks (environment-specific and not required by the local disposable-double acceptance gate).
- Unresolved failures: none.
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-20)

- Source: `openspec/changes/split-tests-by-feature-and-responsibility/review/2026-07-20_feature-ZAC-64_split-tests-by-feature-and-responsibility_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `e22df47efde0b91383aeca642ac237ffa849fdbf`
- Transitions: `REV-001 still-open; REV-002 still-open`
- Open blockers: `REV-001, REV-002`
- Follow-ups: none
- Next action: `/dev-fix --review "openspec/changes/split-tests-by-feature-and-responsibility/review/2026-07-20_feature-ZAC-64_split-tests-by-feature-and-responsibility_codex-review-r1.md"`

## Verification (continued)

### Round 3 (2026-07-20 14:57 Asia/Taipei)

- Tested head: `cdf783d0347308743d44ab76b7af016f5bbc6c11`
- Status: `pass`
- Checks: `python -m unittest tests.support.test_contracts` (4/4); `python -m unittest discover -s tests/integration -t .` (125/125); `python -m unittest discover -s tests/repositories -t .` (95/95); `python -m unittest discover -s tests/frontend -t .` (77/77); `python -m unittest tests.test_architecture_contract` (49/49); `python -m unittest discover -s tests -t .` (489/489); documented focused `python -m py_compile` paths (pass); `git diff --check` and `git diff --check ecc21ec1bd4a7664206fd234d27149a61746b688 HEAD` (pass); `openspec validate split-tests-by-feature-and-responsibility --strict` (valid).
- Worktree attribution: product code, tests, specs, and runtime configuration remained committed at the tested head; only the existing devlog and review workflow records were dirty before and after checks.
- Skipped: configured build quality command (none configured); live Medplum/dcm4chee/OIE/GDT external-runtime checks (environment-specific and not required by the local disposable-double acceptance gate).
- Unresolved failures: none.
- Next action: `/dev-review`

## Code Review (continued)

### Round 2 (2026-07-20 15:03 Asia/Taipei)

- Source: `openspec/changes/split-tests-by-feature-and-responsibility/review/2026-07-20_feature-ZAC-64_split-tests-by-feature-and-responsibility_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `cdf783d0347308743d44ab76b7af016f5bbc6c11`
- Transitions: `REV-001 resolved; REV-002 resolved`
- Open blockers: `none`
- Follow-ups: `none`
- Next action: commit only the review/devlog workflow records, then `/dev-done`
