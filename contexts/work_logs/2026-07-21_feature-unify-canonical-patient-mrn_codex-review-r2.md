---
reviewer: codex
mode: closure
round: 2
branch: feature/unify-canonical-patient-mrn
base: main
reviewed_head: 650ecde3e94fa41c3020f16b0e822202f3c9dba8
previous_review: contexts/work_logs/2026-07-21_feature-unify-canonical-patient-mrn_codex-review-r1.md
previous_reviewed_head: 621a270df17af9c597a7cd53528145a83bef1b7d
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P1 | still-open | Canonical lookup now precedes aliases, but `backend/repositories/gdt_workflow.py:270-276` searches only Patients that already have a GDT context. A canonical Patient without an order/context is invisible, so the fallback at lines 278-288 can still select another Patient's colliding legacy alias. |
| REV-002 | P2 | resolved | `backend/repositories/schema.py:681-697` safely normalizes unambiguous canonicalizable values after duplicate audit; `backend/repositories/maintenance.py:12-18` uses the same canonical semantics for sequence high-water; `tests/repositories/test_schema_migrations.py:126-163` proves normalization and allocation of `MRN-900001`. |

## New blocking findings

None.

## Follow-up findings

None.

## Verification and residual risk

- The fix delta preserves exact Order-identifier precedence and correctly makes canonical MRN outrank a colliding alias when the canonical Patient already has a context; ambiguous legacy-only matches also remain unbound.
- REV-001 remains because Patient creation (`backend/repositories/patients.py:36`) does not create a GDT context; contexts are created during GDT order creation (`backend/repositories/gdt_workflow.py:73-89`). A result for a known canonical Patient with no context can therefore still be misassociated through alias fallback.
- Verification Round 3 passed the 100-test finding-focused suite, all 586 tests, syntax/compile checks, diff hygiene, and strict OpenSpec validation at the reviewed head.
- Live external-server checks and cross-process SQLite contention remain environment-specific residual risks.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-21_feature-unify-canonical-patient-mrn_codex-review-r2.md" REV-001`

Reason: REV-001 still permits a legacy alias to capture a known canonical Patient MRN when that Patient has no GDT context.
