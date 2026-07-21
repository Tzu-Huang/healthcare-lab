---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-51_harden-oie-hlab-runtime-delivery-diagnostics
base: main
reviewed_head: daa1e406950d429cf747cd874c56c3d2d0adad30
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

None.

## New blocking findings

### [P2][REV-001] Port diagnostics do not inspect live OIE port ownership

- Evidence: `backend/services/oie_diagnostics.py:18` declares `ports_in_use`, but no probe invokes it. `backend/app_factory.py:351-362` derives the port-contract result only from persisted desired mappings and the HLAB listener port. In addition, the real listener reports bind failures as `state="degraded"` at `backend/runtime/oie_result_listener.py:92`, while `backend/services/oie_diagnostics.py:94` recognizes a port conflict only for the synthetic state `bind-failed` used by its test.
- Impact: an external OIE Channel occupying `6600` or `6661`, or an actual HLAB bind conflict, is reported as a valid desired port contract or generic not-listening condition. Settings therefore cannot identify port failures at the required layer.
- Classification: explicit-requirement blocker. The runtime-diagnostics and Settings-workspace specs require independent runtime port checks and actionable per-layer failure categories.
- Required resolution: incorporate bounded live OIE `portsInUse` evidence into the port probe, classify the real listener degraded/bind-error state safely, and add tests using actual listener status shapes and external/duplicate live OIE port ownership.

### [P2][REV-002] Settings hides delivery counts and queued messages remain healthy

- Evidence: `backend/services/oie_diagnostics.py:140-146` marks delivery degraded only when `errors > 0`; a nonzero `queued` count with zero errors is categorized `available` and `healthy`. Although counts are placed in `evidence`, `frontend/static/js/views/settings.js:81-92` renders only layer, state, summary, and guidance and never renders `check.evidence`.
- Impact: an operator sees neither the queued/error totals nor a distinct indication that accepted ORUs are waiting for redelivery. A verified zero queue and a nonzero queue receive the same healthy presentation, so the principal ZAC-51 outage condition is not diagnosable from Settings.
- Classification: explicit-requirement blocker. The runtime-diagnostics spec requires queued/error counts to be displayed, and the Settings spec requires unavailable statistics to be distinguishable from a verified zero queue.
- Required resolution: give nonzero queued delivery a bounded actionable state/category, render allowlisted queued/error counts in Settings, explicitly distinguish zero from unavailable, and cover zero/queued/error/unavailable UI behavior.

## Follow-up findings

None.

## Verification and residual risk

- Verification evidence at the reviewed head passed: focused 90 tests, full 574 tests, 31 JavaScript syntax checks, Python compileall, Docker Compose config, strict OpenSpec validation, and diff hygiene.
- Live OIE 4.5.2 destination-statistics endpoint behavior remains environment-specific residual risk; unsupported responses degrade explicitly rather than fabricating zero.
- Review inspected `main...daa1e406950d429cf747cd874c56c3d2d0adad30` against the active OpenSpec requirements and task boundaries.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-21_feature-ZAC-51_harden-oie-hlab-runtime-delivery-diagnostics_codex-review-r1.md"`

Reason: REV-001 and REV-002 block the explicit runtime-diagnostics acceptance requirements.
