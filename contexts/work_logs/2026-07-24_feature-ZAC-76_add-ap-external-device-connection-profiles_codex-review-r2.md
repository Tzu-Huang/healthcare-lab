---
reviewer: codex
mode: closure
round: 2
branch: feature/ZAC-76_add-ap-external-device-connection-profiles
base: main
reviewed_head: c7df9b3810c8642d2fb355c60dfc6631065294c9
previous_review: contexts/work_logs/2026-07-24_feature-ZAC-76_add-ap-external-device-connection-profiles_codex-review-r1.md
previous_reviewed_head: 3490ac596e617ba81f8d402596e5167011f845b0
verdict: approved
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P2 | resolved | Effective dcm4chee settings now override AP MWL calling/station identity and carry AP AE, endpoint, and delivery role into runtime workflows; AP result return rejects a non-SCU effective role. |
| REV-002 | P2 | resolved | Effective GDT resolution now binds the saved `bridgeProfile` to the active Bridge profile and returns stable value-safe validation/readiness when it is unavailable. |
| REV-003 | P2 | resolved | AP MSH-3 through MSH-6 identity is represented in managed OIE preprocessing, normalized desired-state drift, preview-token digest, and owned guarded updates. |

## New blocking findings

None.

## Follow-up findings

None.

## Verification and residual risk

- Closure review inspected `git diff
  3490ac596e617ba81f8d402596e5167011f845b0..c7df9b3810c8642d2fb355c60dfc6631065294c9`
  and the production consumers and regression tests needed to verify each prior
  finding.
- `REV-001`: `backend/services/integration_settings.py` now composes
  `dimse.callingAETitle`, the scheduled-station identity, and the closed
  `apDevice` runtime projection. `backend/services/dcm4chee_coordination.py`
  consumes AP AE/endpoint/role evidence and enforces the SCU role before an AP
  result-return workflow.
- `REV-002`: effective GDT composition compares the AP association with the
  active typed Bridge profile, exposes its resolved name, and Settings readiness
  maps the same stable association failure to `needs-setup`.
- `REV-003`: the managed OIE template emits a bounded MSH identity
  preprocessing script; normalization compares the identity fields, owned XML
  merge updates the script only through guarded lifecycle execution, and the
  desired digest binds previews to those values.
- Verification Round 2 passed at the reviewed head: 810 Python tests with 1
  skip, 46 architecture tests, 39 JavaScript syntax checks, Python compilation,
  strict OpenSpec validation, and diff hygiene.
- The skipped test is pre-existing and not required by an acceptance criterion.
  Root `npm test` remains inapplicable because the repository has no root
  `package.json`.
- No product code or tests were modified during closure review.

## Next Action

Commit only the r1 and r2 review records, then run `/dev-done`.

Reason: the closure review is approved and only workflow review records remain
uncommitted.
