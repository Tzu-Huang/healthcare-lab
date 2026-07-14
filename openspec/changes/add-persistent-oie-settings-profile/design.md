## Context

Healthcare Lab stores its durable local workflow state in SQLite through `DemoStore`. OIE order and result-listener endpoints currently take their defaults from environment-backed Flask configuration, while no Management API credentials or managed Channel identities are persisted. Later OIE Settings work needs one backend-owned profile without changing the existing Patient, Order, or OIE Result model.

The local-lab credential is deliberately simple and case-sensitive (`admin` / `Admin`). It is still a secret: callers may replace it, but read APIs and logs must never disclose it. This change creates the settings contract only; consuming it to call OIE, manage Channels, or auto-start the listener remains future work.

## Goals / Non-Goals

**Goals:**

- Persist one local OIE profile and its managed Channel mappings across app restarts.
- Provide stable read/update API shapes with clear validation failures.
- Make password updates write-only and prevent secret disclosure in responses and logs.
- Add the schema without rewriting or invalidating existing Healthcare Lab records.

**Non-Goals:**

- Call or authenticate to the OIE Management API.
- Create, update, deploy, enable, or disable OIE Channels.
- Start or reconfigure the running HLAB result listener.
- Build the Settings UI or introduce production secret-management infrastructure.

## Decisions

### Store the profile and Channel mappings in additive SQLite tables

Add a singleton `oie_settings_profiles` row keyed by a stable local profile name and child rows in `oie_managed_channel_mappings`. A unique `(profile_id, logical_type)` constraint prevents two mappings from claiming the same role.

Separate mapping rows are preferred over one JSON column because later Channel lifecycle work will need to find and update individual logical mappings. Reusing `lab_servers` was considered, but its generic health and operation fields do not model credentials, listener intent, or Channel identity cleanly.

### Seed one local profile without modifying existing workflow data

On database initialization, create missing tables and insert the local profile only when it does not exist. Defaults are:

- Management API base URL: `http://oie:8080`
- Username/password: `admin` / `Admin`
- TLS verification: disabled
- Management request timeout: 10 seconds
- Result listener: `0.0.0.0:6665`, MLLP enabled, auto-start enabled

Existing environment-backed OIE order sending and listener runtime behavior remain unchanged in this change. The persisted `autoStart` value expresses future desired behavior; initialization must not start the listener.

### Use one GET and one full-profile PUT endpoint

Expose `GET /api/oie/settings` and `PUT /api/oie/settings`. PUT validates the complete non-secret profile and replaces the submitted managed Channel mapping collection atomically.

A full update is preferred over an implicit nested merge because omitted mappings would otherwise have ambiguous deletion semantics. If `password` is omitted, the stored password is preserved. A non-empty `password` replaces it. An empty or null password is rejected; explicit secret clearing is outside this change.

### Keep the password write-only

The password is stored in the local SQLite profile because this lab does not yet provide an external secret store. Store methods must build response dictionaries explicitly and return `passwordConfigured` rather than the stored value. Validation errors and logs must not include request bodies or secret values.

Database encryption or a secret reference was considered, but without an independently managed key it would add complexity without materially protecting this local-lab deployment. The table boundary allows a later secret-reference strategy without changing the public API.

### Validate before opening the write transaction

The Management API URL must use HTTP or HTTPS and include a host. Username and listener host are required. Timeout must be a positive numeric value, and listener port must be an integer from 1 through 65535. Each Channel mapping requires a non-empty logical type and Channel name; Channel ID, template version, and last known revision may be empty until deployment occurs.

All validation completes before the profile and mappings are updated, so a rejected request leaves the previous settings intact. Error messages name the invalid field and expected format or range.

## Risks / Trade-offs

- [Risk] The default `http://oie:8080` works inside Docker but not for every direct host-run setup. → Mitigation: the profile is immediately editable through the update API.
- [Risk] A plaintext local SQLite password can be read by anyone with database-file access. → Mitigation: treat the database as restricted local state, never expose the secret through APIs or logs, and preserve a future secret-reference migration path.
- [Risk] Replacing all Channel mappings in one PUT can remove an omitted mapping. → Mitigation: document full-replacement semantics and return the complete saved collection after update.
- [Risk] Persisted listener settings may drift from the currently running listener until later integration work. → Mitigation: this change clearly treats them as desired configuration and does not claim runtime application.

## Migration Plan

1. Create the two missing tables during normal `DemoStore` initialization.
2. Seed the singleton local profile and no managed Channel mappings only when absent.
3. Leave existing Patient, Order, OIE Result, and other workflow tables untouched.
4. Verify a database populated with legacy records initializes and returns those records unchanged.

Rollback removes the new code and endpoints while leaving the additive tables harmlessly unused; no existing data rollback is required.

## Open Questions

None. The local defaults, SQLite secret storage, and password-update behavior were confirmed during exploration.
