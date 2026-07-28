## Why

Operators currently configure the GDT bridge twice: the application stores a container-visible path while an optional `.env` controls the Windows bind-mount source. A Windows absolute path entered in the GDT page cannot become usable until an external deployment step recreates `lab-app`, so the current experience is both confusing and incomplete.

## What Changes

- Add a bounded localhost deployment controller that accepts one dedicated host GDT bridge root, validates and provisions it, persists deployment-owned state, and recreates only `lab-app`.
- Let the GDT UI display and edit the host absolute path, derive the documented bridge subdirectories, and expose explicit save/apply/restart progress.
- Keep `/data/gdt-bridge` fixed and hidden as the supported container-visible implementation path.
- Preserve typed GDT behavior settings separately from the deployment-owned host bind path.
- Retain `.env` compatibility as an advanced bootstrap/override path without requiring operators to edit it for normal GDT setup.

## Capabilities

### New Capabilities

- `healthcare-lab-gdt-host-path-controller`: Defines the bounded localhost control protocol, path safety, deployment-state persistence, and `lab-app` recreation behavior.

### Modified Capabilities

- `healthcare-lab-gdt-bridge-settings`: Changes host bind-mount information from read-only deployment metadata into an explicitly applied GDT setup operation while keeping the application path fixed.
- `healthcare-lab-container-release`: Adds controller lifecycle and persistent deployment state to the supported wrapper without requiring `.env` or Compose YAML edits.

## Impact

Affected areas include the GDT Settings/console frontend, GDT deployment metadata APIs, a new Windows host-side controller, `deploy/lab.ps1`, Compose interpolation, deployment-state persistence, diagnostics, tests, and release documentation. The controller crosses the browser/host/container boundary and therefore requires strict origin, request, path, logging, and mutation limits.
