## Context

ZAC-15 originally asked for backend verification before adding a frontend OpenEMR/GDT status card. Since then, Healthcare Lab has added the single dashboard group, Docker Compose defaults, and group-level checks. The remaining work is narrower: make the backend check prove that the default OpenEMR/GDT runtime can actually read from OpenEMR and use the shared folder contract.

Existing useful pieces:

- `run_lab_smoke_check()` already returns structured smoke steps.
- `run_gdt_bridge_smoke()` already probes GDT folder write/read access.
- `run_http_smoke()` already validates OpenEMR HTTP reachability.
- `OpenEMRProcedureOrderSource` already owns DB config, PyMySQL connection creation, procedure-order query mapping, and missing-schema detection.

## Approach

Add a dedicated backend verify helper for the OpenEMR/GDT group and call it from the existing smoke/API path. The helper should return step dictionaries in the existing smoke format so operation history and API responses stay consistent.

Recommended step model:

| Step | Required | Healthy | Degraded | Down |
| --- | --- | --- | --- | --- |
| `openemr_http` | yes | HTTP responds with 2xx-4xx | - | connection/server failure |
| `openemr_db_connection` | yes | MariaDB connection opens | - | config, driver, auth, network, or connection failure |
| `openemr_order_schema` | yes | required query can execute | - | required table/query failure |
| `openemr_ecg_orders` | no | at least one matching ECG order | zero matching orders | unexpected query failure should be required failure via schema/query step |
| `gdt_folder_contract` | yes | required folders are present and writable/readable | - | required folder failure |

The implementation can use one query path for `openemr_order_schema` and `openemr_ecg_orders`: execute `OpenEMRProcedureOrderSource.list_orders()`, classify successful zero rows as Degraded, and classify connection/schema exceptions according to the failure source. If the current source class cannot distinguish connection from schema reliably, add a small verify method on that class rather than duplicating SQL elsewhere.

## Status Mapping

Healthcare Lab currently uses `Healthy`, `Degraded`, `Down`, and `Unknown`. The Linear issue uses `Unhealthy`; implementation should map that concept to existing `Down` unless the broader app intentionally changes vocabulary in a separate proposal.

## API Surface

Use the existing smoke/action response shape first. The developer-visible result should be available from the OpenEMR/GDT smoke/check path and include each sub-check message. A separate endpoint is optional only if the existing smoke response cannot represent the contract clearly.

## Risks

- OpenEMR initial startup may expose HTTP before MariaDB schema is ready. The verify result should report this as `Down` with a concrete DB/schema message, not hide it behind HTTP health.
- Empty clean installs may have no ECG procedure order. That should be visible as `Degraded`, preserving the distinction between a connected backend and missing test data.
- Local direct Flask startup may not have OpenEMR DB env vars. That should report `Unknown` or `Down` based on whether the OpenEMR/GDT smoke is expected to verify Docker runtime defaults in that mode.

