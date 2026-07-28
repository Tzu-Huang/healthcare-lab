## 1. Dependency and Domain Contract

- [x] 1.1 Declare the supported `pydicom` runtime dependency and verify the container installation path includes it.
- [x] 1.2 Add immutable normalized waveform/channel models and the typed ECG waveform error hierarchy under a focused domain module.
- [x] 1.3 Define supported SOP Class, SCPECG lead, voltage-unit, and display-safe metadata allowlists.

## 2. Parser Implementation

- [x] 2.1 Validate SOP Class, Waveform Sequence structure, dimensions, sampling frequency, sample interpretation, and exact Waveform Data byte length.
- [x] 2.2 Decode signed 16-bit multiplexed samples into channel-major data without adding an undeclared numerical dependency.
- [x] 2.3 Apply sensitivity, correction factor, baseline, and supported voltage-to-mV conversion while preserving raw calibrated offsets.
- [x] 2.4 Resolve and reorder the complete 12-lead layout from SCPECG source codes and reject missing, duplicate, unknown, or ambiguous definitions.
- [x] 2.5 Build the normalized duration, SOP identity, channel records, and allowlisted display metadata without framework or filesystem coupling.

## 3. Focused Verification

- [x] 3.1 Add constructed pydicom dataset tests for both supported SOP Classes, shuffled canonical lead ordering, calibration, unit conversion, and metadata exclusion.
- [x] 3.2 Add typed-error tests for unsupported SOP Classes, missing/empty Waveform Sequence, inconsistent byte length, unsupported sample interpretation, unknown units, and ambiguous lead layouts.
- [x] 3.3 Add optional local-fixture tests for both Philips DICOM ECG files, including 12 × 10,000 shape, 1,000 Hz, 10-second duration, canonical leads, and first-time-point calibration evidence.
- [x] 3.4 Run focused tests and confirm the Git-excluded `dicom-formats/` directory remains untracked and unstaged.

## 4. Regression Verification

- [ ] 4.1 Run the repository quality gate and architecture contract tests.
- [ ] 4.2 Build or validate the application container dependency installation and record final verification evidence.
