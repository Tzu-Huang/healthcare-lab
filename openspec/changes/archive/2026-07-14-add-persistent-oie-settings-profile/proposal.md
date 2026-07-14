## Why

Healthcare Lab currently reads OIE listener settings from runtime environment values and has no durable configuration shared by OIE administration, managed Channel lifecycle work, and the HLAB result listener. A persistent, secret-safe backend contract is needed before those later OIE Settings features can be implemented.

## What Changes

- Add one persisted local OIE settings profile containing the Management API base URL, username, write-only password, TLS verification mode, and request timeout.
- Add persisted HLAB result listener settings for host, port, MLLP framing, and the desired auto-start state.
- Add persisted managed Channel mappings for logical type, OIE Channel ID, Channel name, template version, and last known revision.
- Add backend APIs to read and update the profile with actionable URL, host, timeout, and port validation.
- Seed local-lab defaults, including case-sensitive credentials `admin` / `Admin` and listener defaults `0.0.0.0:6665` with MLLP and auto-start enabled.
- Keep the password write-only: API responses expose only whether a password is configured, and application logs must not expose the secret.
- Preserve all existing Patient, Order, and OIE Result records and workflows during database initialization and migration.

## Capabilities

### New Capabilities

- `healthcare-lab-oie-settings-profile`: Define persistence, defaults, validation, secret handling, managed Channel mappings, and read/update APIs for the shared OIE settings profile.

### Modified Capabilities

None.

## Impact

- Affected code: `backend/lab_store.py`, `app.py`, and focused tests in `tests/test_lab_store.py` and `tests/test_app.py`.
- Affected APIs: new OIE settings read/update endpoints under `/api/oie/settings`.
- Affected persistence: additive SQLite tables for the profile and its managed Channel mappings; existing clinical and OIE result tables remain unchanged.
- No OIE Management API calls, Channel creation/deployment, listener startup behavior, or Settings UI are included.
