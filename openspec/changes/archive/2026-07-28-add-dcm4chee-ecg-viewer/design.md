## Context

The dcm4chee result browser already renders Study/Series/Instance actions from persisted result projections. Separate backend work now provides result-ID-scoped ECG metadata and SVG routes that retrieve through the authoritative dcm4chee profile, normalize DICOM waveform data, and return disclosure-safe errors. The missing layer is a small browser-owned page that connects eligible instance results to those APIs.

The viewer must preserve the generic dcm4chee Web UI action, work on direct navigation and reload, avoid exposing upstream retrieval details, and distinguish an explicitly supported ECG instance from a generic DICOM result associated with an ECG order.

## Goals / Non-Goals

**Goals:**

- Offer `View ECG Graph` only when a result projection explicitly reports ECG rendering capability and has a persisted result ID.
- Provide a stable `/viewer/ecg/<result-id>` page that loads result-scoped metadata and SVG output.
- Present loading, successful graph/summary, unsupported, missing, and upstream failure states accessibly.
- Keep feature code modular and testable within the existing Flask, JavaScript, template, and CSS structure.
- Preserve all existing artifact, generic viewer, and retrieve actions.

**Non-Goals:**

- Fetch DICOM or WADO-RS directly from the browser.
- Infer ECG support from patient association, order code, modality alone, or user-controlled URLs.
- Add waveform parsing, calibration, rendering algorithms, persistence, or a diagnostic-grade ECG interface.
- Replace or embed the dcm4chee Web UI.

## Decisions

### Use a server-rendered viewer shell with result ID in the path

Flask will serve a focused template for `/viewer/ecg/<result-id>`. The template exposes only the result ID and application-owned API route shapes to a dedicated JavaScript module. Direct navigation and reload therefore reconstruct state without relying on the originating result-browser tab.

Alternative considered: a client-side modal in the main application. Rejected because it does not provide a stable direct URL, couples viewer lifecycle to the console, and makes reload/new-tab behavior harder to reason about.

### Treat backend capability as the eligibility authority

The result projection must carry an explicit display-safe ECG capability derived from persisted instance identity and backend support. The action helper will require that capability plus a result ID; it will not derive support from `modality`, order association, labels, or the presence of a generic viewer URL.

Alternative considered: show the action for every `ECG`-looking order or DICOM row and let the viewer fail. Rejected because it creates a misleading working action and violates the result-scoped capability boundary.

### Load metadata and SVG through application-owned endpoints

The viewer module first requests `/api/dcm4chee/results/<result-id>/ecg` to obtain safe summary data, then points an image/object presentation at `/api/dcm4chee/results/<result-id>/ecg/render.svg`. It never constructs or reveals WADO-RS URLs. Metadata success does not suppress a later graph-load failure; each phase owns a controlled state.

Alternative considered: fetch SVG bytes and inject markup. Rejected because an application-owned image URL is simpler, avoids DOM injection, and retains browser-native SVG loading behavior.

### Keep viewer state explicit and accessible

The page will have named loading, content, and error regions with a live status message. Success shows the graph and lead/sample-rate/unit/duration summary. Error mapping uses stable backend codes/statuses to distinguish unsupported content from missing results and upstream failures without displaying raw exception text.

### Reuse the secure new-window helper

`View ECG Graph` will use the existing action helper that calls `window.open(url, "_blank", "noopener")`. The new action is additive; `Open Viewer`, artifact, and retrieve actions remain unchanged and keep their current targets.

## Risks / Trade-offs

- [Result projections omit or stale-cache capability] → Hide the action by default and let direct viewer navigation return the backend's controlled current result.
- [Metadata succeeds but SVG loading fails] → Keep graph loading/error handling separate and show a stable retry-safe failure message.
- [Very large SVG affects browser responsiveness] → Rely on existing bounded WADO retrieval/rendering contracts and keep the viewer page otherwise minimal.
- [Backend error shapes evolve] → Map known stable codes/status families and use one disclosure-safe fallback message.
- [New standalone page drifts from application styling] → Use a small feature stylesheet layered on existing base tokens rather than duplicating the main shell.

## Migration Plan

1. Add the viewer route/template, modular API/view JavaScript, and scoped CSS.
2. Add capability-gated result actions after the route is available.
3. Verify direct navigation, reload, secure new-window behavior, and all controlled states with automated tests.
4. Roll back by removing the additive action and viewer assets/routes; existing generic viewer/retrieve behavior requires no data migration.

## Open Questions

- Confirm the exact display-safe capability field name projected onto each persisted result row; prefer the backend's existing metadata contract rather than introducing a second inference rule.
- Confirm whether duration is returned directly by the metadata API or derived from sample count and sampling frequency in the viewer adapter.
