## Context

Healthcare Lab currently loads a broad environment projection into Flask configuration. Medplum credentials are read from that projection while its FHIR base URL is stored in Lab Server inventory; dcm4chee and GDT profiles are constructed directly from configuration; OpenEMR connectivity is environment-backed; and OIE has a mature dedicated SQLite profile with validation, write-only password projection, atomic mutation, managed-Channel mappings, and value-free audits. Runtime services receive configuration mappings through composition, but several consumers still depend on the startup Flask configuration as their effective source.

ZAC-71 is the foundation for later integration-specific Settings issues. It must establish ownership, persistence, migration, secret, and consumer contracts without prematurely implementing all later Settings forms or collapsing distinct integration models into an untyped store.

## Goals / Non-Goals

**Goals:**

- Give every current configuration key one documented owner and activation/restart contract.
- Establish reusable typed profile ports, atomic persistence behavior, stable API projections/errors, one-time bootstrap, and value-free auditing.
- Make persisted effective settings available to HTTP and background consumers through application composition.
- Preserve and adapt the specialized OIE model rather than replacing it.
- Provide migration seams and tests that later Medplum, GDT, dcm4chee, OpenEMR, and AP Settings issues must consume.

**Non-Goals:**

- Redesign the Settings page or add complete integration-specific forms.
- Move image, host-published port, network, volume, bind mount, Docker socket, or container-database settings into application persistence.
- Restart containers, rewrite Compose YAML, or automatically apply deployment-only changes.
- Replace the existing OIE tables or weaken managed-Channel lifecycle ownership and concurrency rules.
- Introduce a production secret-management service or claim encryption at rest that the deployment does not provide.

## Decisions

### Define shared ports and typed registrations, not a generic settings bag

A small settings service will dispatch by a closed integration profile type to registered typed adapters. Each adapter owns its domain model, validation, public projection, private effective projection, bootstrap seed builder, and repository operations. The shared layer owns consistent command semantics, error envelopes, audit metadata, and composition-facing lookup. It will not expose arbitrary keys or accept unknown JSON fields.

Alternative considered: one generic `settings(key, value)` table. Rejected because it moves type safety and secret classification to callers, permits unsupported keys, makes atomic multi-field validation difficult, and recreates competing ownership.

### Add foundation persistence as typed profile records with explicit schema versions

New foundation-managed profiles will use a profile identity/type record and a typed, versioned payload boundary whose allowed fields are defined in code. Secret material will be stored separately from public payload fields so serializers cannot accidentally include it. Repository mutations validate a complete typed candidate before opening the write transaction, then update profile, secrets, and audit atomically. Integration-specific tables remain acceptable adapters; OIE continues using its current schema.

Alternative considered: create dedicated final tables for every later integration now. Rejected because later issues own their detailed form contracts, and premature tables would freeze fields before those designs are complete. The closed typed adapter and schema-version contract prevents an untyped dumping ground while allowing incremental integration tables or typed payload migrations.

### Make bootstrap create-only and record provenance

At database initialization, each registered adapter checks whether its persisted profile exists. Only a missing profile can be seeded from eligible environment values plus safe local topology defaults. The complete candidate is validated and committed with a bootstrap audit in one transaction. Presence of a profile, rather than comparison with defaults, is the durable marker that seeding has completed; restart never merges environment values into it.

Alternative considered: apply environment overrides on every startup. Rejected because UI changes would not be authoritative and restart behavior would vary by deployment shell.

### Model secret mutation as an explicit command

Secret input will be represented internally as preserve, replace(value), or remove rather than as a nullable string. Omitted and blank ordinary replacement inputs map to preserve; a distinct remove operation maps to remove. Public projections contain only configured state. Validation and exception construction must use field names and bounded categories, never submitted values.

Alternative considered: treat blank as removal. Rejected because an unchanged empty password field is the common Settings form submission shape and would cause accidental credential deletion.

### Separate public and effective projections

Adapters will expose a secret-safe public DTO for APIs and a private effective DTO for trusted consumers. Effective readers are injected through application composition and are usable by background workers without Flask request context. Consumers migrated by this change will no longer read the moved settings directly from `os.environ`, `current_app`, raw SQL, or Lab Server inventory when the ownership matrix assigns the value to a typed profile.

Alternative considered: let consumers call API serializers or access Flask configuration. Rejected because public DTOs cannot contain secrets and request-scoped configuration is unsuitable for background runtime work.

### Keep inventory and deployment metadata distinct from integration profiles

Lab Server inventory remains the operational registry for displayed services, health, and container actions. A runtime endpoint currently stored only in inventory must be migrated or projected from the typed owner according to the ownership matrix; it must not remain independently editable in two places. Compose-owned image, publication, network, and mount keys stay deployment-only.

Alternative considered: make `lab_servers` the universal settings store. Rejected because its generic host/base URL fields cannot represent integration-specific validation, secrets, protocol identity, or atomic profile semantics.

### Adapt OIE through its existing repository and service

An OIE adapter will implement the shared reader/mutation contract by delegating to the current OIE settings service and repository. Existing OIE initialization remains authoritative, existing endpoints remain compatible, and lifecycle mapping compare-and-update operations bypass generic whole-profile replacement exactly as they do now.

Alternative considered: migrate OIE rows into the new foundation storage. Rejected because it adds migration and lifecycle risk without improving the shared contract.

## Risks / Trade-offs

- [Risk] A versioned typed payload could drift toward arbitrary JSON. -> Require closed adapter registration, reject unknown fields and profile types, keep validators and migrations integration-owned, and add architecture tests forbidding generic key mutation.
- [Risk] Existing consumers continue reading old sources after ownership changes. -> Document every consumer in the matrix and add tests proving effective readers win after restart and operator override.
- [Risk] SQLite stores secrets without platform encryption. -> Keep secrets structurally separated and never projected or logged; document filesystem protection as the current deployment control and leave external secret storage as a future capability.
- [Risk] Bootstrap failure leaves ambiguous partial state. -> Validate first and commit profile, secret, provenance, and audit in one transaction.
- [Risk] Duplicated Lab Server and typed profile endpoints diverge. -> Assign one owner in the matrix and make any remaining inventory value a derived projection rather than a second writable source.
- [Risk] OIE adaptation changes lifecycle behavior. -> Delegate to existing specialized operations and run the full OIE settings/lifecycle regression suite.

## Migration Plan

1. Publish the ownership matrix and encode the closed profile/field classifications used by tests.
2. Add ordered SQLite migration(s), typed settings domain contracts, repository transactions, stable errors, and secret-safe audit storage.
3. Add create-only bootstrap using validated environment snapshots and safe defaults, with migration tests for clean, legacy, persisted-override, invalid-input, and rollback cases.
4. Compose public/effective settings services and migrate only the foundation-owned consumer seams required by this issue.
5. Add the OIE adapter and verify its existing API, secret, mapping, lifecycle, and startup contracts remain unchanged.
6. Roll back application code only after stopping writes from the new boundary; schema additions remain forward-compatible and existing OIE data is untouched.

## Open Questions

- Which non-OIE integration profile should be the minimal reference implementation proving the shared persistence path without absorbing a later form issue? The implementation proposal should prefer the smallest representative profile or an internal test profile if product scope would otherwise expand.
- Does the repository require application-managed encryption at rest now? The current issue requires leak prevention but does not specify a key-management source; absent one, the design will explicitly avoid claiming encryption and rely on deployment filesystem controls.
