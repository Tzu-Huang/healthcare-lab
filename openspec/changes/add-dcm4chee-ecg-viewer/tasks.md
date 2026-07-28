## 1. Viewer Route and Shell

- [x] 1.1 Add the result-ID ECG viewer Flask route and focused template with loading, content, summary, and accessible status/error regions.
- [x] 1.2 Add feature-scoped ECG viewer CSS using existing Healthcare Lab tokens and responsive layout conventions.

## 2. Viewer Data and Rendering

- [x] 2.1 Add a modular frontend API adapter for result-scoped ECG metadata and SVG URLs without exposing WADO-RS details.
- [x] 2.2 Add viewer JavaScript that reconstructs state from the route result ID and renders loading, graph, lead/sample-rate/unit/duration summary, and disclosure-safe failure states.
- [x] 2.3 Handle metadata success and SVG load failure independently, including accessible status announcements and retry-safe messages.

## 3. Result Action Integration

- [x] 3.1 Project or reuse an explicit display-safe ECG rendering capability and persisted result ID on dcm4chee instance result rows.
- [x] 3.2 Add capability-gated `View ECG Graph` to instance actions with `/viewer/ecg/<result-id>` construction and `noopener`.
- [x] 3.3 Preserve existing `Open Artifact`, `Open Viewer`, and retrieve/copy actions for supported and unsupported results.

## 4. Verification

- [x] 4.1 Add frontend tests for ECG action visibility, non-ECG suppression, result-ID URL construction, `noopener`, and generic action compatibility.
- [x] 4.2 Add viewer tests for direct navigation, reload-safe initialization, loading, successful graph/summary rendering, and SVG load failure.
- [x] 4.3 Add integration/contract tests for the viewer route and controlled not-found, unsupported/invalid-waveform, and upstream failure presentation.
- [x] 4.4 Run focused frontend and integration suites plus `openspec validate add-dcm4chee-ecg-viewer --strict`.
