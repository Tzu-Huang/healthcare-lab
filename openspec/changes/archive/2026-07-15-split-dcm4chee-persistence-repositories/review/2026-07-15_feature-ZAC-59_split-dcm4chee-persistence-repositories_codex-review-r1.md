---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-59_split-dcm4chee-persistence-repositories
base: main
reviewed_head: 5f3db4d480c1780fcac025763429993f3f7cbb8c
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

None.

## New blocking findings

### [P2][REV-001] Keep MWL protocol construction and parsing outside the repository

`Dcm4cheeMwlRepository` accepts a payload builder in
`backend/repositories/dcm4chee_mwl.py:251` and invokes it from
`create_dcm4chee_mwl_attempt` at `backend/repositories/dcm4chee_mwl.py:488` when
the caller does not supply a payload. The same repository module implements
DICOM tag traversal helpers at `backend/repositories/dcm4chee_mwl.py:119` and
uses them during historical backfill at `backend/repositories/dcm4chee_mwl.py:166`.
`backend/lab_store.py:508` wires the template builder into this persistence
owner.

Impact: protocol policy and DICOM payload interpretation remain coupled to
persistence. This violates the explicit requirement that repository modules
contain persistence and row projection only and do not construct MWL payloads
or parse protocol bodies.

Classification: introduced P2 that blocks because it violates an explicit
OpenSpec acceptance criterion.

Required resolution: have callers/services supply the constructed payload and
normalized identifiers. Move historical payload interpretation to a pure
domain/template collaborator (or supply a precomputed projection) so the
repository consumes persistence-ready values without constructing or parsing
DICOM content.

### [P2][REV-002] Make declared capability ports match the workflows they execute

The new narrow protocols declare only partial surfaces. For example,
`DcmPatientSyncCapability` at `backend/services/patient_workflow.py:42` declares
only payload construction and lookup, but `PatientWorkflowService` passes it to
`sync_patient_to_dcm4chee` at `backend/services/patient_workflow.py:156`, whose
path also calls upsert/create/update operations beginning at
`backend/services/patient_workflow.py:208`. A minimal object satisfying the
declared protocol therefore raises `AttributeError`. The same mismatch exists
for result refresh and order sync/verify. In addition,
`DcmEvidenceCapability` at `backend/services/order_workflow.py:165` contains
duplicated and unrelated FHIR/MWL methods.

`backend/app_factory.py:410` and `backend/app_factory.py:428` avoid immediate
production failures only by passing the same broad patient/order coordinator
instance into every named capability slot. The configured patient-sync wrapper
at `backend/app_factory.py:381` also closes over the broad coordinator instead
of honoring the supplied operation capability.

Impact: the type contracts do not describe runtime dependencies, minimal valid
implementations fail, and composition remains nominally rather than actually
capability-limited. This violates the explicit narrow, typed, declared-port
acceptance criterion.

Classification: introduced P2 that blocks because it violates an explicit
OpenSpec acceptance criterion.

Required resolution: define complete operation-specific ports (or cohesive
operation services/callables), remove duplicate/unrelated methods, compose
genuinely capability-limited adapters, and test each path with minimal
structural implementations that expose only the declared surface.

### [P2][REV-003] Cover deterministic MWL backfill selection and transaction rollback

The backfill requirement protects deterministic latest-attempt selection,
preservation of existing mappings/user-managed data, use of the supplied
startup connection, and rollback with the surrounding initialization
transaction. The focused test at
`tests/repositories/test_dcm4chee_mwl.py:90` creates only one attempt, deletes
all mappings, and verifies a successful reopen. The older test at
`tests/repositories/test_lab_store.py:197` has the same single-attempt,
delete-all shape.

Impact: the checked task 4.5 claims latest-selection, preservation, and rollback
coverage, but the tests would still pass if backfill chose an older attempt,
overwrote an existing mapping, or committed independently of a later failing
maintenance step.

Classification: introduced P2 that blocks because the missing coverage is an
explicit verification task and acceptance boundary.

Required resolution: add disposable-database tests with multiple ordered
attempts and a deliberately different existing mapping, proving only the
missing mapping uses the deterministic latest attempt and the existing row is
unchanged. Add a startup-maintenance failure after backfill and prove both the
mapping insertion and attempt linking roll back after reopen.

### [P2][REV-004] Prove result-refresh publication is atomic on completion failure

`tests/repositories/test_dcm4chee_results.py:74` covers only successful refresh
completion and generation ordering. Its rollback test at
`tests/repositories/test_dcm4chee_results.py:52` aborts an ordinary result-row
update, not `complete_dcm4chee_result_refresh` at
`backend/repositories/dcm4chee_results.py:296`. No test fails the refresh-run
publication update at `backend/repositories/dcm4chee_results.py:332` and then
checks visibility after rollback.

Impact: checked task 5.5 explicitly claims refresh atomicity and rollback, while
the acceptance contract protects completed-snapshot visibility. A regression
that partially publishes a failed generation would not be detected.

Classification: introduced P2 that blocks because the missing coverage is an
explicit verification task and acceptance boundary.

Required resolution: publish generation N, begin and populate N+1, force the
N+1 completion update to fail, reopen the disposable database, and prove N
remains the visible completed snapshot while N+1 has no partial completion or
snapshot state.

## Follow-up findings

None.

## Verification and residual risk

Fresh pre-review verification at the reviewed head passed: 290 full regression
tests, 38 architecture contract tests, Python compilation, strict OpenSpec
validation, committed/worktree whitespace checks, and the forbidden-scope
audit. The passing suite does not close the four acceptance gaps above because
the relevant boundary and failure cases are not represented by the current
tests.

No P0/P1 security, privacy, data-loss, live-service, transaction, or stored-row
regression was proven beyond these explicit P2 acceptance violations. The only
pre-existing worktree item is the untracked handoff document.

## Next Action

`/dev-fix --review "openspec/changes/split-dcm4chee-persistence-repositories/review/2026-07-15_feature-ZAC-59_split-dcm4chee-persistence-repositories_codex-review-r1.md"`

Reason: blocking findings REV-001 through REV-004 remain.
