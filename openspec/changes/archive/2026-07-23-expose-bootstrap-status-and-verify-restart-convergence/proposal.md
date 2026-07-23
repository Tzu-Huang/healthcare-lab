## Why

Healthcare Lab can now create or recover its two approved OIE Channels during startup, but the asynchronous bootstrap result is discarded and operators cannot tell whether it is waiting, completed, timed out, partially failed, or was safely blocked. ZAC-69 must make that convergence observable and prove the behavior against the supported OIE 4.5.2 Docker Compose runtime without turning Settings reads into mutation triggers.

## What Changes

- Record and expose a secret-safe latest bootstrap run with mode, state, timestamps, attempts, bounded error category, recovery guidance, and per-logical-type outcomes.
- Add concurrency-safe explicit Retry behavior that reuses the guarded create-missing workflow only for recoverable bootstrap failures.
- Add bootstrap as its own Runtime Diagnostics layer, separate from HLAB listener auto-start and delivery health.
- Always present both approved managed templates in Settings, including missing and inventory-unavailable states, without mutating OIE during reads or browser refresh.
- Distinguish missing, created, unchanged/no-op, recovered, drifted, external, conflict, timeout, and failure evidence in the API and UI.
- Extend automated coverage and the live OIE 4.5.2 runbook/report for clean deployment, restart no-op, one-Channel repair, delayed readiness, and supported persistence-reset scenarios.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `healthcare-lab-oie-startup-bootstrap`: Require queryable run state, guarded Retry, explicit outcome semantics, and read-only status access.
- `healthcare-lab-oie-runtime-diagnostics`: Add an independently degradable bootstrap diagnostic layer with bounded guidance.
- `healthcare-lab-oie-settings-workspace`: Keep both canonical templates visible and present bootstrap status and Retry without read-triggered mutation.
- `healthcare-lab-oie-live-verification`: Require repeatable real-runtime convergence evidence for startup, restart, recovery, timeout, and persistence reset.

## Impact

- Backend bootstrap orchestration, application composition, operational persistence, OIE API mapping, and runtime diagnostics.
- Settings API client, state/view rendering, and operator actions.
- SQLite schema/repository tests, bootstrap/service/API/frontend tests, Docker Compose live verification, and operator documentation.
- ZAC-71 remains the owner of persisted operator configuration; bootstrap run evidence remains operational state rather than a competing configuration source.
