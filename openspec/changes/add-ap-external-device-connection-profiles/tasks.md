## 1. Device Domain and Persistence

- [x] 1.1 Define AP profile, environment, default-selection, protocol-section, safe metadata, and observation contracts with stable validation errors.
- [x] 1.2 Add idempotent multi-profile schema, transactional repository operations, uniqueness/default invariants, value-free audits, and migration coverage.
- [x] 1.3 Add one-time compatibility bootstrap from eligible OIE, GDT Bridge, and dcm4chee values without overwriting existing AP profiles.
- [x] 1.4 Add domain and repository tests for one/multiple profiles, duplicate names, defaults, disabled profiles, rollback, and concurrent/stale selection.

## 2. Effective Configuration and Integrations

- [x] 2.1 Compose an application-scoped effective AP resolver with immutable environment-specific HL7, GDT, and DICOM projections.
- [x] 2.2 Feed effective AP HL7 values into approved OIE desired configuration and expose `apply-required` drift without lifecycle mutation.
- [x] 2.3 Associate effective AP GDT identity with the selected GDT Bridge profile while retaining Bridge-owned filesystem and activation settings.
- [x] 2.4 Feed effective AP AE, MWL identity, endpoint, and result-delivery role into dcm4chee workflows while retaining archive-owned values.
- [x] 2.5 Add cross-feature tests proving every consumer uses the same effective snapshot and disabled sections are excluded.

## 3. APIs, Diagnostics, and Readiness

- [x] 3.1 Add profile list/read/create/update/default-selection APIs with atomic errors and value-safe audit projections.
- [x] 3.2 Implement independent timeout-bounded connectivity checks with partial results and transport-versus-protocol distinctions.
- [x] 3.3 Record and expose last-observed interaction metadata through a closed PHI-safe schema.
- [x] 3.4 Replace static AP readiness with disabled, needs-setup, apply-required, degraded, and ready assessments.
- [x] 3.5 Add API, diagnostics, readiness, timeout, partial-failure, and sensitive-canary tests.

## 4. Modular Settings Experience

- [x] 4.1 Add an AP-owned Settings template/controller, API adapter, state, styles, and module registration.
- [x] 4.2 Implement accessible profile management, environment/default controls, and conditional HL7, GDT, and DICOM sections.
- [x] 4.3 Clearly label AP endpoints versus Healthcare Lab/integration endpoints and present validation and activation impact.
- [x] 4.4 Present bounded diagnostics, safe last interaction, OIE `apply-required` guidance, and Overview readiness.
- [x] 4.5 Add frontend tests for module ownership, accessibility, multi-profile behavior, protocol validation, direction labels, readiness, and redaction.

## 5. Verification

- [x] 5.1 Run focused domain, migration, repository, service, API, integration, diagnostics, readiness, and frontend suites.
- [x] 5.2 Run OIE lifecycle, GDT Bridge, dcm4chee MWL/result, Settings workspace, and configuration-ownership regressions.
- [x] 5.3 Validate the OpenSpec change strictly and confirm saved profiles never mutate OIE automatically.
- [x] 5.4 Confirm APIs, audits, logs, diagnostics, and observations contain no raw clinical payloads, Patient data, Order data, or sensitive endpoint errors.
