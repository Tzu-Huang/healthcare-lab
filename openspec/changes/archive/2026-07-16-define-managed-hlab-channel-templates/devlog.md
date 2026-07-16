---
change: define-managed-hlab-channel-templates
date: 2026-07-16
---

# Development Log

## Context

ZAC-47 defines two constrained, persistence-neutral OIE 4.5.2 managed Channel
templates using the ZAC-61 operator exports as canonical structural evidence.

## Implementation

- Added typed managed Channel contracts, validation, route-set conflict checks,
  and a stable ownership marker.
- Added complete ORM-to-AP and ORU-to-HLAB XML rendering with explicit UTF-8,
  fixed MLLP topology, deterministic normalization, and resilient ORU queueing.
- Added canonical characterization, serialization, secret-leakage, and
  architecture tests without persistence, transport, Flask, or runtime wiring.

## Decisions

- AP host remains an explicit compiler input and a persistence prerequisite for
  ZAC-48; the canonical export IP is never treated as a product default.
- OIE-generated IDs, revisions, timestamps, and user IDs are excluded from
  desired-state comparison.

## Validation Plan

Run focused domain/template tests, architecture contracts, the full unittest
suite, in-memory Python compilation, `git diff --check`, and strict OpenSpec
validation without contacting a live OIE instance.

## Follow-ups

- ZAC-48 must source the AP host from persisted Settings before integration.

## Verification

### Round 1 (2026-07-16 14:41:52 +08:00)

- Tested head: `a254454cc24bfabe2f02ea6b3f3d7cc7ca82f749`
- Status: `pass`
- Checks: `python -m unittest tests.domain.test_oie_channels tests.templates.test_oie_channels`: pass (18 tests); `python -m unittest tests.test_architecture_contract`: pass (42 tests); `python -m unittest discover -s tests`: pass (347 tests); in-memory `compile(...)` over `backend/**/*.py` and `tests/**/*.py`: pass (137 files); `git diff --check`: pass; `openspec validate define-managed-hlab-channel-templates --strict`: pass.
- Unresolved failures: none
- Next action: `/dev-review`

### Round 2 (2026-07-16 15:02:17 +08:00)

- Tested head: `07088e56ecfa3ba5e1598f20b736a18124570f0c`
- Status: `pass`
- Checks: `python -m unittest tests.domain.test_oie_channels tests.templates.test_oie_channels`: pass (20 tests); `python -m unittest tests.test_architecture_contract`: pass (42 tests); `python -m unittest discover -s tests`: pass (347 tests); in-memory `compile(...)` over `backend/**/*.py` and `tests/**/*.py`: pass (137 files); `git diff --check`: pass; `openspec validate define-managed-hlab-channel-templates --strict`: pass.
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-16 14:48:19 +08:00)

- Source: `openspec/changes/define-managed-hlab-channel-templates/review/2026-07-16_feature-ZAC-47_define-managed-hlab-channel-templates_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `a254454cc24bfabe2f02ea6b3f3d7cc7ca82f749`
- Transitions: none
- Open blockers: `REV-001`, `REV-002`, `REV-003`
- Follow-ups: none
- Next action: `/dev-fix --review "openspec/changes/define-managed-hlab-channel-templates/review/2026-07-16_feature-ZAC-47_define-managed-hlab-channel-templates_codex-review-r1.md"`

### Round 2 (2026-07-16 15:04:16 +08:00)

- Source: `openspec/changes/define-managed-hlab-channel-templates/review/2026-07-16_feature-ZAC-47_define-managed-hlab-channel-templates_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `07088e56ecfa3ba5e1598f20b736a18124570f0c`
- Transitions: `REV-001 resolved; REV-002 resolved; REV-003 resolved`
- Open blockers: none
- Follow-ups: none
- Next action: commit only the review and devlog workflow records, then run `/dev-done`
