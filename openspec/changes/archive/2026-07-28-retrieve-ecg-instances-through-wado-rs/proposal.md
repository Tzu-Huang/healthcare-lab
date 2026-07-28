## Why

Healthcare Lab can reconcile dcm4chee result records and can parse and render
DICOM ECG instances, but it cannot yet retrieve the reconciled instance and
serve a graph through a safe application-owned API. A result-ID boundary is
needed so clients can view ECG output without gaining arbitrary upstream URL
or filesystem access.

## What Changes

- Add a backend use case that resolves a persisted dcm4chee result by result ID
  and requires instance-level study, series, and SOP Instance identifiers.
- Retrieve the selected instance through the configured dcm4chee WADO-RS
  profile while reusing its authentication, TLS verification, and timeout
  behavior.
- Accept bare DICOM and valid `multipart/related` WADO-RS responses, with
  bounded response size and controlled malformed-response handling.
- Pass retrieved bytes through the existing normalized DICOM ECG parser and
  framework-independent SVG renderer.
- Expose stable result-scoped ECG metadata/capability and SVG routes without
  accepting caller-provided URLs or filesystem paths.
- Map missing records, non-instance results, unsupported content or SOP
  classes, invalid waveforms, and upstream failures to controlled HTTP errors
  that do not disclose PHI, credentials, or internal endpoints.
- Add end-to-end mocked WADO-RS coverage for bare and multipart DICOM plus
  limits, timeouts, malformed payloads, and parser failures.
- Preserve existing result refresh, reconciliation, and generic viewer-link
  behavior.

## Capabilities

### New Capabilities

- `healthcare-lab-dcm4chee-ecg-retrieval-api`: Defines result-scoped WADO-RS
  retrieval, safe ECG metadata and SVG APIs, response bounds, content handling,
  and controlled error behavior.

### Modified Capabilities

None.

## Impact

- Affected backend areas: dcm4chee result repository lookup, an application
  retrieval service, DICOMweb transport handling, and result-scoped Flask API
  routes.
- Existing `healthcare-lab-dicom-ecg-waveform-parsing` and
  `healthcare-lab-ecg-graph-rendering` capabilities become downstream
  dependencies without changing their contracts.
- Affected verification areas: repository/service/API tests with mocked
  WADO-RS responses and security/error boundary coverage.
- No frontend-owned dcm4chee credentials, arbitrary fetch endpoint, database
  migration, or change to existing viewer URLs is introduced.
