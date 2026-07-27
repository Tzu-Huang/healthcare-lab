---
reviewer: codex
mode: closure
round: 3
branch: feature/ZAC-78_verify-first-run-upgrade-and-operator-handbook
base: main
reviewed_head: 4ca5fedb920c41f1603bc0662347450a6199c6da
previous_review: contexts/work_logs/2026-07-27_feature-ZAC-78_verify-first-run-upgrade-and-operator-handbook_codex-review-r2.md
previous_reviewed_head: a5d1bab8c2b26de66f6268f7fd68342c679b6ed1
verdict: approved
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P2 | resolved | Both handbook sources and generated Word editions now identify the verified `v1.1.1` image/run and completed publication/isolated-clean-install gate, retain unrelated blocked boundaries, and are protected by a Markdown/DOCX drift contract. |

## New blocking findings

None.

## Prior blocking findings

### [P2][REV-001] Released handbook facts are reconciled

Resolved. The English and Traditional Chinese handbook sources now:

- identify `v1.1.1`, release commit
  `54e60d0e69d25c256474d9d0a5c790b1d9b7599e`, Actions run `30242203066`,
  and `ghcr.io/tzu-huang/healthcare-lab:1.1.1`;
- describe anonymous publication, immutable readiness, and the isolated
  clean full-stack installation as complete;
- use `v1.1.1` in the application and protocol compatibility matrices; and
- continue to mark unrelated dcm4chee, GDT, recovery, support, and
  physical-device/control boundaries as blocked.

The regenerated English and Traditional Chinese Word editions contain the same
new image/run facts and no longer contain the obsolete `1.0.0` image or
`v1.0.0 operational release gate` claim. The new regression contract reads
both Markdown sources and both DOCX `word/document.xml` payloads, asserting the
verified state and rejecting the stale claims.

## Follow-up findings

None.

## Verification and residual risk

- Reviewed
  `a5d1bab8c2b26de66f6268f7fd68342c679b6ed1..4ca5fedb920c41f1603bc0662347450a6199c6da`
  and the prior r2 finding directly.
- Verification Round 5 passed 873 repository tests with one non-required
  Windows directory-symlink capability skip, 46 focused release/Compose/
  handbook contracts, compilation, both DOCX schema validations, stale-claim
  scan, OpenSpec strict validation, and diff hygiene.
- DOCX visual rendering was unavailable in the current Windows environment
  because LibreOffice/Poppler were not installed and the helper's AF_UNIX shim
  was unsupported. This is residual presentation risk, not a required release
  criterion; schema, paragraph preservation, and content contracts passed.
- REV-002 remains resolved; no regression evidence was found in this fix delta.

## Next Action

Commit only the review and devlog workflow records, then run `/dev-done`.

Reason: all blocking findings are closed and the reviewed product state is
approved, but workflow records remain uncommitted.
