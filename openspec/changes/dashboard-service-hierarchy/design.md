## Context

The dashboard builds four logical groups from seeded lab-server records. Its action endpoint selects one primary record and passes one Compose service name to the operation adapter. This means dependency containers are absent from the response and parent Stop/Restart never coordinate them. The Docker-socket path also bypasses the service mappings in `deploy/lab.ps1`, so changing only the PowerShell map would not provide consistent behavior.

GDT is now implemented as a local workflow inside `lab-app`: it owns persistence, bridge folders, result import, and the watcher. OpenEMR is an optional legacy source, but Compose still provisions OpenEMR and MariaDB and makes `lab-app` depend on MariaDB.

## Goals / Non-Goals

**Goals:**

- Model external dashboard services and their allowlisted child containers explicitly.
- Provide consistent Docker-backed status and actions through both socket and CLI execution paths.
- Coordinate parent actions in dependency-safe order without making child actions control parents.
- Keep the local GDT workspace while removing OpenEMR from the default runtime and dashboard.

**Non-Goals:**

- Discover arbitrary Docker containers or expose untrusted container names as action targets.
- Add application-protocol health probes for Redis, PostgreSQL, or LDAP.
- Delete the optional OpenEMR integration code or migrate existing OpenEMR volumes.
- Make `lab-app` control its own lifecycle.

## Decisions

### Define service topology in the dashboard allowlist

Each primary group declares its primary Compose service and ordered child definitions. API identifiers and Compose service names are server-controlled rather than accepted directly from the client. This keeps the existing allowlist boundary and avoids persisting infrastructure-only children as editable lab-server records.

Alternative considered: seed every child into `lab_servers`. Rejected because database/LDAP containers are deployment components, not protocol endpoints, and the editable server model would blur those roles.

### Return child runtime state with each dashboard item

The dashboard response will include child identifiers, display names, roles, state/status, and capabilities. Runtime state comes from Docker container inspection; unavailable Docker access produces `Unknown` without inventing HTTP checks.

### Add a child action route and a batch parent operation

Child actions use a nested dashboard route scoped by parent and child identifiers. Parent actions resolve a fixed ordered list: Start operates children before primary, Stop operates primary before children, and Restart restarts children before primary. The operation layer accepts allowlisted Compose service names and records the parent operation result while returning per-target output.

Child actions target exactly one child. They never issue a start/stop/restart request for the parent. A child failure can naturally degrade the parent application, but that is observed health rather than reverse control.

### Keep GDT as a workspace, not a dashboard server

The OpenEMR/GDT dashboard row and its ECG Order shortcut are removed. GDT remains accessible through its dedicated navigation/workspace and retains watcher controls. The default Compose file removes OpenEMR, MariaDB, their volumes, environment wiring, and `lab-app.depends_on`; optional OpenEMR application code remains dormant when not configured.

## Risks / Trade-offs

- [Docker access is unavailable] → Return `Unknown`, disable unsupported controls through existing availability handling, and preserve clear diagnostic messages.
- [A multi-target parent action partially fails] → Stop subsequent unsafe steps, return target-level output, and record a failed operation for visibility.
- [Existing OpenEMR users rely on the bundled Compose services] → Treat removal as a documented default-runtime breaking change; they can retain the prior Compose definitions or configure an external OpenEMR instance.
- [Container display names vary by Compose project prefix] → Resolve containers by Compose service label and expose stable short display names such as `medplum-redis-1`.

## Migration Plan

1. Deploy the updated application and Compose definition.
2. Recreate the Compose project; obsolete OpenEMR containers are no longer part of the default topology.
3. Preserve existing named volumes unless operators deliberately remove them.
4. Roll back by restoring the previous Compose file and application version; retained volumes allow OpenEMR services to be recreated.

## Open Questions

None.
