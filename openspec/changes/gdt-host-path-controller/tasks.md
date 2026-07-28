## 1. Host Controller Foundation

- [x] 1.1 Extract shared GDT host-root normalization, safety validation, directory provisioning, and precedence logic from the deployment wrapper with unit contract coverage.
- [x] 1.2 Implement the loopback-only PowerShell controller with fixed status/apply schemas, strict origin/header/token authorization, redacted logging, and single-operation coordination.
- [x] 1.3 Add atomic controller-owned deployment-state and authorization-file management under an ignored host-local runtime directory.

## 2. Deployment Lifecycle

- [x] 2.1 Extend `deploy/lab.ps1` to start, inspect, and stop exactly one owned controller while preserving deterministic Compose invocation.
- [x] 2.2 Load process, `.env`, controller-owned, and default GDT path sources in documented precedence order and expose bounded ownership/conflict status.
- [x] 2.3 Implement asynchronous provision, persist, `lab-app` recreate, and post-restart diagnostics verification with recoverable terminal evidence.

## 3. Application and UI Integration

- [x] 3.1 Add secret-safe same-origin controller discovery/bootstrap metadata without treating deployment state as typed GDT profile data.
- [x] 3.2 Replace separate editable GDT inbox/outbox paths with one host-root control and derived read-only bridge paths.
- [x] 3.3 Implement explicit confirmation, apply progress polling, reconnect behavior across `lab-app` recreation, conflict guidance, and fallback wrapper instructions.
- [x] 3.4 Keep `/data/gdt-bridge` fixed in typed GDT settings and remove obsolete application-path editing behavior.

## 4. Verification and Documentation

- [x] 4.1 Add backend, frontend, controller, wrapper, Compose, security-negative, and ownership contract tests.
- [ ] 4.2 Verify clean start, retained restart, valid path change, watcher coordination, advanced-override conflict, controller restart, failed recreate, retry, and rollback on supported Docker Desktop for Windows.
- [x] 4.3 Update release and GDT operator documentation with the one-field workflow, controller trust boundary, precedence, diagnostics, fallback, and rollback procedures.
