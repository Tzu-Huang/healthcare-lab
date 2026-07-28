## Why

Healthcare Lab already exposes result-scoped ECG metadata and rendered SVG APIs, but users cannot reach them from the patient-centered dcm4chee result browser. ZAC-95 adds a focused viewer so supported ECG instances can be recognized and opened without exposing WADO-RS details, credentials, or misleading actions on generic DICOM results.

## What Changes

- Add a Healthcare Lab ECG viewer route addressed by persisted dcm4chee result ID, for example `/viewer/ecg/<result-id>`.
- Add an accessible `View ECG Graph` action to supported instance results while preserving existing artifact, generic viewer, and retrieve actions.
- Open the dedicated viewer in a new tab/window with `noopener`.
- Load the existing result-scoped ECG metadata and rendered SVG APIs, then show loading, graph, lead/sample-rate/unit/duration summary, and controlled unsupported/upstream failure states.
- Gate the action on explicit result-level ECG rendering capability and sufficient instance identity; patient/order association or generic DICOM modality alone is not enough.
- Keep the viewer small and application-owned, without displaying raw WADO URLs, internal endpoints, or credentials.
- Add focused frontend route, JavaScript, template, CSS, and automated coverage for action visibility, URL construction, secure window opening, reload/direct navigation, and viewer states.

## Capabilities

### New Capabilities

- `healthcare-lab-dcm4chee-ecg-viewer`: Defines result action eligibility, dedicated viewer navigation, ECG graph presentation, summary metadata, accessibility, and controlled viewer states.

### Modified Capabilities

- `healthcare-lab-dcm4chee-mwl-order-model`: Extends supported PACS result actions with a capability-gated Healthcare Lab ECG graph action while preserving the generic dcm4chee viewer and retrieve behaviors.

## Impact

- Affected frontend areas: Flask page routing and application composition, a dedicated ECG viewer template, modular dcm4chee view/API code, and feature-specific CSS.
- Existing backend dependencies: `GET /api/dcm4chee/results/<result-id>/ecg` and `GET /api/dcm4chee/results/<result-id>/ecg/render.svg`; their result-ID security boundary and controlled errors remain authoritative.
- Affected verification areas: frontend contract/unit tests and route integration tests for eligibility, navigation, loading, success, unsupported, not-found, and upstream failure behavior.
- No database migration, new DICOM/WADO transport, renderer change, credential exposure, or replacement of the generic dcm4chee Web UI action is introduced.
