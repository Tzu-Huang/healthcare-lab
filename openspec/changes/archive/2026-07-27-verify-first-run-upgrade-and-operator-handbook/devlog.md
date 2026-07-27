---
change: verify-first-run-upgrade-and-operator-handbook
date: 2026-07-27
---

## Context

ZAC-78 is the closure gate for the unified Settings series. Its original
exclusive disposable run found ZAC-79 and ZAC-80, so closure resumed only after
both fixes reached `main`.

## Implementation

- Integrated current `main`, including `v1.1.0`, ZAC-79, and ZAC-80.
- Expanded the ZAC-78 release harness across defaults, upgrade workflow
  assembly, filesystem safety, independent integration failures, and
  cross-surface evidence scanning.
- Reconciled original live evidence with the post-fix ZAC-79 and ZAC-80
  evidence records.

## Decisions

- Preserve the running operator-owned `interoperability-lab` project.
- Treat the original exclusive ZAC-78 run plus linked post-fix live evidence as
  the live closure record.
- Retain no screenshots; enforce screenshot-OCR safety through the common
  synthetic canary gate.

## Validation Plan

- Run the focused ZAC-78, GDT, dcm4chee, AP, OIE, readiness, migration, and
  persisted-settings suites.
- Run the full repository test suite, compile checks, OpenSpec strict
  validation, handbook checks, and diff hygiene under `/dev-test`.

## Verification

### Apply round 1 (2026-07-27 Asia/Taipei)

- Tested head: `d882d05`
- Status: `pass`
- Checks: focused release matrix passed 70 tests with 1 Windows symlink
  capability skip; Docker ownership pre-flight found the normal
  `interoperability-lab` project active, so no shared resources were mutated;
  linked ZAC-79 and ZAC-80 post-fix live evidence is present.
- Unresolved failures: none in requested implementation tasks.
- Next action: `/dev-test`

### Round 2 (2026-07-27 12:04 Asia/Taipei)

- Tested head: `e3d26c067ccdc3cacf63f1e0b94167400e6a9514`
- Status: `pass`
- Checks: pass — `python -m unittest discover -s tests` (871 tests, 1
  non-required Windows directory-symlink capability skip); pass —
  `python -m compileall -q backend tests`; pass — focused ZAC-78, Compose,
  wrapper, container-release, and container-workflow contracts (55 tests);
  pass — `openspec validate verify-first-run-upgrade-and-operator-handbook
  --strict`; pass — `git diff --check`; pass — post-check product worktree
  remains clean; pass — committed disposable and post-fix live evidence covers
  required fresh-install, upgrade, failure, restart, and safety matrices.
- Unresolved failures: none.
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-27 12:09 Asia/Taipei)

- Source: `contexts/work_logs/2026-07-27_feature-ZAC-78_verify-first-run-upgrade-and-operator-handbook_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `e3d26c067ccdc3cacf63f1e0b94167400e6a9514`
- Transitions: `REV-001 opened; REV-002 opened`
- Open blockers: `REV-001, REV-002`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-27_feature-ZAC-78_verify-first-run-upgrade-and-operator-handbook_codex-review-r1.md"`

### Round 2 (2026-07-27 14:36 Asia/Taipei)

- Source: `contexts/work_logs/2026-07-27_feature-ZAC-78_verify-first-run-upgrade-and-operator-handbook_codex-review-r2.md`
- Mode: `closure`
- Verdict: `changes-requested`
- Reviewed head: `a5d1bab8c2b26de66f6268f7fd68342c679b6ed1`
- Transitions: `REV-001 still-open; REV-002 resolved`
- Open blockers: `REV-001`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-27_feature-ZAC-78_verify-first-run-upgrade-and-operator-handbook_codex-review-r2.md"`

### Round 3 (2026-07-27 14:56 Asia/Taipei)

- Source: `contexts/work_logs/2026-07-27_feature-ZAC-78_verify-first-run-upgrade-and-operator-handbook_codex-review-r3.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `4ca5fedb920c41f1603bc0662347450a6199c6da`
- Transitions: `REV-001 resolved`
- Open blockers: `none`
- Follow-ups: none
- Next action: commit only the review and devlog workflow records, then run `/dev-done`

### Round 3 (2026-07-27 14:15 Asia/Taipei)

- Tested head: `22cb3d2dae8dd854bb9eb0a53eb49e6aa04c9476`
- Status: `incomplete`
- Checks: pass — `python -m unittest discover -s tests` (872 tests, 1
  non-required Windows directory-symlink capability skip); pass —
  `python -m compileall -q backend tests`; pass — English DOCX validation
  (1776 paragraphs); pass — zh-TW DOCX validation (1781 paragraphs); pass —
  `openspec validate verify-first-run-upgrade-and-operator-handbook --strict`;
  pass — `git diff --check`; pass — post-check product worktree remains clean;
  skip (required) — publish/select a semantic-version image containing ZAC-80
  and rerun the disposable fresh-install matrix against that exact image
  (registry has pre-ZAC-80 `1.1.0` and post-ZAC-80 `sha-54e60d0`, but no
  `1.1.1`).
- Unresolved failures: required task 6.1 and review blocker REV-001 remain
  incomplete until the semantic-version image is published, selected, and
  verified.
- Next action: `/dev-fix "publish and verify semantic-version image containing ZAC-80"`

### Round 4 (2026-07-27 14:31 Asia/Taipei)

- Tested head: `a5d1bab8c2b26de66f6268f7fd68342c679b6ed1`
- Status: `pass`
- Checks: pass — `python -m unittest discover -s tests` (872 tests, 1
  non-required Windows directory-symlink capability skip); pass —
  `python -m compileall -q app.py backend tests`; pass — focused release,
  Compose, workflow, and ZAC-78 verification contracts (45 tests); pass —
  English and zh-TW DOCX package-integrity validation with
  `python -m zipfile -t`; pass —
  `openspec validate verify-first-run-upgrade-and-operator-handbook --strict`;
  pass — `git diff --check`; pass — committed `v1.1.1` release workflow and
  isolated full-stack evidence cover the previously incomplete semantic image
  gate; pass — post-check product state remained unchanged at the full tested
  SHA, with only this workflow devlog dirty.
- Unresolved failures: none.
- Next action: `/dev-review`

### Round 5 (2026-07-27 14:52 Asia/Taipei)

- Tested head: `4ca5fedb920c41f1603bc0662347450a6199c6da`
- Status: `pass`
- Checks: pass — `python -m unittest discover -s tests` (873 tests, 1
  non-required Windows directory-symlink capability skip); pass —
  `python -m compileall -q app.py backend tests`; pass — focused release,
  Compose, workflow, ZAC-78, and bilingual handbook contracts (46 tests);
  pass — English DOCX schema validation (1776 paragraphs); pass — zh-TW DOCX
  schema validation (1781 paragraphs); pass — stale `1.0.0` image/release-gate
  claim scan; pass —
  `openspec validate verify-first-run-upgrade-and-operator-handbook --strict`;
  pass — `git diff --check`; pass — post-check product state remained
  unchanged at the full tested SHA, with only this workflow devlog dirty.
- Unresolved failures: none.
- Next action: `/dev-review`
