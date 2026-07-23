# Settings workspace extension contract

The Settings page is a shell for integration-owned modules. The shell owns
section navigation, Overview readiness cards, guided resume, activation labels,
and the top-level bounded-check action. It does not own integration forms,
protocol state, or persistence.

## Frontend registration

`frontend/static/js/settings/registry.js` is the closed section registry.
Each product integration added after ZAC-72 must supply its own view/controller,
API adapter, state, and integration-specific styles. The outer
`frontend/static/js/views/settings.js` file remains a thin composition root.
OIE is the reference extraction in `frontend/static/js/settings/oie.js`.

Section identifiers and labels are stable:

- `medplum` — Medplum
- `oie` — OIE
- `gdt-bridge` — GDT Bridge
- `dcm4chee` — dcm4chee
- `external-devices` — AP / External Devices
- `deployment` — Deployment & Diagnostics

OpenEMR is intentionally not a Settings section or future registration target.

## Readiness providers

Providers return only a closed `ReadinessAssessment`. They must not return
configuration values, upstream payloads, exception messages, secrets, or PHI.
The allowed primary states are `ready`, `needs-setup`, `degraded`, `disabled`,
and `restart-required`. Activation impact is exactly `immediate`,
`application-restart`, or `container-recreation`.

`GET /api/settings/readiness` reads persisted intent and bounded local runtime
state. It must not initiate network checks. `POST /api/settings/readiness/checks`
delegates to explicitly registered bounded checks, isolates provider failures,
and preserves partial results.

Required sections complete setup only in `ready`. Optional sections complete
setup in `ready` or `disabled`. ZAC-72 treats GDT Bridge, dcm4chee, and
AP / External Devices as optional disabled placeholders until their owning
tickets introduce persisted enablement and diagnostics.

## Activation and diagnostics

Saved changes must be labeled as effective immediately, requiring an
application restart, or requiring container recreation. Presentation never
performs those actions. Diagnostics must use integration-owned timeouts and
return bounded categories and recovery guidance rather than raw failures.
