---
reviewer: codex
mode: reset
round: 3
branch: feature/ZAC-46_implement-oie-management-api-client
base: main
reviewed_head: b94465a645df9fe906e6d4db5fff3c5ff275584b
previous_review: openspec/changes/implement-oie-management-api-client/review/2026-07-16_feature-ZAC-46_implement-oie-management-api-client_codex-review-r2.md
previous_reviewed_head: b839ab179eab4410586020eb457997675c017d2c
verdict: changes-requested
---

# Codex Review

Round 3 resets the review because rebasing invalidated the old reviewed-head
ancestry and Phase B materially expanded the accepted change scope. The review
therefore covers the complete `main...HEAD` change instead of treating the new
composition work as a closure delta.

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P1 | resolved | Login still accepts only documented success states; rejection and malformed-status regressions remain present and passing. |
| REV-002 | P1 | resolved | The TLS mode remains a closed enum and unknown values fail closed in both configuration and transport. |
| REV-003 | P2 | resolved | Every mutation path still invokes the cached 4.5.2 support gate before its mutation request. |
| REV-004 | P2 | resolved | Read operations still enforce operation-specific response fields and types. |
| REV-005 | P1 | new | The public `redeploy(channel_id)` operation sends the same single-channel `_deploy` request as `deploy(channel_id)` even though the recorded 4.5.2 contract exposes `_redeployAll`. |
| REV-006 | P2 | new | `git diff --check main...HEAD` fails on a trailing blank line in `design.md`, contradicting checked verification tasks and persisted pass evidence. |

## New blocking findings

### [P1][REV-005] Redeploy executes deploy instead of the recorded redeploy operation

- Evidence: `backend/clients/oie_management.py:256-260` maps both `deploy()` and
  `redeploy()` to `/channels/{channelId}/_deploy`. The focused mutation test
  explicitly asserts that both request URLs are equal, so it preserves rather
  than detects the defect. The change's authoritative evidence at
  `openspec/changes/implement-oie-management-api-client/evidence.md:33,40`
  records the available operation as `POST /channels/_redeployAll`, while the
  requirement and checked task promise a distinct redeploy primitive.
- Impact: a caller selecting redeploy does not execute the requested primitive;
  it performs an ordinary deploy and reports the result as `redeploy`. Future
  lifecycle orchestration would receive a false success signal for a different
  operation.
- Classification: late-blocker found during reset; pre-existing high-confidence
  correctness defect against an explicit operation contract.
- Required resolution: expose the exact recorded 4.5.2 redeploy-all request (or
  record authoritative evidence for another supported redeploy endpoint), align
  the method signature/spec wording with that contract, and replace the URL-
  equality assertion with an exact request-shape regression.

### [P2][REV-006] The checked diff-hygiene acceptance task does not pass for the branch

- Evidence: `git diff --check main...HEAD` reports
  `openspec/changes/implement-oie-management-api-client/design.md:91: new blank
  line at EOF.` The file ends with two CRLF sequences. Tasks 4.4 and 5.5 are
  checked and the devlog records `git diff --check` as passing, but the recorded
  command without a commit range only inspected the clean worktree and did not
  validate the committed change.
- Impact: the branch does not satisfy its explicit diff-hygiene acceptance work,
  and the persisted evidence overstates what was checked.
- Classification: P2 blocker because it directly violates checked acceptance
  criteria and their recorded verification evidence.
- Required resolution: remove the trailing blank line, run
  `git diff --check main...HEAD` against the committed fix state, and correct the
  verification record so its command and result are reproducible.

## Follow-up findings

None.

## Verification and residual risk

- Reviewed the complete `main...b94465a645df9fe906e6d4db5fff3c5ff275584b`
  diff, OpenSpec evidence/requirements/tasks, client/domain implementation,
  Phase B repository/service/application composition, and focused tests.
- The focused mutation test passes but reproduces REV-005's incorrect equality
  expectation; passing tests therefore do not mitigate that finding.
- Persisted apply evidence reports 383 full-suite tests, compilation, and strict
  OpenSpec validation passing. No independent `/dev-test` verification round for
  the rebased Phase B head is present yet.
- Live OIE verification remains intentionally outside this change. The concrete
  read-timeout implementation continues to rely on CPython urllib response
  internals; this remains a non-blocking portability risk.

## Next Action

`/dev-fix --review "openspec/changes/implement-oie-management-api-client/review/2026-07-16_feature-ZAC-46_implement-oie-management-api-client_codex-review-r3.md"`

Reason: REV-005 and REV-006 are blocking findings.
