## 1. Typed GDT Profile

- [x] 1.1 Add the validated persisted GDT Bridge profile schema, repository registration, safe defaults, and idempotent migration.
- [x] 1.2 Add one-time legacy environment bootstrap and update the configuration ownership documentation for runtime, derived, and deployment-only GDT fields.
- [ ] 1.3 Add typed GDT profile read/update APIs with stable field errors, value-free audits, and activation metadata.
- [x] 1.4 Add profile persistence, validation, bootstrap, rollback, audit, and public-projection tests.

## 2. Effective Runtime and Watcher Lifecycle

- [x] 2.1 Compose an application-scoped effective GDT profile reader usable outside request context.
- [ ] 2.2 Migrate order export, result import, directory resolution, filename binding, and post-success handling to one effective profile snapshot.
- [ ] 2.3 Build a serialized watcher lifecycle coordinator with deterministic startup, immutable per-scan profiles, safe reload, and explicit `restart-required` outcomes.
- [ ] 2.4 Add compatibility and lifecycle tests for disabled mode, startup defaults, profile changes, reload/restart behavior, and existing order/result flows.

## 3. Filesystem Provisioning and Diagnostics

- [x] 3.1 Implement bridge-root confinement and explicit provisioning for documented inbox, outbox, processing, archive, error, and diagnostic directories.
- [x] 3.2 Implement bounded checks for root/mount existence, directory existence, read access, watcher state, and healthy empty folders.
- [x] 3.3 Implement the generated empty diagnostic-file write/delete probe with guaranteed cleanup and watcher exclusion.
- [x] 3.4 Add tests for missing paths, permission failures, path escape rejection, provisioning, probe cleanup failures, and PHI-safe output/logging.

## 4. Modular GDT Settings Experience

- [ ] 4.1 Register a GDT-owned Settings module with typed profile API adapter, state, accessible form, Advanced controls, and activation messaging.
- [ ] 4.2 Present `/data/gdt-bridge` as the supported Docker application path and optional discovered host bind-mount source as read-only deployment metadata.
- [ ] 4.3 Add explicit directory provisioning, bounded diagnostic actions, and watcher/readiness presentation to the GDT module.
- [ ] 4.4 Register the GDT readiness and diagnostic providers with guided setup and Run all checks while preserving optional-disabled completion behavior.
- [ ] 4.5 Add frontend/API tests for navigation ownership, form validation, disabled/readiness states, host/application path distinction, diagnostics, and keyboard accessibility.

## 5. Verification

- [ ] 5.1 Run focused GDT profile, filesystem, watcher, API, and Settings module tests and record passing evidence.
- [ ] 5.2 Run the existing GDT order/result and Settings regression suites and resolve compatibility failures.
- [ ] 5.3 Validate the OpenSpec change strictly and confirm diagnostics, errors, logs, and readiness expose no GDT contents or PHI-bearing filenames.
