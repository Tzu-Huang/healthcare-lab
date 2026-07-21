---
reviewer: codex
mode: initial
round: 1
branch: feature/unify-canonical-patient-mrn
base: main
reviewed_head: 621a270df17af9c597a7cd53528145a83bef1b7d
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

None.

## New blocking findings

### [P1][REV-001] GDT legacy alias lookup can override an exact canonical-MRN patient match

- Evidence: `backend/repositories/gdt_workflow.py:273-277` combines canonical Patient MRN, effective legacy number, generated number, and override matches in one `OR` query, then selects the newest context with `ORDER BY context.id DESC LIMIT 1`. GDT overrides are user-controlled correlation values and are not constrained against canonical Patient MRNs. If Patient B has a newer context whose override equals Patient A's canonical MRN, a result carrying Patient A's canonical MRN is attached to Patient B's context.
- Impact: a clinical result can be displayed under the wrong Patient, which is an identity-integrity defect even though exact Order identifiers still take precedence.
- Classification: explicit-requirement blocker. The GDT spec requires a canonical MRN to resolve the corresponding Patient while legacy aliases remain compatible; legacy compatibility cannot supersede an unambiguous canonical identity.
- Required resolution: resolve canonical MRN separately and with higher precedence than legacy aliases, reject or explicitly treat ambiguous alias collisions as unmatched, and add regression coverage for canonical-MRN/legacy-alias collisions.

### [P2][REV-002] Migration leaves safely normalizable legacy MRNs unchanged and sequence seeding cannot recognize them

- Evidence: `backend/repositories/schema.py:662-688` audits normalized duplicates and installs the expression index but never rewrites an unambiguous value such as `" mrn-900000 "` to `MRN-900000`. `backend/repositories/maintenance.py:12-17` subsequently seeds the global sequence using a case-sensitive, untrimmed `MRN-(\d+)` match, so that value is also excluded from the high-water mark.
- Impact: migrated server tables continue displaying a noncanonical MRN even though it is safely normalizable, and a database whose sequence ledger is absent or stale can allocate a lower automatic number rather than advancing beyond the normalized existing value.
- Classification: explicit-requirement blocker. The migration plan requires normalization of unambiguous conforming legacy values, and the allocation contract requires persistent monotonic behavior across restart/migration.
- Required resolution: normalize unambiguous canonicalizable legacy values transactionally before creating the index (while preserving unique truly nonconforming identities), make sequence seeding use the same normalization semantics, and test normalization plus high-water allocation on a migrated legacy database.

## Follow-up findings

None.

## Verification and residual risk

- Verification at the reviewed head passed 178 focused checks, all 584 tests, affected JavaScript syntax checks, affected Python compilation, diff hygiene, and strict OpenSpec validation.
- Live OIE, Medplum, GDT, and dcm4chee checks remain environment-specific residual risk and are not required for local acceptance.
- Cross-process SQLite contention is not directly exercised; the expression unique index covers normalized alternate writes, but a later hardening test may verify lock/error behavior across independent application instances.
- Review inspected `main...621a270df17af9c597a7cd53528145a83bef1b7d` against the active OpenSpec requirements and task boundaries.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-21_feature-unify-canonical-patient-mrn_codex-review-r1.md"`

Reason: REV-001 and REV-002 block canonical Patient identity and legacy migration acceptance requirements.
