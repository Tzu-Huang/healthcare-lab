## Why

Healthcare Lab can already call the OIE 4.5.2 management API and compile approved HLAB Channel templates, but it lacks the coordination layer that can reconcile those templates with live OIE state without overwriting another operator's work. A managed lifecycle is needed now so operators can safely preview and perform Channel creation, updates, deployment, undeployment, deletion, and recreation while preserving strict ownership and revision boundaries.

## What Changes

- Add lifecycle inspection that combines managed templates, persisted mappings, and live OIE inventory to classify each expected Channel as `Missing`, `Unchanged`, `Drifted`, or `Conflict`, while exposing unrelated Channels as external and read-only.
- Add deterministic previews for create, update, unchanged, and conflict outcomes before any mutation, including owned-field differences and the revision on which the preview is based.
- Add guarded create and update operations that revalidate ownership and current state immediately before mutation, retrieve the complete current Channel, preserve fields outside the approved edit surface, and always update with `override=false`.
- Add deploy and undeploy operations scoped to one explicitly identified managed Channel. Do not expose OIE's redeploy-all primitive; a safe single-Channel redeploy may only be added if the OIE contract supports it without affecting external Channels.
- Add guarded deletion that undeploys first, deletes only the explicitly identified managed Channel, clears its persisted OIE identity and revision, and retains its logical template mapping so it becomes `Missing` and can be recreated.
- Add structured success, failure, and partial-failure results with safe retry behavior and durable lifecycle audit events that contain neither secrets nor PHI.
- Add defense-in-depth against reckless or accidental “YOLO” operations: no startup mutation, no name-only ownership, no automatic adoption, no automatic conflict override, no bulk mutation, no wildcard target, no stale-preview execution, and no hidden destructive fallback.
- Add mocked lifecycle tests for classification, preview, create, idempotent update, drift, conflict, revision races, deploy, undeploy, delete, partial failure, and retry behavior.

## Capabilities

### New Capabilities

- `healthcare-lab-oie-managed-channel-lifecycle`: Safe reconciliation, preview, mutation, retry, and audit behavior for Healthcare Lab-managed OIE Channels.

### Modified Capabilities

- `healthcare-lab-oie-settings-profile`: Add targeted persistence operations for managed Channel identity/revision changes and durable lifecycle audit records without replacing unrelated settings.

## Impact

- Backend domain and service layers gain lifecycle state, preview, operation-result, and audit contracts plus a coordinator over the existing OIE management client and Channel templates.
- OIE API endpoints gain inspection, preview, and explicitly targeted lifecycle operations with stable error responses.
- SQLite schema and OIE settings repository gain targeted mapping updates and secret-safe lifecycle audit persistence.
- Application composition wires the lifecycle coordinator to existing settings, template, and management-client boundaries.
- Existing external OIE Channels remain read-only, and existing patient/order/result workflows are unaffected.
