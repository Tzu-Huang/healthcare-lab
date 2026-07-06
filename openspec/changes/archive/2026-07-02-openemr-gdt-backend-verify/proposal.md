## Why

Healthcare Lab now has the OpenEMR/GDT dashboard group, Docker Compose defaults, and shallow health checks wired together. The remaining gap for ZAC-15 is that those checks do not yet prove the default backend runtime is actually connected behind the scenes.

Today the dashboard can mark OpenEMR reachable by HTTP and the GDT Bridge healthy by folder probing, but MariaDB connectivity, required OpenEMR order schema, and the OpenEMR procedure-order query are not represented as a required backend verification contract. This makes it hard to distinguish a truly working OpenEMR/GDT backend from a runtime where the visible services are up but order ingestion cannot work.

## What Changes

- Add a backend OpenEMR/GDT verification contract that returns structured steps for:
  - OpenEMR HTTP reachability.
  - OpenEMR MariaDB connection.
  - Required OpenEMR procedure-order schema/query readiness.
  - GDT shared-folder structure and write/read access.
- Reuse the existing `OpenEMRProcedureOrderSource` configuration and query path instead of adding a separate DB adapter.
- Treat MariaDB connection or required schema/query failures as required check failures.
- Treat a reachable DB with zero matching ECG procedure orders as a degraded verification result, not a hard backend failure.
- Expose the verify result through the backend smoke/API path so developers can inspect the structured details before any frontend status-card work.

## Non-Goals

- No frontend redesign or new operator-facing configuration fields.
- No automatic OpenEMR seed-data creation.
- No change from the current Healthcare Lab status vocabulary unless implementation needs a local mapping from issue language `Unhealthy` to existing `Down`.
- No migration of GDT AP workflow UI back into Healthcare Lab.

## Capabilities

### New Capabilities

- `healthcare-lab-openemr-gdt-backend-verify`: Define the backend verification behavior for the OpenEMR/GDT default runtime.

### Modified Capabilities

- None.

## Impact

- Affected code: Healthcare Lab smoke checks, OpenEMR procedure-order source, lab server operation responses, tests.
- Affected runtime: local Docker Compose default OpenEMR, OpenEMR MariaDB, lab-app GDT shared volume.
- Affected workflow: developers can run a backend verify/smoke action and see whether OpenEMR/GDT is healthy, degraded because no ECG orders exist, or down because a required backend dependency failed.

