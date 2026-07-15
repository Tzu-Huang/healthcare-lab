---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-58_extract-patient-identifier-order-repositories
base: main
reviewed_head: be41f8c1f31e91b99ab37189edf15035e7da90b5
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

None.

## New blocking findings

### [P1][REV-001] An empty latest DICOM refresh republishes stale results

File: `backend/repositories/enrichment.py:53`

Impact: after a completed refresh legitimately finds no DICOM results, Patient
projections can display results from an older refresh. That changes observable
projection semantics and can present stale clinical evidence as current.

Evidence: refresh runs are read newest-first, but lines 57-59 use the truthiness
of the accumulated result list to decide whether a snapshot was selected. An
empty newest snapshot therefore leaves the condition true and allows an older
non-empty snapshot to overwrite it. A disposable-database reproduction with an
older `[{'marker': 'old'}]` snapshot and a newer `[]` snapshot returned the old
item from `get_patient_record()`. The pre-extraction implementation tracked key
presence instead, so an empty newest snapshot remained authoritative.

Classification: fix-introduced compatibility regression.

Required resolution: record that the first completed refresh row for each
Patient has been selected independently of snapshot contents, preserve an empty
latest snapshot, and add a regression test covering newer-empty/older-nonempty
refresh history.

### [P2][REV-002] Domain modules retain a SQLite dependency

Files: `backend/domain/patient.py:7`, `backend/domain/order.py:7`

Impact: both new domain modules import `sqlite3.Row`, contrary to the explicit
requirement that Patient and Order domain rules remain independent of SQLite.
This couples otherwise pure projection rules to the persistence technology and
leaves the architecture boundary incomplete.

Evidence: each module imports `Row` from `sqlite3` solely for projection type
annotations. The OpenSpec requirement states that Patient and Order rules must
reside in framework-independent domain modules, and the design further requires
domain/templates to remain independent of Flask and SQLite.

Classification: fix-introduced explicit-acceptance violation.

Required resolution: replace the SQLite type dependency with a persistence-
neutral row protocol/type (or an appropriate generic indexed-record type), and
add an architecture assertion preventing Flask/SQLite imports in these domain
and template modules.

### [P2][REV-003] Declared coordination ports do not describe their consumers

Files: `backend/services/patient_workflow.py:38`,
`backend/services/order_workflow.py:95`, `backend/services/coordination.py:8`

Impact: the supposedly explicit protocol-coordination boundaries are not
structurally truthful. The services and their typed helpers call many operations
absent from the declared protocols, while the runtime adapters hide the mismatch
behind `Any` and string-based `__getattr__`. Static checking cannot verify the
narrow boundary, and future missing-method errors remain runtime-only.

Evidence: `PatientCoordinationPort` declares only three methods, but the service
itself calls `create_dcm4chee_e2e_demo_fixture` and its coordination helpers call
the DICOM refresh/sync operations beginning at line 141. `OrderCoordinationPort`
declares four methods, while the service calls FHIR workflow, attempt, evidence,
and simulated-return operations beginning at line 146 and the MWL helpers call
the remaining mapping/attempt operations. The adapters expose these only through
an allowlisted `__getattr__` returning `Any`.

Classification: fix-introduced explicit-acceptance violation.

Required resolution: define complete, cohesive FHIR/dcm4chee coordination ports
for the actual consumers and implement explicit typed adapter methods (or compose
the owning collaborators directly). Add contract tests proving the adapters
satisfy those declared ports without a general `Any` fallback.

## Follow-up findings

None.

## Verification and residual risk

- Full automated suite: pass, 275 tests.
- Focused domain/template/repository/service/architecture/integration suite:
  pass, 175 tests.
- Python compilation, frontend syntax, architecture contracts, strict OpenSpec
  validation, and scope/data-safety audit: pass.
- Disposable review reproduction for REV-001: failed as described; the latest
  empty snapshot returned the older non-empty snapshot.
- Residual risk: current tests do not cover an authoritative empty DICOM refresh
  following a non-empty refresh, and no static type check currently exposes the
  incomplete coordination protocols.

## Next Action

`/dev-fix --review "openspec/changes/extract-patient-identifier-order-repositories/review/2026-07-15_feature-ZAC-58_extract-patient-identifier-order-repositories_codex-review-r1.md"`

Reason: blocking findings REV-001, REV-002, and REV-003 remain.
