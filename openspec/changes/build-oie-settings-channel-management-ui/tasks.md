## 1. Consolidate the Settings Foundation

- [x] 1.1 Repair and consolidate the overlapping Settings template, API, state, component, view, style, and application initialization fragments into one valid modular ownership path.
- [x] 1.2 Restore focused Settings syntax, static-loading, initialization, navigation, and ownership tests before adding new behavior.
- [x] 1.3 Preserve existing listener reload-reminder behavior and managed-Channel preview safety while removing duplicate declarations and malformed presentation text.

## 2. OIE Connection Settings and Test

- [x] 2.1 Add a narrow Settings connection-test service that uses persisted private credentials, closes its OIE session, and projects only bounded version, current-user, TLS, status, and test-time fields.
- [x] 2.2 Expose the connection-test API with stable validation, TLS, authentication, permission, connection, timeout, unsupported-version, server, and unexpected-response errors that contain no secrets or raw upstream material.
- [x] 2.3 Implement the OIE Connection form for URL, username, write-only password replacement, TLS mode, timeout, Save, password-configured state, and connection-test results.
- [x] 2.4 Add service, API, repository-regression, and frontend tests for defaults, password preservation/replacement, successful testing, classified failures, and secret absence.

## 3. Listener Intent and Runtime Controls

- [x] 3.1 Render saved listener host, port, MLLP, and auto-start intent separately from stopped, running, or degraded runtime status and effective/attempted configuration.
- [x] 3.2 Wire Start, Stop, and Retry controls to refresh status while preserving persistence-only Save and process-local Stop semantics.
- [x] 3.3 Preserve the unapplied-intent reminder until runtime matches saved intent and add the listener-port warning covering the ORU route, Docker/runtime exposure, firewall, and Retry/restart work.
- [x] 3.4 Add controlled API and browser interaction coverage for matching, unapplied, stopped, running, degraded, retry-recovery, disabled-auto-start, and port-warning states.

## 4. Managed Channel Inventory and Editing

- [x] 4.1 Present the approved ORM and ORU routes with name, endpoints, ownership/classification, deployment, drift, revision, blocking reasons, and last-operation status.
- [x] 4.2 Present external Channels as read-only cards with no edit, lifecycle, adoption, force, override, bulk, or redeploy-all controls.
- [x] 4.3 Add structured editing and validation for only approved template-owned endpoint, timeout, queue, and retry fields without exposing raw payloads or unowned OIE fields.
- [x] 4.4 Persist desired edits through the existing Settings/template boundary and require an Apply preview before any OIE update.

## 5. Preview-Bound Channel Lifecycle

- [x] 5.1 Consolidate Create, Apply, Deploy, Undeploy, Delete, and Recreate into one preview controller with target, exact route, differences, expected steps, token, busy state, and fresh-preview recovery.
- [x] 5.2 Add a single-target Redeploy lifecycle operation that revalidates ownership/revision, performs bounded undeploy then deploy steps, reports partial failure, and never invokes redeploy-all.
- [x] 5.3 Change Delete to require the exact previewed display name, disclose Channel ID/route/undeploy implications, retain the logical template after success, and expose Recreate when Missing.
- [x] 5.4 Render success, failure, partial-failure, stale-preview, conflict, validation, revision, deployment, and runtime outcomes as actionable bounded messages and refresh inventory after execution.
- [ ] 5.5 Add domain, service, API, frontend module, and browser tests for all lifecycle actions, no-ops, stale revisions, external/conflict blocking, exact-name confirmation, partial failure, and recreation.

## 6. Responsive Integration and Quality Gate

- [x] 6.1 Complete responsive Settings layout, keyboard/label/status accessibility, action grouping, and narrow-viewport safety-information coverage without regressing existing sidebar views.
- [x] 6.2 Run focused Settings/OIE frontend, domain, service, API, runtime, composition, architecture, and integration suites using controlled doubles without live infrastructure.
- [ ] 6.3 Run full regression, JavaScript syntax, Python compile, diff, and strict OpenSpec validation checks and record verification evidence.
- [x] 6.4 Audit the final change for password/session leakage, raw payload exposure, external mutation, force/override/adoption, bulk operations, redeploy-all, implicit listener restart, and unintended schema or workflow changes.
