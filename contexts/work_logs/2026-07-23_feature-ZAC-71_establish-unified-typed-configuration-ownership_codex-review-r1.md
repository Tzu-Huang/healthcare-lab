---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-71_establish-unified-typed-configuration-ownership
base: main
reviewed_head: d934e193bd6cca25c9bdb3adc408afa631432d15
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P2 | open | The Lab Server API still persists an independently writable Medplum `baseUrl` after the typed profile becomes authoritative. |
| REV-002 | P2 | open | The OIE adapter bypasses shared secret allowlisting/removal and reduces validation failures to a message without field paths. |
| REV-003 | P2 | open | Complete replacements audit every public field as changed, including no-op updates. |
| REV-004 | P2 | open | `authGraceSeconds: true` is accepted and persisted as integer `1`. |
| REV-005 | P2 | open | Medplum secret replacement trims leading and trailing whitespace before persistence. |

## New blocking findings

### [P2][REV-001] Medplum still has two independently writable URL owners

- Location: `backend/application_composition.py:142-155`, `backend/repositories/lab.py:80-93`, `backend/api/lab_servers.py:75-83`
- Impact: The typed Medplum profile is seeded from Lab Server inventory and then becomes the runtime authority, but `PUT /api/lab/servers/<id>` continues accepting `baseUrl` changes for the Medplum row. Operators can receive HTTP 200 with the new inventory URL while FHIR workflows continue using the unchanged typed URL. This preserves the competing sources of truth ZAC-71 explicitly exists to remove.
- Evidence: On a clean temporary app, updating the Medplum Lab Server to `https://competing.example/fhir/R4` returns 200 and reads back that value, while `get_effective("medplum").base_url` remains `http://127.0.0.1:8103/fhir/R4`.
- Classification: Acceptance-level correctness defect introduced by this change.
- Required resolution: Make the Medplum inventory URL a projection of the typed owner or reject/delegate profile-owned Lab Server field mutations. Add API/service coverage proving the inventory and effective profile cannot diverge.

### [P2][REV-002] The OIE adapter does not satisfy the shared typed mutation contract

- Location: `backend/services/integration_settings.py:62-77`, `backend/services/integration_settings.py:158-181`, `backend/api/integration_settings.py:74-93`
- Impact: The shared OIE endpoint silently ignores unknown secret names, rejects the required explicit password removal operation, and maps specialized validation failures to a generic message without the required field-path list. Callers therefore cannot rely on the closed typed contract or stable error shape across registered profiles.
- Evidence: `PUT /api/settings/profiles/oie` with `secrets: {"arbitrary": "canary"}` returns 200; deleting `managementApi.password` returns `secret_removal_rejected`; an invalid `managementApi.baseUrl` returns `settings_validation_failed` with only `message` and no `fields`.
- Classification: Explicit typed-settings and secret-semantics requirement violation.
- Required resolution: Give the OIE adapter an explicit field/secret schema, reject unknown keys, implement distinct password removal with a safe effective not-configured state, and translate OIE validation failures into stable bounded field-path entries. Add focused tests for all three cases without changing the existing `/api/oie/settings` response contract.

### [P2][REV-003] Mutation audits do not report the fields that actually changed

- Location: `backend/repositories/integration_settings.py:141-160`, `backend/repositories/integration_settings.py:203-216`
- Impact: Every complete update records every profile field in `changed_fields_json`, even when values are identical. This makes the durable audit claim changes that never occurred and prevents operators from determining what a mutation actually changed.
- Evidence: Submitting an unchanged Medplum profile returns 200, appends one audit, and reports `["authGraceSeconds","baseUrl","clientId","enabled","scope","tokenUrl"]`.
- Classification: Explicit audit correctness requirement violation.
- Required resolution: Compare the validated candidate and secret command against the stored state inside the transaction, record only fields with real changes, and define/test no-op behavior. A no-op must not claim unrelated changed fields; if it records an audit, the operation and empty change set must be intentional and specified.

### [P2][REV-004] Boolean auth grace values pass integer validation

- Location: `backend/domain/integration_settings.py:111-123`
- Impact: Python treats booleans as integers, so the validator accepts JSON `true` for `authGraceSeconds` and persists it as `1`. The profile is therefore not enforcing the explicit field type promised by the typed settings boundary.
- Evidence: `PUT /api/settings/profiles/medplum` with `authGraceSeconds: true` returns 200 and the effective setting becomes integer `1`.
- Classification: Explicit typed-validation requirement violation.
- Required resolution: Reject booleans before integer coercion and add domain/API tests for both boolean values plus valid integer/string policy as intended.

### [P2][REV-005] Secret replacement changes whitespace-sensitive credentials

- Location: `backend/domain/integration_settings.py:67-69`
- Impact: `replace_secret()` calls `strip()` and stores the trimmed value. A valid non-blank credential containing leading or trailing spaces is silently changed, so subsequent authentication uses a different secret from the operator's submitted replacement.
- Evidence: Replacing `clientSecret` with `"  spaced-secret  "` returns 200, but the effective secret is `"spaced-secret"`.
- Classification: Explicit write-only secret replacement requirement violation.
- Required resolution: Use trimming only to decide whether an input is blank; preserve the exact original non-blank string for storage. Add repository/service/API canary coverage that never prints the secret while proving exact round-trip through the private effective projection.

## Follow-up findings

None.

## Verification and residual risk

- Reviewed `git diff main...d934e193bd6cca25c9bdb3adc408afa631432d15`, both delta specs, tasks, ownership documentation, schema/migration, domain, repository, service, API, composition, consumer wiring, and focused tests.
- Persisted verification reports 66 focused tests and 655 full-suite tests passing at the reviewed head, plus Python compilation, diff check, and strict OpenSpec validation.
- Reproduced all five findings against temporary databases without changing repository files.
- Residual risk: no browser UI is added by this issue, and no external Medplum/OIE environment check is required for these deterministic contract defects.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-23_feature-ZAC-71_establish-unified-typed-configuration-ownership_codex-review-r1.md"`

Reason: five blocking explicit-requirement findings remain.
