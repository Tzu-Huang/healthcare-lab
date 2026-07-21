## Context

ZAC-45, ZAC-48, and ZAC-49 supply the persistence, Management API client, managed-Channel templates/lifecycle, and listener runtime needed by ZAC-50. The modular frontend also reserves Settings owners, but the current merged Settings files contain overlapping listener and Channel implementations, duplicate declarations, malformed strings, and incomplete markup. The change must first consolidate those files, then expose a coherent operator workflow without weakening the safety contracts beneath it.

The Settings workspace serves a local lab operator. OIE credentials are sensitive, external Channels are outside Healthcare Lab ownership, OIE revisions can change concurrently, and listener settings can differ from the socket currently bound by the process. Browser verification must use controlled doubles rather than requiring OIE, Docker, or a listener port.

## Goals / Non-Goals

**Goals:**

- Provide one responsive Settings workspace for OIE connection, HLAB listener intent/runtime, and managed-Channel lifecycle.
- Keep passwords write-only and return actionable, classified connection and operation failures.
- Make saved listener intent and actual runtime state visibly distinct.
- Offer constrained managed-Channel edits and single-target operations only after state-bound preview.
- Repair and consolidate the existing Settings modules without moving business behavior back into catch-all assets.

**Non-Goals:**

- Generic OIE administration, arbitrary connector design, raw JSON/XML, transformer, filter, or script editing.
- External-Channel mutation, automatic adoption, force/override, bulk operations, or redeploy-all.
- Automatic listener restart on Save, automatic Docker configuration changes, or multi-process listener coordination.
- Message search, manual result fetch, or changes to Patient, Order, and ORU processing semantics.

## Decisions

### Consolidate the existing modular owners before adding behavior

The change will retain `api/settings.js`, `state/settings.js`, `components/settings-shell.js`, `views/settings.js`, the Settings template, and Settings CSS as the named owners, remove accidental duplicate/overlapping content, and keep `app.js`, `styles.css`, and `index.html` as thin compatibility/loading entrypoints. This makes the merge repair part of the feature rather than creating another temporary Settings implementation.

Building a second view alongside the damaged one was rejected because duplicate state and event ownership would make listener and lifecycle behavior nondeterministic.

### Add one secret-safe connection-test application operation

A Settings-facing service/API operation will construct the Management API client from persisted private configuration, authenticate, read current-user and system/version data, classify failures using existing OIE error categories, close the session, and return only bounded presentation fields. The test uses the saved password unless the user first saves a replacement; password text is never echoed back or included in diagnostics.

Calling low-level OIE endpoints independently from the browser was rejected because it would duplicate session handling and expose transport details. Testing an unsaved password inline was rejected for the first release because it complicates secret lifetime and makes Test semantics ambiguous.

### Separate persisted listener intent from runtime controls

Save remains persistence-only. The listener section renders saved host, port, framing, and auto-start beside explicit runtime state, effective/attempted endpoint, and degraded error. Start, Stop, and Retry call their existing process-local endpoints and then refresh status. A mismatch remains visible until status confirms the saved intent is applied.

Implicitly restarting on Save was rejected because it can interrupt in-flight delivery. Treating Save success as runtime success was rejected because the socket may still use the previous endpoint.

### Constrain Channel editing to template-owned route and transport fields

Edit opens a structured form for the approved source endpoint, destination endpoint, and bounded timeout/retry fields represented by the managed template. Saving edits updates desired Settings/template inputs; Apply requests an update preview and shows owned-field differences before execution. Raw payloads and unowned OIE fields never cross the UI editing boundary.

A generic Channel form was rejected because it would duplicate OIE Administrator and undermine ownership-preserving merge behavior. Treating Edit and Apply as the same immediate mutation was rejected because every write requires preview.

### Present lifecycle operations through one preview controller

Create, Apply, Deploy, Redeploy, Undeploy, Delete, and Recreate use the same selected logical type, preview result, bounded token, busy state, and fresh-preview recovery. Recreate is the UI label for Create after a previously mapped Channel is missing. Redeploy is a new single-target lifecycle operation that revalidates ownership/revision and performs bounded undeploy then deploy steps; it never calls redeploy-all.

Delete confirmation uses the exact displayed Channel name. The preview also displays Channel ID, exact route, deployment implications, and ordered expected steps. This aligns the destructive action with what the operator can see while the token continues to bind the actual identity and revision.

### Derive warnings and action availability from explicit state

The UI does not infer ownership or invent actions. It renders lifecycle classification, deployment status, permitted actions, owned differences, blocking reasons, and last bounded operation outcome from API projections. External items have no mutation controls. Changing the HLAB listener port produces a warning that the ORU destination, exposed port/firewall, and listener process may require coordinated work, but the UI does not edit Docker files.

### Verify with modular and browser-level controlled doubles

Pure module tests cover state and rendering decisions; Flask API/service tests cover secret-safe connection results and lifecycle extensions; Playwright exercises navigation, save/test, runtime actions, read-only external cards, previews, stale tokens, delete confirmation, and responsive layout against the test application. No verification requires live OIE or real listener binding.

## Risks / Trade-offs

- [The Settings merge repair obscures functional changes] → Separate consolidation tasks and focused syntax/ownership checks before adding behavior.
- [Saved configuration passes validation but cannot connect] → Keep Save and Test distinct and show stable authentication, TLS, timeout, connection, version, permission, and response categories.
- [Listener and Channel ports become inconsistent] → Show the exact two routes and a coordinated-change warning; require explicit Channel Apply and listener Retry/restart.
- [Redeploy partially succeeds] → Return ordered undeploy/deploy step outcomes and require refreshed inspection before retry.
- [A Channel changes after preview] → Revalidate identity, revision, deployment state, and desired digest; reject with a fresh-preview requirement.
- [Operation controls overwhelm smaller screens] → Use responsive cards, grouped primary/secondary actions, and a single preview surface.

## Migration Plan

1. Consolidate the malformed Settings modules and restore focused frontend checks without changing public behavior.
2. Add the connection-test service/API contract and constrained lifecycle extensions behind existing composition seams.
3. Implement the connection and listener sections, then the managed/external Channel inventory and preview controller.
4. Add constrained editing, single-target redeploy, Channel-name delete confirmation, warnings, and responsive verification.
5. Deploy without schema migration. Rollback removes the new UI/API surface while retaining existing persisted settings, mappings, audits, and listener behavior.

## Open Questions

None. The first release uses saved credentials for Test Connection, exposes only template-owned Channel fields, defines Redeploy as a single-target undeploy/deploy sequence, and confirms Delete with the displayed Channel name.
