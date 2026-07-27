## 1. Clean-Start Secret Contract

- [x] 1.1 Add failing Compose and wrapper contract coverage for rendering a clean checkout with no `.env` and no optional application integration secret variables.
- [x] 1.2 Change the Compose secret/bootstrap inputs so omitted optional credentials do not block rendering or startup and do not create placeholder configured values.
- [x] 1.3 Verify a fresh database reports missing required credentials as secret-safe `configured: false` and `needs-setup`.

## 2. Valid dcm4chee Defaults

- [x] 2.1 Add regression coverage for the exact local dcm4chee defaults resolved by the supported Compose deployment.
- [x] 2.2 Align the default TLS verification value with the non-TLS local profile while retaining strict rejection of explicitly contradictory settings.
- [x] 2.3 Verify fresh application composition seeds the dcm4chee profile without an operator override.

## 3. Release Image Alignment

- [ ] 3.1 Identify and publish through the normal release workflow an immutable semantic-version image containing the Settings readiness API.
- [ ] 3.2 Update Compose, `.env.example`, release documentation, and version assertions to the verified image tag without changing existing immutable tags.
- [x] 3.3 Add or extend pulled-image verification to assert health and the stable `GET /api/settings/readiness` envelope.

## 4. Verification and Handoff

- [x] 4.1 Run focused typed-settings, dcm4chee, Compose, wrapper, container, and application-shell suites.
- [x] 4.2 Execute a collision-safe disposable no-env startup using synthetic data and record bounded evidence or a precise environment-dependent skip.
- [ ] 4.3 Re-run the ZAC-78 fresh-install gate and record whether ZAC-79 no longer blocks closure.
- [x] 4.4 Run OpenSpec strict validation and diff-hygiene checks.
