---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-69_expose-bootstrap-status-and-verify-restart-convergence
base: main
reviewed_head: 7f917f2c608f1309db65d24b295be285dd68f9ef
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P2 | open | Unsupported OIE versions derive a guidance code that the durable bootstrap repository rejects. |

## New blocking findings

### [P2][REV-001] Unsupported-version guidance cannot be persisted

- Location: `backend/services/oie_bootstrap_coordination.py:29`,
  `backend/repositories/oie_bootstrap_status.py:58-71`
- Impact: When OIE reports an unsupported version, the bootstrap result's safe
  `unsupported-version` category is mapped to `use-supported-oie-version`.
  `OieBootstrapStatusRepository.complete_run()` rejects that value because its
  guidance allowlist contains `verify-oie-version` instead. The coordinator
  then catches the persistence error and overwrites the intended distinct
  outcome with generic `failure` / `inspect-bootstrap-diagnostics` evidence.
  Operators therefore lose the bounded category and actionable version
  guidance required by the startup-bootstrap and runtime-diagnostics
  acceptance contracts.
- Evidence: Direct evaluation at the reviewed head produces
  `{"derived": "use-supported-oie-version", "allowlisted": false}`. Existing
  tests assert that the bootstrap service emits `unsupported-version`, but no
  coordinator-to-real-repository test covers completion of that result.
- Classification: acceptance-level correctness defect introduced by this
  change.
- Required resolution: Use one canonical allowlisted version-guidance code
  across coordination and persistence, then add a coordinator/repository test
  proving an unsupported-version run completes durably with its original safe
  category and guidance instead of falling back to generic failure.

## Follow-up findings

None.

## Verification and residual risk

- Reviewed `git diff main...7f917f2c608f1309db65d24b295be285dd68f9ef`,
  all four delta specs, tasks, bootstrap repository/coordinator, lifecycle
  reset fix, API/diagnostics wiring, Settings presentation, and affected tests.
- Verification Round 2 reports 664 full-suite tests, JavaScript syntax checks,
  Python compilation, Compose config, strict OpenSpec validation, and diff
  hygiene passing at the reviewed head.
- The isolated OIE 4.5.2 report covers clean startup, retained restart,
  one-Channel repair, delayed readiness/Retry, all supported reset
  combinations, and read-only surface checks.
- Residual risk: the live matrix exercised readiness and reset convergence but
  did not use an intentionally unsupported OIE image; REV-001 is independently
  reproducible without external infrastructure.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-23_feature-ZAC-69_expose-bootstrap-status-and-verify-restart-convergence_codex-review-r1.md"`

Reason: REV-001 violates explicit durable status and diagnostic guidance requirements and remains blocking.
