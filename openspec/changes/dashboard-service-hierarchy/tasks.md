## 1. Dashboard Service Model and Operations

- [x] 1.1 Define the three primary service groups and their allowlisted child Compose services.
- [x] 1.2 Add Docker runtime inspection and independent child Check, Start, Stop, and Restart operations.
- [x] 1.3 Coordinate primary Start, Stop, and Restart across declared children in dependency-safe order.
- [x] 1.4 Add dashboard API payloads and nested child action routes with allowlist validation.

## 2. Dashboard User Interface

- [x] 2.1 Render expandable child service rows with stable names, runtime state, and action controls.
- [x] 2.2 Preserve expanded state and refresh affected primary/child status after actions.
- [x] 2.3 Remove the OpenEMR/GDT dashboard row shortcut while retaining dedicated GDT navigation and watcher controls.

## 3. Default Runtime Cleanup

- [x] 3.1 Remove OpenEMR, OpenEMR MariaDB, related volumes/environment wiring, and `lab-app.depends_on` from default Compose deployment.
- [x] 3.2 Update deployment helpers, environment examples, and documentation for optional OpenEMR and local GDT behavior.

## 4. Verification

- [x] 4.1 Add backend tests for hierarchy payloads, child allowlisting/state/actions, and dependency-safe parent operation order.
- [x] 4.2 Add frontend and Compose contract tests for expandable child controls and the three-service default topology.
- [x] 4.3 Run focused and full automated verification and resolve regressions.
