## 1. Persisted Profile Evolution

- [ ] 1.1 Extend the closed Medplum profile with `webUiUrl`, `timeoutSeconds`, canonical URL normalization, and bounded numeric validation.
- [ ] 1.2 Add an idempotent persisted-profile schema migration that preserves existing public values and the client secret.
- [ ] 1.3 Extend one-time environment bootstrap and Docker-local defaults without reseeding existing profiles.
- [ ] 1.4 Add domain, repository, and service tests for bootstrap migration, restart preservation, secret rotation, blank preservation, explicit removal, and invalid fields.

## 2. Effective Runtime Ownership

- [ ] 2.1 Introduce an application-composed Medplum runtime provider for effective enabled settings, timeout, and reusable in-memory authorization.
- [ ] 2.2 Invalidate cached authorization state when authentication-relevant effective settings change while preserving reuse for an unchanged profile.
- [ ] 2.3 Apply the persisted timeout and secret-safe exception translation to metadata, token, read, and write requests.
- [ ] 2.4 Route Patient, Order, retry, FHIR preview/sync, live inventory, DiagnosticReport, and related-resource operations through the runtime provider.
- [ ] 2.5 Add focused tests proving immediate post-save use, token reuse/invalidation, timeout behavior, disabled behavior, and shared Patient/Order/FHIR ownership.

## 3. Health, Smoke, and Inventory Compatibility

- [ ] 3.1 Derive Medplum inventory application and browser presentation from the effective typed profile while keeping deployment controls compatible.
- [ ] 3.2 Route Medplum health and smoke checks through the effective profile and remove hard-coded or inventory-owned workflow decisions.
- [ ] 3.3 Add architecture and integration tests that reject competing Medplum URL or credential sources.

## 4. Save-and-Test Diagnostics

- [ ] 4.1 Implement a bounded Medplum diagnostic service with independent metadata, OAuth token, and authenticated `_count=1` FHIR read stages.
- [ ] 4.2 Add a typed API operation that saves a valid profile first and then returns partial, stable, value-free diagnostic results.
- [ ] 4.3 Add API and service tests for wrong URL, token failure, missing credentials, successful authenticated access, disabled profiles, partial results, and persisted-save behavior after test failure.
- [ ] 4.4 Add canary tests proving secrets, tokens, authorization headers, upstream bodies, and FHIR resources never appear in responses, logs, diagnostics, or audits.

## 5. Modular Medplum Settings UI

- [ ] 5.1 Replace the Medplum placeholder with accessible controls for enabled state, internal FHIR URL, browser Web UI URL, OAuth fields, refresh grace, and timeout.
- [ ] 5.2 Implement the feature-owned Medplum Settings API/view module with load, save, blank-secret preservation, configured-state display, and explicit secret removal.
- [ ] 5.3 Implement Save-and-test interaction with separate saved-state confirmation and metadata, OAuth, and authenticated-read result cards.
- [ ] 5.4 Add focused frontend/template tests for field ownership, labels, validation mapping, single initialization, secret behavior, partial diagnostics, and narrow responsive layout.

## 6. Verification and Documentation

- [ ] 6.1 Update configuration ownership and operator documentation for canonical Medplum settings, activation behavior, safe defaults, and deployment-only boundaries.
- [ ] 6.2 Run focused typed-settings, Medplum client, workflow, health/smoke, API, frontend, architecture, and security regression suites.
- [ ] 6.3 Run the full repository verification command and record passing evidence before review.
