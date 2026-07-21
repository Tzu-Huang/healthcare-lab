---
change: harden-oie-hlab-runtime-delivery-diagnostics
date: 2026-07-21
---

## Context

ZAC-51 hardens the AP-to-OIE-to-HLAB ORU delivery path so temporary lab-app downtime remains retryable and failures are diagnosable without exposing secrets or PHI.

## Implementation

- Separated HLAB listener settings from OIE host-published ingress ports and aligned canonical/compiled ORU queue behavior.
- Enforced `MSH-10` idempotency with duplicate recognition and bounded failure ACK behavior.
- Added layered runtime diagnostics, destination statistics availability, Settings mutation audit, and recovery guidance.
- Added focused backend, frontend, Compose, outage/recovery, redaction, and schema ownership coverage.

## Decisions

- OIE destination queueing is the durable delivery boundary.
- Missing `MSH-10` is rejected so a supported result cannot be accepted without a stable redelivery key.
- Diagnostics are independently degradable and expose only allowlisted evidence.
- Host-published port changes require container recreation; Channel endpoints require Apply/Redeploy.

## Validation Plan

- Run focused OIE/runtime/Settings suites and the full unittest suite.
- Check every frontend JavaScript module, compile Python sources, validate Compose and OpenSpec, and verify diff hygiene.
- Treat live external OIE/Docker outage exercises as environment-specific; locally simulatable failure/recovery paths are automated.

## Follow-ups

- Confirm destination statistics behavior against the deployed OIE 4.5.2 runtime during environment acceptance.

## Verification

### Round 1 (2026-07-21 11:34 +08:00)

- Tested head: `daa1e406950d429cf747cd874c56c3d2d0adad30`
- Status: `pass`
- Checks: PASS — focused OIE/runtime/Settings unittest selection, 90 tests; PASS — full `python -m unittest`, 574 tests; PASS — `node --check` for 31 frontend JavaScript files; PASS — Python `compileall` for backend and tests; PASS — Docker Compose config validation; PASS — strict OpenSpec validation; PASS — `git diff --check`; PASS — post-check worktree remained clean; SKIP (not required locally) — live OIE 4.5.2 and real container outage exercise, with locally simulatable retry/recovery coverage passing in the automated suites.
- Unresolved failures: none
- Next action: `/dev-review`

### Round 2 (2026-07-21 11:46 +08:00)

- Tested head: `531d2256ae5d77ba4af600e0f3dfd72747ec8cf0`
- Status: `pass`
- Checks: PASS — focused post-fix OIE/runtime/Settings unittest selection, 40 tests; PASS — full `python -m unittest`, 577 tests; PASS — `node --check` for 31 frontend JavaScript files; PASS — Python `compileall` for backend and tests; PASS — Docker Compose config validation; PASS — strict OpenSpec validation; PASS — `git diff --check`; PASS — post-check product worktree remained clean; SKIP (not required locally) — live OIE 4.5.2 and real container outage exercise, with locally simulatable retry/recovery coverage passing in the automated suites.
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-21 11:42 +08:00)

- Source: `contexts/work_logs/2026-07-21_feature-ZAC-51_harden-oie-hlab-runtime-delivery-diagnostics_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `daa1e406950d429cf747cd874c56c3d2d0adad30`
- Transitions: none
- Open blockers: `REV-001`, `REV-002`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-21_feature-ZAC-51_harden-oie-hlab-runtime-delivery-diagnostics_codex-review-r1.md"`

### Round 2 (2026-07-21 11:47 +08:00)

- Source: `contexts/work_logs/2026-07-21_feature-ZAC-51_harden-oie-hlab-runtime-delivery-diagnostics_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `531d2256ae5d77ba4af600e0f3dfd72747ec8cf0`
- Transitions: `REV-001 resolved; REV-002 resolved`
- Open blockers: `none`
- Follow-ups: `none`
- Next action: commit only the review and devlog workflow records, then run `/dev-done`
