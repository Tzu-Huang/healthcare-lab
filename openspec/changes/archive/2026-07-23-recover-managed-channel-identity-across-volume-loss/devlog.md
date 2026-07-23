---
change: recover-managed-channel-identity-across-volume-loss
date: 2026-07-23
---

## Context

ZAC-68 extends the existing bounded OIE startup bootstrap so managed Channel identity can recover safely when the Healthcare Lab SQLite volume and OIE appdata volume are retained or reset independently.

## Implementation

- Added conservative `recoverable` inventory classification with exact marker, logical type, payload, route, uniqueness, and listener ownership validation.
- Added atomic expected-empty mapping rebinding with bounded lifecycle audit evidence.
- Added guarded startup recovery that revalidates complete inventory, preserves live deployment state, and reconciles logical types independently.
- Added persistence-matrix, blocker, idempotence, stale-state, audit-safety, and stopped-state tests plus operating documentation.

## Decisions

- Recovery is distinct from missing, unchanged, drifted, and conflicted classification.
- Mapping bind and recovery audit commit in one database transaction.
- Existing Channels are never deployed, updated, or otherwise mutated during identity recovery.
- Unknown or contradictory route ownership fails closed.

## Validation Plan

- Focused domain, repository, lifecycle, and bootstrap unit tests.
- Complete Python unittest regression suite.
- Python bytecode compilation, whitespace validation, and strict OpenSpec validation.

## Follow-ups

- Initial closure-oriented code review of the tested product state.

## Verification

### Round 1 (2026-07-23T10:19:28+08:00)

- Tested head: `ae767bded8cb39e6f1ca81197fd5c3eda1a609da`
- Status: `pass`
- Checks: `python -m unittest tests.domain.test_oie_channel_lifecycle tests.repositories.test_oie_settings tests.services.test_oie_channel_lifecycle tests.services.test_oie_channel_bootstrap` — pass, 72 tests; `python -m unittest discover -s tests` — pass, 641 tests; `python -m compileall -q backend tests` — pass; `git diff --check` — pass; `openspec validate recover-managed-channel-identity-across-volume-loss --strict` — pass; post-check product worktree — clean and still at tested head.
- Unresolved failures: none
- Next action: `/dev-review`

### Round 2 (2026-07-23T10:37:46+08:00)

- Tested head: `c692c027185b330f8ea0769b166cdb604aa2c289`
- Status: `pass`
- Checks: `python -m unittest tests.domain.test_oie_channel_lifecycle tests.repositories.test_oie_settings tests.services.test_oie_channel_lifecycle tests.services.test_oie_channel_bootstrap` - pass, 76 tests; `python -m unittest discover -s tests` - pass, 645 tests; `python -m compileall -q backend tests` - pass; `git diff --check` - pass; `openspec validate recover-managed-channel-identity-across-volume-loss --strict` - pass; post-check product state - unchanged at tested head, with only the pre-existing workflow review artifact uncommitted.
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-23T10:24:00+08:00)

- Source: `contexts/work_logs/2026-07-23_feature-ZAC-68_recover-managed-channel-identity-across-volume-loss_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `ae767bded8cb39e6f1ca81197fd5c3eda1a609da`
- Transitions: `REV-001 open; REV-002 open`
- Open blockers: `REV-001, REV-002`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-23_feature-ZAC-68_recover-managed-channel-identity-across-volume-loss_codex-review-r1.md"`

### Round 2 (2026-07-23T10:39:36+08:00)

- Source: `contexts/work_logs/2026-07-23_feature-ZAC-68_recover-managed-channel-identity-across-volume-loss_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `c692c027185b330f8ea0769b166cdb604aa2c289`
- Transitions: `REV-001 resolved; REV-002 resolved`
- Open blockers: none
- Follow-ups: none
- Next action: commit only workflow review/devlog records, then run `/dev-done`
