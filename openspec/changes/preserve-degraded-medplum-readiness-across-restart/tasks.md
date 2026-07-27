## 1. Persistence Contract

- [x] 1.1 Add an idempotent SQLite migration for opaque Medplum configuration revisions and the latest bounded verification projection.
- [x] 1.2 Implement repository read/write validation for allowlisted overall and stage outcomes without values, secrets, upstream text, or FHIR bodies.
- [x] 1.3 Advance the configuration revision on relevant public-field and secret mutations while preserving idempotent bootstrap behavior.

## 2. Diagnostic and Readiness Integration

- [ ] 2.1 Persist Save-and-test outcomes only when they still match the effective Medplum configuration revision.
- [ ] 2.2 Derive Medplum readiness as ready, degraded, or needs-setup from matching successful, matching failed, or missing/stale bounded evidence.
- [ ] 2.3 Ensure explicit re-verification can replace degraded evidence after recovery without adding startup or readiness-read network calls.

## 3. Verification

- [x] 3.1 Add migration and repository tests for revision changes, stale evidence, bounded validation, and legacy configured profiles.
- [ ] 3.2 Add service and API tests for successful, failed, concurrent/stale, and subsequent successful Save-and-test outcomes.
- [ ] 3.3 Add restart/recreation coverage proving failed Medplum readiness remains incomplete with retained storage.
- [ ] 3.4 Run focused Medplum, Settings readiness, migration, integration, frontend, security/redaction, and OpenSpec strict-validation checks.

## 4. ZAC-78 Closure Evidence

- [ ] 4.1 Re-run the isolated ZAC-78 Medplum failure and retained-container-recreation scenario using synthetic credentials.
- [ ] 4.2 Record bounded evidence that the fix preserves degraded readiness and does not expose credentials, PHI, FHIR bodies, or arbitrary upstream responses.
