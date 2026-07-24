## 1. Zero-Edit Compose Contract

- [ ] 1.1 Add contract tests that render the supported Compose file with a deliberately absent repository-root `.env` and assert pinned images, local ports, volumes, networks, and safe defaults.
- [ ] 1.2 Remove the mandatory `lab-app` env-file injection and normalize Compose interpolation so direct repository-root startup succeeds without manual files.
- [ ] 1.3 Add bounded override fixtures proving documented image, host-port, bind-mount, service credential, and security-hardening values still interpolate correctly.
- [ ] 1.4 Add recreate-persistence coverage proving the instance database and GDT bridge content survive compatible `lab-app` replacement.

## 2. Supported Wrapper and Directory Provisioning

- [ ] 2.1 Add wrapper contract tests using a fake Docker command boundary for every supported action with and without a repository-root `.env`.
- [ ] 2.2 Make `deploy/lab.ps1` use absolute Compose inputs, conditionally pass only an existing `.env`, and report bounded failures without printing file contents or values.
- [ ] 2.3 Implement safe provisioning for the default repository-local instance/GDT directory contract before start and applicable restart actions.
- [ ] 2.4 Define and test exact-path safety behavior for an advanced GDT bind override, rejecting empty or broad targets without deletion, movement, or YAML edits.

## 3. Configuration Migration and Ownership

- [ ] 3.1 Add clean-install and legacy-upgrade tests covering missing environment input, eligible one-time bootstrap, invalid bootstrap rollback, and secret-safe evidence.
- [ ] 3.2 Add restart and container-recreate tests proving persisted typed profiles remain authoritative when environment values change or disappear.
- [ ] 3.3 Reduce `.env.example` to advanced deployment and explicitly documented compatibility-bootstrap inputs while keeping the closed ownership registry synchronized.
- [ ] 3.4 Add architecture tests preventing deployment-only settings from entering typed persistence and preventing migrated runtime consumers from regaining direct environment ownership.

## 4. Dashboard Settings Handoff

- [ ] 4.1 Add Dashboard markup and styles for an accessible, non-blocking incomplete-setup notice with bounded unavailable behavior.
- [ ] 4.2 Reuse the Settings readiness API during Dashboard activation and derive notice visibility and destination from `complete` and `nextAction`.
- [ ] 4.3 Extend registered navigation so the notice opens Settings at the owning section while guided setup refreshes authoritative readiness.
- [ ] 4.4 Add frontend tests for incomplete, complete, optional-disabled, unavailable, keyboard activation, no browser-storage cursor, and sensitive-value canaries.

## 5. Documentation and Verification

- [ ] 5.1 Rewrite root and deployment Quick Start instructions around zero-edit Compose/wrapper startup followed by application setup in Settings.
- [ ] 5.2 Document Advanced deployment overrides, one-time legacy bootstrap, persisted precedence, activation classes, local-only security defaults, directory behavior, backup, upgrade, and rollback.
- [ ] 5.3 Run focused Compose, wrapper, migration, settings, and frontend tests plus the complete regression suite and Python/JavaScript syntax checks.
- [ ] 5.4 Render Compose with clean and override fixtures, run secret-canary output checks, `git diff --check`, and strict OpenSpec validation.
