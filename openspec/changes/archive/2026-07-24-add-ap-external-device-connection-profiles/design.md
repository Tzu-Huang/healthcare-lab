## Context

Healthcare Lab treats AP as the in-house ECG software that obtains work orders, combines ECG results, and returns integrated results. Today its HL7 destination is stored in OIE desired Channel fields, its GDT identity is stored in the GDT Bridge profile, and its DICOM station identity is embedded in the dcm4chee profile. The Settings workspace has an AP / External Devices placeholder but no owner or runtime projection.

The shared `integration_settings_profiles` table is intentionally unique by `profile_type`, so it represents one canonical profile per integration. ZAC-76 requires multiple named device profiles and one default per environment, which is a different aggregate and cardinality. Existing OIE preview/apply safeguards, GDT activation semantics, dcm4chee identity safety, and PHI-safe diagnostics remain authoritative.

## Goals / Non-Goals

**Goals:**

- Persist multiple AP/external-device profiles and resolve one enabled default for a requested environment.
- Reuse one device identity across enabled HL7, GDT, and DICOM protocol paths.
- Validate profile identity, ports, AE titles, conditional protocol completeness, uniqueness, and default conflicts atomically.
- Project effective values through explicit application services and make OIE drift visible as `apply-required`.
- Provide bounded diagnostics and last-interaction metadata without raw clinical payloads.
- Provide a modular Settings UI and readiness provider.

**Non-Goals:**

- Automatically previewing, applying, deploying, or redeploying OIE Channels.
- Replacing the OIE, GDT Bridge, or dcm4chee settings aggregates.
- Publishing host ports, changing Compose topology, or provisioning external devices.
- Storing or displaying raw HL7, GDT, DICOM, Patient, or Order content in diagnostics.
- Migrating historical messages or records when a device identity changes.

## Decisions

### Use a dedicated multi-profile aggregate

Add AP profile and safe observation tables with a repository dedicated to device cardinality and invariants. Do not relax `integration_settings_profiles.profile_type` uniqueness or encode a list inside one JSON payload. Dedicated rows allow transactional name/default constraints, stable identifiers, independent audits, and future profile lifecycle operations.

### Make environment explicit and normalize default selection

Each profile carries a normalized environment key. The repository enforces unique profile names and at most one default per environment in the same transaction that creates, updates, enables, disables, or selects a default. An effective resolver receives the environment explicitly from application composition. A disabled profile cannot be selected as effective; disabling the current default leaves the environment in `needs-setup` until another enabled default is selected.

### Keep protocol sections subordinate to one device identity

HL7, GDT, and DICOM sections each carry an enabled flag and protocol-specific values. Disabled sections may retain incomplete test metadata, while enabled sections must be complete. Common descriptive metadata is allowlisted and excludes credentials and clinical identifiers.

The HL7 section owns the AP MLLP endpoint and AP-side application/facility identity. The GDT section associates the device with a selected GDT Bridge profile and supplies device sender/receiver identity without overriding Bridge filesystem/lifecycle settings. The DICOM section owns the AP AE title, optional endpoint, MWL calling/station identity, and result-delivery role; archive called AE and archive endpoints remain dcm4chee-owned.

### Resolve immutable effective projections through application services

An application-scoped resolver returns an immutable snapshot for one operation. OIE, GDT, and dcm4chee adapters consume narrow protocol projections rather than reading AP persistence. This prevents each integration from independently merging environment and saved values.

### Treat AP-driven OIE changes as desired-state drift

The effective HL7 destination feeds only the approved ORM-to-AP desired projection. A changed host, port, or owned identity invalidates any stale desired comparison and reports `apply-required`. Saving an AP profile never calls lifecycle preview, execute, deploy, or redeploy operations. Existing state-bound preview tokens and ownership-safe mutations remain the only activation path.

### Bound and redact diagnostics

Connectivity checks use allowlisted protocol roles, short configured timeouts, and independent partial results. TCP reachability is reported only as transport reachability. Last-observed interaction records contain profile identifier, protocol, direction, timestamp, outcome code, and bounded correlation metadata; payloads and Patient/Order identifiers are rejected at the boundary.

### Give AP Settings independent ownership

The AP module owns its template/controller, API adapter, state, styles, CRUD/default actions, diagnostics, and readiness provider. Readiness is `disabled` when no AP workflows are enabled, `needs-setup` when selection or enabled protocol fields are incomplete, `apply-required` when OIE desired state differs, `degraded` after failed diagnostics, and `ready` otherwise.

## Risks / Trade-offs

- [Default selection can race] → Enforce selection and conflicting-default rejection inside one database transaction and test concurrent/stale mutations.
- [Existing settings contain overlapping AP values] → Bootstrap at most one compatibility profile when no AP profiles exist, then make persisted AP state authoritative and report conflicts explicitly.
- [Cross-integration projections can create hidden coupling] → Expose narrow immutable application-service ports and keep each integration’s persistence independent.
- [Connectivity checks may imply protocol success] → Label TCP-only checks `transport-reachable` and never infer HL7/DICOM application success.
- [Observation metadata can leak PHI] → Use a closed value-safe schema, reject unrecognized fields, and add sensitive-canary tests across APIs, logs, and audits.
- [A disabled default can silently route traffic] → Exclude disabled profiles from effective resolution and surface `needs-setup`.

## Migration Plan

1. Add idempotent AP profile, protocol configuration, audit, and safe-observation schema.
2. Seed one compatibility profile only when no AP profile exists, using eligible existing OIE/GDT/dcm4chee values without changing live integrations.
3. Add profile APIs, effective resolver, diagnostics, and readiness.
4. Migrate OIE, GDT, and dcm4chee consumers to narrow effective projections with characterization tests.
5. Replace the Settings placeholder and verify default selection, disabled/test profiles, drift, diagnostics, and privacy.
6. Roll back application code if necessary; additive AP tables remain unused and existing integration settings remain intact.

## Open Questions

- Confirm the production environment-key source and normalization rules before implementation.
- Confirm whether the first release needs device authentication material; this proposal intentionally excludes secrets until a protocol-specific requirement exists.
- Confirm which DICOM result-delivery roles are supported initially and whether AP host/port is required for every role.
