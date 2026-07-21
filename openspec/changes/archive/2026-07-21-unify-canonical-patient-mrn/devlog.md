---
change: unify-canonical-patient-mrn
date: 2026-07-21
---

# Development Log

## Context

Unify Patient MRNs across OIE/HL7 v2, Medplum/FHIR, GDT, and dcm4chee/DICOM while keeping protocol-owned identifiers separate.

## Implementation

- Added canonical `MRN-NNNNNN` normalization, validation, allocation, and database-enforced normalized uniqueness.
- Propagated canonical MRN through protocol mappings and retained legacy GDT correlation aliases.
- Corrected API projections, console labels, documentation, and automated coverage.

## Decisions

- The MRN sequence is global, monotonic, and may contain per-server gaps.
- Medplum references, GDT workflow identifiers, and DICOM issuers/UIDs are not MRNs.

## Validation Plan

- Run focused repository/migration, API/service, and frontend suites.
- Run the full unittest suite, syntax checks, diff checks, and strict OpenSpec validation.
- Defer live external-server verification to an environment-specific workflow when available.

## Follow-ups

- Repair the repository's architecture ownership baselines before closure verification.
- Run live OIE, Medplum, GDT, and dcm4chee checks in `/dev-test` when those services are available.

## Verification

### Round 1 (2026-07-21 17:14:05 +08:00)

- Tested head: `d72b82e6666e7e9fdcd6bbe7d04c6ba455ad5ac5`
- Status: `fail`
- Checks: PASS — focused repository/migration suite (30 tests); PASS — focused Patient/OIE/FHIR/GDT/dcm4chee API and service suite (84 tests); PASS — focused frontend suite (17 tests); FAIL — full `unittest discover` suite (582/584 passed, 2 failures); PASS — JavaScript syntax checks for all affected views; PASS — Python compilation for affected backend modules; PASS — `git diff --check`; PASS — strict OpenSpec validation; SKIP (not required for local acceptance) — live OIE, Medplum, GDT, and dcm4chee verification because external service availability is environment-specific.
- Unresolved failures: `test_backend_catch_all_modules_match_reviewed_legacy_baseline` reports three unreviewed `backend/dashboard_services.py` placement entries; `test_owner_inventory_is_complete_and_aggregate_libraries_are_removed` reports the existing `integration/test_gdt_api.py` owner inventory is missing `test_gdt_bridge_config_rejects_missing_folders_without_creating_them`.
- Next action: `/dev-fix "repair architecture ownership baselines for dashboard_services and GDT test inventory"`

### Round 2 (2026-07-21 17:19:42 +08:00)

- Tested head: `621a270df17af9c597a7cd53528145a83bef1b7d`
- Status: `pass`
- Checks: PASS — focused repository/migration suite (30 tests); PASS — focused Patient/OIE/FHIR/GDT/dcm4chee API and service suite (84 tests); PASS — focused frontend and architecture suite (64 tests); PASS — full `unittest discover` suite (584 tests); PASS — JavaScript syntax checks for all affected views; PASS — Python compilation for affected backend modules; PASS — `git diff --check`; PASS — strict OpenSpec validation; SKIP (not required for local acceptance) — live OIE, Medplum, GDT, and dcm4chee verification because external service availability is environment-specific.
- Unresolved failures: none.
- Next action: `/dev-review`

### Round 3 (2026-07-21 17:29:03 +08:00)

- Tested head: `650ecde3e94fa41c3020f16b0e822202f3c9dba8`
- Status: `pass`
- Checks: PASS — REV-001/REV-002 focused repository, migration, GDT, and architecture suite (100 tests); PASS — full `unittest discover` suite (586 tests); PASS — JavaScript syntax checks for all affected views; PASS — Python compilation for affected backend modules; PASS — `git diff --check`; PASS — strict OpenSpec validation; SKIP (not required for local acceptance) — live OIE, Medplum, GDT, and dcm4chee verification because external service availability is environment-specific.
- Unresolved failures: none; review findings remain pending closure-review classification.
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-21 17:22:14 +08:00)

- Source: `contexts/work_logs/2026-07-21_feature-unify-canonical-patient-mrn_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `621a270df17af9c597a7cd53528145a83bef1b7d`
- Transitions: `REV-001 open; REV-002 open`
- Open blockers: `REV-001`, `REV-002`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-21_feature-unify-canonical-patient-mrn_codex-review-r1.md"`

### Round 2 (2026-07-21 17:30:27 +08:00)

- Source: `contexts/work_logs/2026-07-21_feature-unify-canonical-patient-mrn_codex-review-r2.md`
- Mode: `closure`
- Verdict: `changes-requested`
- Reviewed head: `650ecde3e94fa41c3020f16b0e822202f3c9dba8`
- Transitions: `REV-001 still-open; REV-002 resolved`
- Open blockers: `REV-001`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-21_feature-unify-canonical-patient-mrn_codex-review-r2.md" REV-001`

### Round 3 (2026-07-21 17:33:50 +08:00)

- Source: `contexts/work_logs/2026-07-21_feature-unify-canonical-patient-mrn_codex-review-r3.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `650ecde3e94fa41c3020f16b0e822202f3c9dba8`
- Transitions: `REV-001 accepted-risk; REV-002 resolved`
- Open blockers: none
- Follow-ups: none
- Next action: commit only the review/devlog workflow records, then `/dev-done`
