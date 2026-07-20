---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-64_split-tests-by-feature-and-responsibility
base: main
reviewed_head: e22df47efde0b91383aeca642ac237ffa849fdbf
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P1 | open | The focused owner modules register methods from two remaining aggregate case libraries; assertion bodies were not moved to their owners. |
| REV-002 | P2 | open | The durable ownership map publishes count and compilation commands that reference paths deleted by this change. |

## New blocking findings

### [P1][REV-001] Focused suites alias methods from remaining catch-all case libraries

- Evidence: `tests/integration/_api_case_library.py:74` still defines the
  `HealthcareLabApiTests` class and contains the 125 `def test_*` assertion
  bodies (the first is at line 96); `tests/repositories/_store_case_library.py:35`
  likewise retains all 27 store assertion bodies. The new feature files such
  as `tests/integration/test_fhir_api.py:5-27` contain only a subclass and a
  `register_cases(...)` name list, while `tests/integration/_owners.py:4-7`
  copies `_case_*` attributes into that subclass. The case libraries rename
  the original methods at import time at `_api_case_library.py:4413-4421` and
  `_store_case_library.py:1003-1010` so the aggregate source remains executable.
- Impact: the physical assertion owner is still the broad aggregate module,
  not the focused responsibility suite. A contributor changing FHIR,
  dcm4chee, GDT, OIE, or repository behavior must continue searching the
  catch-all library, and the focused files do not expose the test setup and
  assertion implementation that their ownership names claim. This leaves the
  catch-all responsibility location in place behind an underscore filename
  and does not satisfy the requirement to move assertions by ownership before
  removing the old location.
- Classification: `fix-introduced`.
- Required resolution: move each retained test method body into its named
  feature/responsibility owner (or a physically focused module), leave only
  setup/fakes/factories in reusable support, remove both aggregate case
  libraries, and retain a one-to-one old-ID-to-owner inventory/check.

### [P2][REV-002] Published verification commands reference deleted paths

- Evidence: `docs/test-ownership-map.md:36-37` tells contributors to count
  methods in `tests\\integration\\test_app.py` and
  `tests\\repositories\\test_lab_store.py`; `docs/test-ownership-map.md:95`
  publishes a `py_compile` command with those same paths. Both paths are absent
  at the reviewed head (`Test-Path` returns `False` for each), so the published
  commands cannot be run from the resulting branch.
- Impact: the durable baseline and quality-gate instructions are not
  reproducible at the exact state they document, undermining the explicit
  focused-command and final-verification acceptance criteria.
- Classification: `fix-introduced`.
- Required resolution: update the commands to the actual focused/case-library
  paths as appropriate, or explicitly pin the historical count command to a
  checkout of the mainline baseline; the final compilation command must cover
  the files that exist after the catch-all cleanup.

## Follow-up findings

None.

## Verification and residual risk

The committed state passed the recorded local verification: full unittest
discovery 488/488, integration 125/125, repository discovery 95/95, frontend
discovery 77/77, architecture contract 49/49, focused Python compilation,
diff check, and strict OpenSpec validation. Live Medplum, dcm4chee, OIE, and
GDT runtime checks remain environment-specific and were not required by the
disposable-double acceptance gate. Passing tests do not close REV-001 because
the review concerns physical assertion ownership and discoverability.

## Next Action

`/dev-fix --review "openspec/changes/split-tests-by-feature-and-responsibility/review/2026-07-20_feature-ZAC-64_split-tests-by-feature-and-responsibility_codex-review-r1.md"`

Reason: blocking findings remain.
