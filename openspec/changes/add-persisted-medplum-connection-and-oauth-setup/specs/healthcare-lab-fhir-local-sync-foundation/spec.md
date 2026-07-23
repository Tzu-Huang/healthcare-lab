## ADDED Requirements

### Requirement: All Medplum-backed FHIR workflows share the effective profile
Healthcare Lab SHALL use the same enabled effective Medplum base URL, OAuth credential source, token policy, and timeout for Patient, Order, retry, FHIR preview and synchronization, live inventory reads, DiagnosticReport fetches, and related-resource fetches.

#### Scenario: Profile changes after application startup
- **WHEN** an operator saves a valid changed Medplum profile
- **THEN** the next Patient, Order, retry, preview, synchronization, DiagnosticReport, or related-resource request uses the changed profile
- **AND** no workflow continues using a startup-only environment snapshot

#### Scenario: A workflow fails upstream
- **WHEN** a shared-profile Medplum request is unauthorized, unavailable, timed out, or malformed
- **THEN** existing local-first ledger and retry behavior is preserved
- **AND** the surfaced error contains no authorization data or FHIR resource body
