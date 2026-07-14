## Why

The dashboard currently presents logical workflow groups as flat services and only controls each group's primary container, which hides runtime dependencies and makes start/stop behavior incomplete. OpenEMR is also still provisioned as part of the default GDT stack even though the active GDT workflow is local and OpenEMR-independent.

## What Changes

- Replace the four dashboard service groups with three external primary services: OIE, Medplum, and dcm4chee.
- Add expandable, allowlisted sub-service rows for Medplum Redis/Postgres and dcm4chee LDAP/Postgres, with Docker-backed Check, Start, Stop, and Restart controls.
- Make primary Start, Stop, and Restart actions coordinate their declared sub-services in dependency-safe order while keeping child actions one-way and independent from the primary service.
- Keep OIE as a standalone primary service with no child rows.
- **BREAKING** Remove the OpenEMR/GDT service group and dashboard ECG Order shortcut; the dedicated GDT workspace remains available.
- **BREAKING** Stop provisioning OpenEMR and OpenEMR MariaDB in the default Docker Compose runtime, and remove the lab app's default dependency on that database.
- Preserve the local GDT bridge, watcher, order, and result workflows without requiring OpenEMR.

## Capabilities

### New Capabilities

- `healthcare-lab-dashboard-service-hierarchy`: Defines the dashboard primary/sub-service model, dependency-aware parent controls, independent child controls, and container status checks.

### Modified Capabilities

- `healthcare-lab-dashboard-gdt-order-flow`: Removes the dashboard service-row shortcut while preserving the focused GDT order workspace.
- `healthcare-lab-openemr-gdt-backend-verify`: Makes OpenEMR verification an optional integration rather than a dependency of the default runtime.

## Impact

- Dashboard service API payloads and action routes in `app.py` and `backend/dashboard_services.py`.
- Docker operation adapters and allowlists in `backend/lab_operations.py` and `deploy/lab.ps1`.
- Dashboard rendering and styles in `frontend/static/app.js` and `frontend/static/styles.css`.
- Default service topology in `deploy/docker-compose.yml` and related deployment documentation/configuration.
- Dashboard, operation-adapter, compose, and frontend contract tests.
