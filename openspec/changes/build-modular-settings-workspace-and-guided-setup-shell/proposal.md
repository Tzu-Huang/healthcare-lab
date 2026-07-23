## Why

Healthcare Lab's Settings entry is still an OIE-specific operational screen, so users cannot understand overall integration setup progress or extend configuration one integration at a time. ZAC-71 now provides typed configuration ownership, making this the right point to establish a modular, secret-safe Settings workspace before later integration tickets add their forms.

## What Changes

- Replace the OIE-only Settings presentation with an accessible, responsive workspace containing Overview, Medplum, OIE, GDT Bridge, dcm4chee, AP / External Devices, and Deployment & Diagnostics sections.
- Preserve the existing OIE settings, listener, diagnostics, and managed-Channel safeguards inside an OIE-owned section.
- Introduce a shared frontend Settings module contract under which each integration owns its view, API adapter, state, and styling rather than extending one monolithic Settings script.
- Add a secret-safe setup-readiness API and view model with `ready`, `needs-setup`, `degraded`, `disabled`, and `restart-required` states derived from persisted configuration and bounded diagnostics.
- Add resumable first-run guidance, safe local defaults, optional-integration disabling, Advanced disclosures, and clear activation-impact labels.
- Add a top-level Run all checks action that delegates only to registered integration-specific bounded diagnostics.
- Exclude OpenEMR completely: it receives no Settings section, readiness provider, diagnostic registration, setup step, or extension contract in this change or its planned follow-on work.

## Capabilities

### New Capabilities

- `healthcare-lab-settings-workspace`: Defines modular Settings ownership, readiness aggregation, guided first-run behavior, activation-impact presentation, accessible navigation, and diagnostics orchestration.

### Modified Capabilities

- None.

## Impact

The change affects the Settings template, frontend module boundaries and styling, application navigation, a new backend readiness service/API, application composition, and frontend/API/service tests. Existing typed settings and specialized OIE APIs remain authoritative. It introduces no integration-specific persistence or forms, never returns secrets or PHI, does not rewrite Compose or restart services, and adds no OpenEMR behavior.
