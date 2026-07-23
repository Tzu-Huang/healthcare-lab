## 1. Typed Profile and Persistence

- [ ] 1.1 Register the closed dcm4chee profile schema, defaults, validators, public fields, secret fields, and stable field-level errors.
- [ ] 1.2 Add idempotent missing-profile bootstrap from eligible `DCM4CHEE_*` values and document browser-facing versus application-facing Docker defaults.
- [ ] 1.3 Add typed profile read/update APIs with atomic persistence, write-only secret mutations, mounted-reference projections, value-free audits, and stable identity conflict handling.
- [ ] 1.4 Add validation, bootstrap, migration, persistence, rollback, audit, redaction, and identity-conflict tests.

## 2. Canonical Effective Runtime

- [ ] 2.1 Compose an application-scoped effective dcm4chee profile reader that supplies immutable operation snapshots outside request context.
- [ ] 2.2 Migrate Patient ADT sync and MWL create/readback to the effective persisted profile.
- [ ] 2.3 Migrate result reconciliation, viewer links, fixture behavior, and remaining dcm4chee consumers to the same effective profile.
- [ ] 2.4 Add compatibility tests proving built-in defaults and external profiles are used consistently across every workflow.

## 3. Bounded Diagnostics and Readiness

- [ ] 3.1 Implement independent timeout-bounded Web UI HTTP, QIDO-RS metadata, HL7 TCP, and DIMSE TCP checks with allowlisted redacted outcomes.
- [ ] 3.2 Distinguish transport reachability from protocol success and preserve partial results across check failures and timeouts.
- [ ] 3.3 Replace the static-disabled readiness provider with dcm4chee-owned disabled, needs-setup, ready, and degraded assessments.
- [ ] 3.4 Add diagnostic and readiness tests for built-in Docker, external PACS, partial connectivity, disabled state, timeouts, and sensitive canaries.

## 4. Modular dcm4chee Settings Experience

- [ ] 4.1 Register a dcm4chee-owned Settings module with dedicated view/controller, API adapter, state, styles, and accessible common fields.
- [ ] 4.2 Add the Advanced disclosure for DICOMweb overrides, viewer, UID, HL7 identities, TLS/authentication, and mounted credential references.
- [ ] 4.3 Present separate save, validation, activation, and diagnostic outcomes with redacted configured/reference state.
- [ ] 4.4 Integrate dcm4chee readiness and diagnostics into Overview, guided setup, and Run all checks while preserving optional-disabled completion.
- [ ] 4.5 Add frontend and API tests for module ownership, accessibility, validation mapping, advanced fields, disabled behavior, and redaction.

## 5. Verification

- [ ] 5.1 Run focused typed-settings, dcm4chee client/workflow, diagnostics, readiness, API, and frontend tests and record evidence.
- [ ] 5.2 Run existing Patient, Order, MWL, result reconciliation, Settings, and configuration-architecture regression suites.
- [ ] 5.3 Validate the OpenSpec change strictly and confirm APIs, diagnostics, readiness, logs, and errors expose no secrets, private-key material, raw upstream payloads, or PHI.
