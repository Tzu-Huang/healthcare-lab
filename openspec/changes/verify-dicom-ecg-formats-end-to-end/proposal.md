## Why

The ECG parsing, rendering, retrieval, and viewer capabilities are implemented
independently, but the assembled workflow has not been proven against both
supported DICOM ECG Waveform Storage formats. A repeatable release gate and
operator documentation are required before the parent ECG Viewer feature can
be considered complete.

## What Changes

- Establish a safe, reproducible fixture strategy for the supplied 12-lead and
  General ECG Waveform Storage instances, including de-identification review or
  documented sanitized derivatives.
- Add automated end-to-end coverage from a persisted reconciled result through
  WADO-RS multipart extraction, DICOM normalization, SVG rendering, and the
  dedicated viewer route for both supported SOP Classes.
- Verify the canonical 12-lead, 10,000-sample, 1,000 Hz, 10-second, microvolt to
  millivolt, graph-label, and display-summary contracts.
- Add regression coverage for unsupported DICOM, missing waveform data, wrong
  units, truncated samples, upstream failures, and unauthorized or
  unconfigured profiles.
- Re-verify result refresh and grouping, generic viewer links, artifact
  actions, runtime/container dependencies, and disclosure-safe failures.
- Publish a manual `View ECG Graph` checklist plus configuration, supported SOP
  Class, troubleshooting, and demonstration-only/non-diagnostic guidance.
- Record zoom, calipers, annotations, print layout, and export as follow-up
  issues instead of expanding this MVP.

## Capabilities

### New Capabilities

- `healthcare-lab-ecg-viewer-release-verification`: Defines the fixture safety,
  assembled end-to-end release gate, regression matrix, manual acceptance
  checklist, and operator documentation contract for the ECG Viewer.

### Modified Capabilities

None.

## Impact

The change affects test fixtures and fixture-validation tooling, backend and
frontend end-to-end tests, deployment dependency checks, bounded verification
evidence, and ECG Viewer operating documentation. The existing parser,
renderer, result-scoped APIs, viewer behavior, and dcm4chee result workflows are
verification subjects; new interactive graph features and diagnostic claims
remain out of scope.
