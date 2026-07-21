## Why

Healthcare Lab already has persisted OIE settings, a safe managed-Channel lifecycle, and an auto-starting HLAB result listener, but operators do not yet have one coherent and usable Settings workspace for those capabilities. ZAC-50 completes that operator surface while preserving the existing ownership, revision, secret, and runtime-safety boundaries.

## What Changes

- Consolidate the partially merged Settings frontend into valid modular API, state, component, view, template, and style owners, with a sidebar entry separated from operational workspaces.
- Add an OIE Connection section for Management API URL, username, write-only password replacement, TLS mode, timeout, Save, and Test Connection results including connection state, OIE version, and current user.
- Add an HLAB Result Listener section that distinguishes saved intent from actual stopped, running, or degraded runtime state and exposes Start, Stop, and Retry without making Save restart the listener.
- Warn when listener changes remain unapplied and when a port change may also require managed-Channel, Docker/runtime, firewall, or process restart work.
- Add managed-Channel inventory cards for the two approved routes, including ownership, deployment, drift, revision, and last-operation status; keep external Channels read-only.
- Provide preview-bound Create, Apply, Deploy, single-Channel Redeploy, Undeploy, Delete, and Recreate flows. Delete requires the exact displayed Channel name and reports the exact affected route.
- Limit editing to approved template-owned fields and keep raw Channel JSON/XML, transformers, filters, arbitrary connectors, force, adoption, override, bulk mutation, and redeploy-all outside the UI.
- Add controlled backend and browser verification that does not require a live OIE runtime.

## Capabilities

### New Capabilities

- `healthcare-lab-oie-settings-workspace`: Defines the complete Settings operator workspace, connection testing and secret-safe presentation, listener intent/runtime controls, managed and external Channel presentation, constrained editing, route warnings, and guarded operation UX.

### Modified Capabilities

- `healthcare-lab-oie-managed-channel-lifecycle`: Add a safe single-target redeploy operation and align destructive confirmation with the exact displayed Channel name while retaining preview, ownership, and revision protections.
- `healthcare-lab-modular-frontend`: Advance the existing Settings foundation into the complete responsive ZAC-50 workspace and representative interaction coverage.

## Impact

- Backend service/API composition gains a Settings-facing OIE connection test and narrowly scoped lifecycle contract extensions; the low-level OIE client, persisted secret handling, listener runtime, and approved templates remain the underlying owners.
- Frontend Settings modules and CSS are consolidated and expanded; existing sidebar navigation and operational OIE behavior remain compatible.
- Focused service, API, frontend module, Playwright interaction, architecture, and regression tests cover success and classified failure paths using controlled doubles.
- No generic OIE Administrator replacement, raw payload editor, external-Channel mutation, message query, manual result fetch, automatic Channel mutation at startup, Docker file rewriting, or multi-replica listener coordination is introduced.
