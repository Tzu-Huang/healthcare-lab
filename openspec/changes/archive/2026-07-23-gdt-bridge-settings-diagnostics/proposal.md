## Why

GDT Bridge runtime behavior is still configured through deployment/runtime details that operators cannot safely validate from Settings. With the typed settings boundary and modular Settings workspace now available, GDT can adopt those shared contracts while preserving the existing order/result workflow.

## What Changes

- Add a typed, persisted GDT Bridge profile for enabled state, application-visible shared path, GDT identities, filename binding, import-success behavior, poll interval, and stable-file interval.
- Add a GDT-owned Settings module that explains the fixed Docker application path separately from discoverable host bind-mount deployment information.
- Add bounded, PHI-safe filesystem and watcher diagnostics, including explicit bridge-directory provisioning and a generated empty-file write/delete probe.
- Move watcher and bridge runtime consumers to the effective persisted profile with deterministic startup and explicit immediate-reload versus `restart-required` outcomes.
- Preserve existing GDT order export, result import, and watcher behavior while applying the selected profile.

## Capabilities

### New Capabilities

- `healthcare-lab-gdt-bridge-settings`: Defines the typed GDT profile, Settings experience, bounded diagnostics, provisioning, and activation behavior.

### Modified Capabilities

- `healthcare-lab-gdt-bridge-console`: Makes bridge export, import, filename filtering, post-success handling, and watcher operation consume the effective persisted GDT profile.
- `healthcare-lab-settings-workspace`: Registers GDT readiness and diagnostics in the modular Settings shell and guided setup.
- `healthcare-lab-typed-integration-settings`: Adds GDT ownership, bootstrap, validation, and effective-profile behavior to the shared typed settings boundary.

## Impact

- Affects GDT profile persistence and APIs, application composition, watcher lifecycle, bridge filesystem services, and the GDT Settings frontend module.
- Extends readiness and Run all checks with GDT-owned providers.
- Documents `/data/gdt-bridge` as the supported Docker application path while keeping host bind-mount changes deployment-owned.
- Adds focused backend, API, watcher, filesystem, and frontend tests; no breaking API change is intended for existing GDT order/result workflows.
