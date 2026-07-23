## 1. Configuration Ownership Contract

- [ ] 1.1 Inventory every Medplum, OIE, GDT, dcm4chee, OpenEMR, AP-facing, Flask, and Compose configuration key with its current source and runtime consumers.
- [ ] 1.2 Publish the ownership matrix classifying each key exactly once as deployment-only, runtime persisted, secret, or derived/default, including bootstrap and restart/activation behavior.
- [ ] 1.3 Add contract tests that keep the matrix aligned with supported environment/Compose keys and reject duplicate or missing ownership classifications.

## 2. Typed Settings Domain and Persistence

- [ ] 2.1 Add closed integration profile registrations, typed public/effective projections, explicit preserve/replace/remove secret commands, and stable value-free validation error types.
- [ ] 2.2 Add ordered SQLite migration(s) for typed profile identity/version, separated secret storage, bootstrap provenance, and allowlisted mutation audits without creating a generic key-value mutation interface.
- [ ] 2.3 Implement repository transactions that validate complete typed candidates and atomically persist profile fields, secret changes, provenance, and audit records.
- [ ] 2.4 Add repository tests for valid round trips, unknown profile/field rejection, atomic validation failure, secret preserve/replace/remove, audit rollback, and prohibited-value canaries.

## 3. Bootstrap and Effective Configuration

- [ ] 3.1 Implement create-only environment/default bootstrap for missing registered profiles with complete pre-validation and durable persisted-profile authority.
- [ ] 3.2 Add clean-install, legacy-environment, persisted-override, changed-environment restart, invalid-bootstrap, and transaction-rollback migration tests.
- [ ] 3.3 Compose request-context-independent effective-settings readers and migrate the foundation-owned runtime consumer seams away from competing environment, Flask request, inventory, or raw SQL reads.
- [ ] 3.4 Add service/composition tests proving HTTP and background consumers receive the same effective typed settings and persisted overrides remain authoritative after restart.

## 4. Shared API and OIE Adaptation

- [ ] 4.1 Add shared typed settings service/API projections with stable success envelopes, field-path error codes, unknown-field rejection, and secret configured-state-only responses.
- [ ] 4.2 Implement the OIE shared-boundary adapter by delegating to the existing OIE settings service/repository without migrating its schema or changing lifecycle mapping operations.
- [ ] 4.3 Add API/service tests for secret-safe reads and mutations, blank-secret preservation, explicit removal, bounded errors, and value-free diagnostics/exceptions.
- [ ] 4.4 Run existing OIE settings, managed-Channel lifecycle, startup bootstrap, FHIR, GDT, and dcm4chee regression tests to prove compatibility.

## 5. Documentation and Verification

- [ ] 5.1 Document typed settings architecture, one-time environment migration, persisted ownership, filesystem secret-storage assumptions, and guidance required for later Settings issues.
- [ ] 5.2 Verify architecture rules prevent new integration consumers from reading migrated runtime settings directly from `os.environ`, Flask request state, or raw SQL.
- [ ] 5.3 Run focused settings/migration/composition tests, the complete regression suite, Python compilation, `git diff --check`, and strict OpenSpec validation.
