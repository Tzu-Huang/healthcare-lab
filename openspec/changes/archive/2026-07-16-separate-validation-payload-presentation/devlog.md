---
change: separate-validation-payload-presentation
date: 2026-07-16
---

# Development Log

## Context

ZAC-61 separates validation, protocol construction, reusable presentation, and
persistence ownership without changing public, payload, or storage contracts.

## Implementation

Added bounded-context mapper ownership; completed Patient, Order, FHIR, GDT,
dcm4chee, Lab, and OIE responsibility migrations; retained mechanical
compatibility delegates; and enforced repository and mapper boundaries.

## Decisions

- Preserve exact public dictionaries and generated protocol payloads.
- Retain GDT bridge directory readiness in its infrastructure health owner.
- Keep compatibility exports mechanical and shrink architecture baselines only.

## Validation Plan

Run complete unittest discovery, Python compilation, applicable artifact
validation, `git diff --check`, and strict OpenSpec validation against a clean,
fully captured `HEAD`.

## Follow-ups

Proceed through initial `/dev-review`; no product follow-ups are open from apply.

## Verification

### Round 1 (2026-07-16 Asia/Taipei)

- Tested head: `7b881a2066d99db91dd19dd84d71669cead63084`
- Status: `pass`
- Checks:
  - pass — `python -m unittest discover -s tests -p 'test_*.py'` — 359 tests passed.
  - pass — `python -m compileall -q backend tests`.
  - pass — PowerShell XML parse of `docs/AP_RESULT_TO_LAB.xml` and `docs/Dashboard_to_OIE_to_AP.xml` — 2 files parsed.
  - pass — sensitive-key marker scan of both XML exports — no matches.
  - pass — `git diff --check HEAD`.
  - pass — `openspec validate separate-validation-payload-presentation --strict`.
  - skip (not required) — frontend syntax check; no frontend files changed.
- Unresolved failures: none
- Next action: `/dev-review`

### Round 2 (2026-07-16 14:29 Asia/Taipei)

- Tested head: `2365f0e5b07586bef032ad046498cfd099700114`
- Status: `pass`
- Checks:
  - pass — `python -m unittest discover -s tests -p "test_*.py"` — 361 tests passed.
  - pass — `python -m compileall -q backend tests`.
  - pass — `git diff --check HEAD`.
  - pass — `openspec validate separate-validation-payload-presentation --strict`.
  - skip (not required) — frontend syntax check; no frontend files changed by the review fixes.
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-16 Asia/Taipei)

- Source: `openspec/changes/separate-validation-payload-presentation/review/2026-07-16_feature-zac-61-separate-validation-payload-presentation_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `7b881a2066d99db91dd19dd84d71669cead63084`
- Transitions: `REV-001 open; REV-002 open`
- Open blockers: `REV-001, REV-002`
- Follow-ups: none
- Next action: `/dev-fix --review "openspec/changes/separate-validation-payload-presentation/review/2026-07-16_feature-zac-61-separate-validation-payload-presentation_codex-review-r1.md"`

### Round 2 (2026-07-16 14:31 Asia/Taipei)

- Source: `openspec/changes/separate-validation-payload-presentation/review/2026-07-16_feature-zac-61-separate-validation-payload-presentation_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `2365f0e5b07586bef032ad046498cfd099700114`
- Transitions: `REV-001 resolved; REV-002 resolved`
- Open blockers: `none`
- Follow-ups: none
- Next action: commit only the review and devlog workflow records, then run `/dev-done`
