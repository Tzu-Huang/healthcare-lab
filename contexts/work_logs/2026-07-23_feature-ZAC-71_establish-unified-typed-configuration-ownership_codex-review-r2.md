---
reviewer: codex
mode: closure
round: 2
branch: feature/ZAC-71_establish-unified-typed-configuration-ownership
base: main
reviewed_head: 4c7d81fe281a9c2b11b3aafcbfafe185b4ca899c
previous_review: contexts/work_logs/2026-07-23_feature-ZAC-71_establish-unified-typed-configuration-ownership_codex-review-r1.md
previous_reviewed_head: d934e193bd6cca25c9bdb3adc408afa631432d15
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P2 | resolved | `LabRegistryService.update_server` rejects Medplum `baseUrl` mutations, with API coverage proving the typed effective value remains unchanged. |
| REV-002 | P2 | still-open | Unknown secrets, explicit password removal, and typed field-path errors are fixed, but unknown ordinary OIE fields are still silently accepted. |
| REV-003 | P2 | resolved | The repository compares public and secret values inside the transaction and records an empty change set for a tested no-op. |
| REV-004 | P2 | resolved | The validator explicitly rejects booleans and accepts a positive integer; API coverage exercises `true`, `false`, and `45`. |
| REV-005 | P2 | resolved | Blank detection trims only for classification while the original non-blank secret text is persisted and tested exactly. |

## New blocking findings

None.

## Follow-up findings

None.

## Verification and residual risk

- Closure review inspected `git diff d934e193bd6cca25c9bdb3adc408afa631432d15..4c7d81fe281a9c2b11b3aafcbfafe185b4ca899c` and the code/tests relevant to REV-001 through REV-005.
- Persisted verification at the reviewed head reports 73 focused tests and 662 complete-suite tests passing, plus Python compilation, `git diff --check`, and strict OpenSpec validation.
- Reproduction against a temporary application added an unknown top-level OIE field and received HTTP 200. `OieSettingsAdapter.replace` allowlists only secret names (`backend/services/integration_settings.py:72-86`), while the delegated validator reads expected keys without rejecting extras (`backend/domain/oie.py:26-33`).
- Residual risk: nested unknown OIE keys under `managementApi`, `resultListener`, and managed-channel entries appear subject to the same omission and need regression coverage with the bounded fix.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-23_feature-ZAC-71_establish-unified-typed-configuration-ownership_codex-review-r2.md"`

Reason: REV-002 remains blocking because the shared OIE field schema still accepts unknown ordinary fields.
