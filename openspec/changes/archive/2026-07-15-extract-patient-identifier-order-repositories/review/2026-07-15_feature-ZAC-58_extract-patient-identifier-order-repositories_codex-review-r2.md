---
reviewer: codex
mode: closure
round: 2
branch: feature/ZAC-58_extract-patient-identifier-order-repositories
base: main
reviewed_head: c145b182edadf97f0b014ff41d17e9f7e8f0fcbe
previous_review: openspec/changes/extract-patient-identifier-order-repositories/review/2026-07-15_feature-ZAC-58_extract-patient-identifier-order-repositories_codex-review-r1.md
previous_reviewed_head: be41f8c1f31e91b99ab37189edf15035e7da90b5
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P1 | resolved | `backend/repositories/enrichment.py:51-60` tracks snapshot selection independently of snapshot truthiness, and `tests/repositories/test_patients_orders.py:30` covers a newer empty snapshot following an older non-empty snapshot. The targeted regression passes. |
| REV-002 | P2 | resolved | `backend/domain/patient.py:10` and `backend/domain/order.py:10` now use the persistence-neutral `IndexedRecord` protocol from `backend/domain/records.py`; `tests/test_architecture_contract.py:1194` prevents Flask/SQLite imports across the patient/order domain and template modules. The targeted architecture test passes. |
| REV-003 | P2 | still-open | The consumed method names are now enumerated and `__getattr__` is gone, but every operation in both coordination protocols and both adapters is still typed as `*args: Any, **kwargs: Any -> Any` (`backend/services/patient_workflow.py:40-80`, `backend/services/order_workflow.py:97-151`, `backend/services/coordination.py:17-168`). The contract test checks only method-name equality and even constructs both adapters with `object()` (`tests/services/test_patient_order_ports.py:44-66`), so it cannot verify delegate signatures or result types. |

### [P2][REV-003] Coordination contracts still erase every operation signature

Files: `backend/services/patient_workflow.py:40`,
`backend/services/order_workflow.py:97`, `backend/services/coordination.py:17`,
`tests/services/test_patient_order_ports.py:44`

Impact: the explicit method inventory prevents unrelated attribute lookup, but
the declared boundary still cannot statically detect a wrong argument list,
keyword, or return type. A facade with incompatible coordination methods can
therefore appear valid at the annotated boundary until a workflow invokes it.
This leaves the explicit, typed coordination-port acceptance requirement only
partially implemented.

Evidence: all 49 declared protocol methods and all 49 adapter methods accept
arbitrary positional and keyword arguments and return `Any`. The runtime
protocol assertion checks only attribute presence; Python runtime protocols do
not compare signatures. The added test passes `object()` as each facade and
does not invoke or inspect a representative typed delegate signature.

Classification: fix-introduced explicit-acceptance violation; continuation of
REV-003, not a new finding.

Required resolution: retain the explicit method inventory but give each
consumed operation a concrete parameter and return contract matching its real
owner, and mirror those contracts on the adapters (or compose narrower typed
FHIR/dcm4chee owners directly). Strengthen the contract coverage so a generic
`*args/**kwargs -> Any` port or adapter cannot pass; an architecture signature
assertion or an existing static type check is sufficient.

## New blocking findings

None.

## Follow-up findings

None.

## Verification and residual risk

- Closure-targeted verification: pass, 6 tests covering the REV-001 regression,
  REV-002 architecture boundary, and coordination adapter/port tests.
- The immediately preceding `/dev-test` verification at this same reviewed head
  reported 178 focused tests and 278 full-regression tests passing, plus Python
  compilation, frontend syntax, strict OpenSpec validation, and scope/data-safety
  audit passing with no required skips.
- Residual risk: runtime behavior is covered, but no current check proves the
  coordination operation signatures because the protocols, adapters, and
  contract tests all erase them with `Any`.

## Next Action

`/dev-fix --review "openspec/changes/extract-patient-identifier-order-repositories/review/2026-07-15_feature-ZAC-58_extract-patient-identifier-order-repositories_codex-review-r2.md"`

Reason: REV-003 remains blocking because the coordination boundary enumerates
operations but still does not provide verifiable typed signatures.
