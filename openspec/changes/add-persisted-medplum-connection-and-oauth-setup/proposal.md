## Why

Medplum connection decisions are still split between persisted typed settings, legacy environment values, Lab Server inventory, and hard-coded health/smoke defaults. Operators need one browser-managed, secret-safe profile that takes effect immediately and can prove metadata reachability, OAuth authentication, and bounded FHIR access independently.

## What Changes

- Extend the persisted Medplum profile with distinct internal FHIR and browser Web UI URLs, enabled state, OAuth client configuration, refresh grace, and bounded request timeout.
- Complete one-time migration of eligible legacy Medplum environment values while preserving the persisted profile as authoritative after bootstrap.
- Add a modular Medplum Settings section with secret-preserving save, explicit secret removal, clear internal-versus-browser URL labels, and immediate activation guidance.
- Add “Save and test” diagnostics with independent metadata, OAuth token, and authenticated bounded FHIR-read results.
- Make Patient, Order, FHIR preview/sync, DiagnosticReport, health, smoke, and compatible inventory presentation consume the same effective persisted profile.
- Keep access tokens in memory only and keep credentials, tokens, authorization headers, and FHIR resource bodies out of logs and diagnostics.
- Do not create or manage Medplum ClientApplication resources.

## Capabilities

### New Capabilities

- `healthcare-lab-medplum-settings-profile`: Defines the canonical persisted Medplum connection, OAuth, runtime activation, diagnostics, and secret-safety contract.

### Modified Capabilities

- `healthcare-lab-settings-workspace`: Adds the operator-facing Medplum configuration and guided “Save and test” experience.
- `healthcare-lab-fhir-local-sync-foundation`: Requires all Medplum-backed Patient, Order, preview, synchronization, and DiagnosticReport reads to consume the same enabled effective profile.
- `healthcare-lab-typed-integration-settings`: Extends bootstrap and effective-settings ownership so health, smoke, inventory compatibility, and workflows cannot retain competing Medplum configuration sources.

## Impact

- Backend typed settings domain, persistence bootstrap, application composition, Medplum HTTP/auth clients, workflow providers, health/smoke orchestration, and Lab Server inventory projection.
- Typed Settings and Medplum diagnostic APIs, with stable value-free error and result envelopes.
- Modular Settings template, API, state/view module, styles, and focused interaction tests.
- Docker-local application defaults remain `http://medplum:8103/fhir/R4` internally and `http://127.0.0.1:3000` for browser navigation.
