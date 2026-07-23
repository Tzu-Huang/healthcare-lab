## Context

ZAC-35 established a dcm4chee connection-profile shape and the existing ADT, MWL, result-reconciliation, and viewer workflows, but the effective profile is still built from Flask startup configuration. ZAC-71 introduced typed persisted integration settings with secret-safe public projections and one-time bootstrap seams. ZAC-72 introduced a modular Settings shell, where dcm4chee currently remains an optional static-disabled placeholder.

The profile mixes operator-facing addresses (the browser Web UI URL) with application-facing endpoints (DICOMweb, HL7, and DIMSE). It also contains stable identity fields used in persisted mappings, plus authentication and mounted-file references that must never expose credential or private-key contents.

## Goals / Non-Goals

**Goals:**

- Establish one validated persisted dcm4chee profile as the canonical source for all runtime consumers.
- Preserve a ready-to-use built-in Docker profile while supporting external PACS endpoints.
- Provide an accessible dcm4chee Settings module with essential and Advanced fields.
- Report independent, bounded, redacted diagnostics and aggregate readiness.
- Keep bootstrap, update, audit, and public projections secret-safe and deterministic.

**Non-Goals:**

- Reading or mutating the dcm4chee database, LDAP configuration, archive storage, or Compose topology.
- Claiming DICOM or HL7 protocol success from a successful TCP connection.
- Returning password, token, certificate, or private-key file contents.
- Migrating existing Patient, Order, Study, or DICOM objects when an identity field changes.

## Decisions

### Register one named typed dcm4chee profile

Add a closed `dcm4chee` profile to the shared typed-settings registry. Its public payload contains enabled state, labels, URLs, endpoints, AE/HL7 identities, Patient assigning authority, viewer template, UID root, TLS/auth mode, username, token URL, certificate path, and private-key path. Credential values, when supported, use the existing write-only secret mutation contract; mounted certificate and key paths remain references and file contents are never read into API projections.

A separate dcm4chee persistence store was rejected because it would duplicate ZAC-71 validation, audit, bootstrap, and redaction behavior.

### Seed environment values once, then read persisted state

At startup, construct the built-in candidate from the same `DCM4CHEE_*` compatibility inputs used today and create it only if no persisted profile exists. Later environment changes do not overwrite operator intent. An application-scoped effective-profile reader supplies immutable snapshots outside request context.

Continuing to merge environment values on every read was rejected because it makes ownership ambiguous and allows deployment drift to override saved settings.

### Preserve stable identity explicitly

Profile name, Patient assigning authority, and UID root participate in durable identities and mappings. Validation accepts syntactically valid values, while updates that change an identity after dependent local records exist return a stable conflict requiring an explicit migration decision. The first implementation does not rewrite existing mappings.

Silently changing identity fields was rejected because it could split Patient, MWL, and Study namespaces.

### Use one effective projection across every workflow

Patient ADT sync, MWL create/readback, result reconciliation, viewer links, and diagnostics request a profile snapshot from the same reader at operation start. Compatibility adapters may translate the typed payload into the established ZAC-35 profile shape, but workflow services no longer construct their own profiles from Flask configuration.

### Separate operator-facing and application-facing validation

The Settings form labels the Web UI URL as browser-facing and all protocol endpoints as application-facing. Local Docker defaults use service-reachable application endpoints and a host-reachable Web UI URL. URL, port, AE title, TLS/auth combination, and mounted-reference readability checks return stable field codes without raw exception text.

### Keep diagnostics independent and bounded

The diagnostic service executes Web UI HTTP reachability, a minimal QIDO-RS metadata query, HL7 TCP reachability, and DIMSE TCP reachability as independent timeout-bounded checks. Each result uses allowlisted states and codes. TCP checks explicitly report `transport-reachable`, not protocol health, and partial failure remains visible.

### Register dcm4chee-owned readiness and UI

The dcm4chee module owns its view/controller, API adapter, state, styles, readiness provider, and bounded diagnostic provider. Disabled profiles report `disabled`; invalid or incomplete profiles report `needs-setup`; valid profiles with failed checks report `degraded`; and a valid effective built-in profile reports `ready`. The Settings shell only aggregates these projections.

## Risks / Trade-offs

- [Existing mappings make identity changes unsafe] → Detect dependent records and reject the update with stable migration guidance.
- [Browser and container network perspectives differ] → Label URL roles explicitly and seed Compose-safe application endpoints separately from the host-facing Web UI.
- [Connectivity checks can hang or leak upstream details] → Apply per-check timeouts, isolate failures, and map output to allowlisted codes.
- [Persisted intent can differ from an in-flight operation] → Capture one immutable profile snapshot per operation and apply changes to subsequent operations.
- [Mounted credential references can reveal sensitive infrastructure] → Return configured/readable state and bounded basename-free guidance rather than contents or raw filesystem errors.

## Migration Plan

1. Register the dcm4chee schema and idempotent missing-profile bootstrap.
2. Add typed profile APIs, validation, conflict handling, and public redaction.
3. Compose the application-scoped effective reader and migrate all dcm4chee consumers.
4. Add independent diagnostics and readiness registration.
5. Replace the Settings placeholder with the dcm4chee-owned module.
6. Verify built-in Docker defaults, external profiles, partial connectivity, disabled state, and regressions.
7. Roll back application code if needed; the additive persisted profile remains unused by the previous version.

## Open Questions

- Which auth modes require a stored write-only token/password versus a deployment-mounted reference in the first supported release?
- Should identity-field changes be unconditionally immutable after first save, or only blocked when dependent local records exist?
