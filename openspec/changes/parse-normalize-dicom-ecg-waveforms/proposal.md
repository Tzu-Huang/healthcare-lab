## Why

Healthcare Lab can discover DICOM ECG results but does not yet have a safe,
renderer-independent way to decode their multiplexed waveform samples. A
normalized parser is required before retrieval APIs, graph rendering, and
end-to-end viewer verification can share reliable calibrated ECG data.

## What Changes

- Declare `pydicom` as an application/runtime dependency.
- Parse the supported 12-lead and General ECG Waveform Storage SOP Classes into
  one framework-independent ECG waveform model.
- Decode multiplexed signed samples, apply DICOM channel calibration, and
  normalize supported voltage units to mV while preserving the calibrated
  signal without median centering.
- Derive canonical I, II, III, aVR, aVL, aVF, and V1-V6 ordering from SCPECG
  channel source codes rather than vendor channel position.
- Expose only explicitly allowlisted, display-safe DICOM metadata.
- Reject unsupported or inconsistent waveform datasets with typed domain
  errors.
- Add focused tests using local-only, Git-excluded DICOM fixtures plus
  constructed malformed datasets.

## Capabilities

### New Capabilities

- `healthcare-lab-dicom-ecg-waveform-parsing`: Defines supported DICOM ECG
  inputs, normalized calibrated output, canonical lead mapping, safe metadata,
  and typed rejection behavior.

### Modified Capabilities

None.

## Impact

- Adds a focused ECG waveform owner under `backend/domain/` and mirrored domain
  tests.
- Adds `pydicom` to `requirements.txt` and the application container dependency
  installation path.
- Does not add HTTP routes, dcm4chee retrieval, plotting, persistence, or
  working-directory-dependent fixture lookup.
- Keeps `dicom-formats/` local-only through `.git/info/exclude`; fixture files
  are not part of the proposal commit or any later push.
