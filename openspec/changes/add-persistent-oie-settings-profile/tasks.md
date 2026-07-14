## 1. Persistence Model

- [x] 1.1 Add additive SQLite tables for the singleton OIE settings profile and managed Channel mappings.
- [x] 1.2 Seed the confirmed local Management API, credential, timeout, TLS, and result listener defaults only when the profile is absent.
- [x] 1.3 Add store methods that read and atomically update the profile and replace its managed Channel mappings.
- [x] 1.4 Ensure store response serialization exposes `passwordConfigured` but never the stored password.

## 2. Validation And Secret Handling

- [x] 2.1 Validate the Management API HTTP(S) URL, required username and listener host, positive numeric timeout, and listener port range.
- [x] 2.2 Validate required managed Channel identity fields and reject duplicate logical types.
- [x] 2.3 Implement password update semantics: omission preserves, non-empty replaces, and empty or null rejects.
- [ ] 2.4 Audit new response and error paths so the password and request body are never logged or serialized.

## 3. Backend API

- [ ] 3.1 Add `GET /api/oie/settings` to return the persisted secret-safe profile.
- [ ] 3.2 Add `PUT /api/oie/settings` to validate and atomically save the full profile and mapping collection.
- [ ] 3.3 Keep persisted listener settings separate from current listener start, stop, status, and app-start behavior.

## 4. Verification

- [x] 4.1 Add store tests for local defaults, restart persistence, Channel mapping replacement, and duplicate logical-type rejection.
- [ ] 4.2 Add API tests for reads, valid updates, actionable URL/host/timeout/port errors, and atomic rejection.
- [ ] 4.3 Add secret-safety tests covering default masking, password preservation/replacement, empty-password rejection, and response/log exclusion.
- [x] 4.4 Add migration-compatibility coverage proving existing Patient, Order, and OIE Result records still load after initialization.
- [ ] 4.5 Run the focused Python test suite and strict OpenSpec validation.
