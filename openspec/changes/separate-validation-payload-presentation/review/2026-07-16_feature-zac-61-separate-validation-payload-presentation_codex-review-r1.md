---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-61_separate-validation-payload-presentation
base: main
reviewed_head: 7b881a2066d99db91dd19dd84d71669cead63084
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P2 | open | Repository protocol-builder enforcement is name-based and admits equivalent renamed implementations. |
| REV-002 | P2 | open | Two environment-specific OIE channel exports were added outside the approved ZAC-61 change scope. |

## New blocking findings

### [P2][REV-001] Repository builder enforcement can be bypassed by renaming

At `tests/test_architecture_contract.py:1102-1134`, validation is detected only
when a function name contains `validate`, builders only when names begin with
`build_` or `serialize_`, and presentation only when names contain `project`.
A repository-local `render_hl7_payload`, `make_message`, or `row_to_public_json`
implementation therefore passes while owning the exact responsibilities that
task 1.5 and the modified architecture requirement say repositories must not
implement. There is also no negative fixture proving forbidden implementations
are rejected.

Impact: the new architecture quality gate does not enforce the explicit
acceptance boundary and can regress silently. Classification: initial-review
blocking P2 because it violates an explicit requirement.

Required resolution: implement responsibility detection that is not solely
dependent on the prohibited function choosing an expected name, and add
negative fixture tests covering at least renamed validation, protocol-builder,
and row-presentation implementations while continuing to permit SQL,
transactions, the two infrastructure validators, and thin mapper delegates.

### [P2][REV-002] Environment-specific OIE exports are outside ZAC-61 scope

Commit `7b881a2` adds `docs/AP_RESULT_TO_LAB.xml` and
`docs/Dashboard_to_OIE_to_AP.xml` (864 lines) after apply completed. The latter
contains an environment-specific destination at
`docs/Dashboard_to_OIE_to_AP.xml:181-182` (`192.168.30.15:6671`) and both retain
Mirth export metadata at lines 421-429. The approved design explicitly limits
ZAC-61 to a behavior-preserving ownership refactor, excludes external
integration changes, and requires no unrelated work.

Impact: the branch now carries deployment/integration configuration unrelated
to the reviewed acceptance scope, obscuring the release boundary. Classification:
initial-review blocking P2 because it violates the explicit scope constraint.

Required resolution: remove these exports from the ZAC-61 branch (preserve them
in a separate appropriately scoped change if needed), then rerun verification
against the resulting committed head.

## Follow-up findings

None.

## Verification and residual risk

- Reviewed `main...7b881a2066d99db91dd19dd84d71669cead63084` against the OpenSpec proposal,
  design, modified requirement, tasks, changed production modules, tests, and
  compatibility/architecture contracts.
- Verification Round 1 passed 359 tests, Python compilation, XML parsing and
  marker scan, diff checking, and strict OpenSpec validation.
- Automated test success does not close REV-001 because the test itself lacks
  adversarial negative cases, and does not close REV-002 because it is a scope
  finding rather than malformed XML.

## Next Action

`/dev-fix --review "openspec/changes/separate-validation-payload-presentation/review/2026-07-16_feature-zac-61-separate-validation-payload-presentation_codex-review-r1.md"`

Reason: blocking findings REV-001 and REV-002 remain.
