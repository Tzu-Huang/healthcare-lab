## 1. Fixture Safety and Contract

- [x] 1.1 Inventory both supplied ECG files, record hashes and provenance, and review all identifying attributes against an explicit de-identification checklist.
- [x] 1.2 Exclude any unresolved source fixture or generate a documented sanitized derivative that preserves SOP Class, channel, sample, timing, and calibration invariants.
- [x] 1.3 Add a machine-readable fixture manifest and validation helper that fails on identity or invariant drift without printing PHI.

## 2. Automated End-to-End Release Gate

- [x] 2.1 Add persisted-result-to-viewer tests for both SOP Classes through controlled bare and multipart WADO-RS responses.
- [x] 2.2 Assert canonical leads, 10,000 samples per channel, 1,000 Hz, 10 seconds, microvolt-to-millivolt calibration, SVG labels, viewer summary, and safety classification.
- [x] 2.3 Add disclosure-safe regression cases for non-ECG DICOM, missing Waveform Sequence, wrong units, truncated samples, malformed multipart data, upstream failures, and unknown results.
- [ ] 2.4 Add authorization and unconfigured-profile coverage without exposing credentials, endpoints, internal paths, raw metadata, or upstream payloads.

## 3. Compatibility and Deployment Verification

- [ ] 3.1 Re-verify result refresh, reconciliation and grouping, generic viewer links, artifact actions, and capability-gated ECG actions with mixed result types.
- [x] 3.2 Verify the supported local and container dependency installation paths parse and render both ECG formats without manual package installation.
- [ ] 3.3 Run the relevant unit, integration, frontend, dependency, and disclosure-safety suites and record the exact tested commit.

## 4. Manual Acceptance and Documentation

- [ ] 4.1 Execute and record a bounded synthetic dcm4chee checklist for result refresh, `View ECG Graph`, viewer loading, graph labels, summary fields, and safety notice for both SOP Classes.
- [x] 4.2 Document configuration, supported SOP Class UIDs, fixture policy, runtime dependencies, stable troubleshooting categories, recovery actions, and display limitations.
- [x] 4.3 State that the viewer is demonstration-only and non-diagnostic, and create follow-up issues for zoom, calipers, annotations, print layout, or export instead of expanding this change.
- [ ] 4.4 Run strict OpenSpec validation and repository diff-hygiene checks, recording precise environment-dependent skips or linked blocking defects.
