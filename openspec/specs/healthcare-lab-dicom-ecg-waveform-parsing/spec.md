# healthcare-lab-dicom-ecg-waveform-parsing Specification

## Purpose
TBD - created by archiving change parse-normalize-dicom-ecg-waveforms. Update Purpose after archive.
## Requirements
### Requirement: Supported DICOM ECG instances
The system SHALL parse 12-lead ECG Waveform Storage SOP Class
`1.2.840.10008.5.1.4.1.1.9.1.1` and General ECG Waveform Storage SOP Class
`1.2.840.10008.5.1.4.1.1.9.1.2` through the same framework-independent
implementation.

#### Scenario: Parse either supported SOP Class
- **WHEN** a structurally valid instance of either supported SOP Class is parsed
- **THEN** the system returns the same normalized ECG waveform model type

#### Scenario: Reject another SOP Class
- **WHEN** a dataset declares a SOP Class outside the supported allowlist
- **THEN** the system raises a typed unsupported-SOP error

### Requirement: Normalized ECG waveform model
The system SHALL return channel-major calibrated samples, canonical lead names
and source codes, sampling frequency, calibrated unit, duration, SOP Class UID,
and display-safe metadata without depending on Flask, Streamlit, Matplotlib,
filesystem paths, or process working-directory changes.

#### Scenario: Normalize the known fixture shape
- **WHEN** either supported Philips fixture is parsed
- **THEN** the model contains 12 channels by 10,000 samples, a 1,000 Hz sampling frequency, a 10-second duration, and calibrated unit mV

#### Scenario: Preserve calibrated signal offsets
- **WHEN** calibrated samples contain a non-zero baseline or median
- **THEN** the parser returns those values without median centering or other signal processing

### Requirement: Multiplexed sample decoding
The system SHALL validate waveform dimensions and decode supported signed
16-bit DICOM Waveform Data from time-point-major multiplexing into
channel-major samples.

#### Scenario: Decode the first time point
- **WHEN** a waveform contains one signed sample for each channel at its first time point
- **THEN** each decoded channel begins with the corresponding multiplexed sample before calibration and unit normalization

#### Scenario: Reject inconsistent byte length
- **WHEN** Waveform Data length does not exactly match channel count, sample count, and supported sample width
- **THEN** the system raises a typed malformed-waveform error

#### Scenario: Reject unsupported sample interpretation
- **WHEN** a waveform declares a sample interpretation other than the supported signed 16-bit representation
- **THEN** the system raises a typed unsupported-sample error

### Requirement: DICOM channel calibration
The system SHALL apply Channel Sensitivity, Channel Sensitivity Correction
Factor, and Channel Baseline according to DICOM calibration semantics, then
convert each supported voltage unit to mV.

#### Scenario: Apply complete channel calibration
- **WHEN** a channel provides sensitivity, correction factor, baseline, and a supported voltage unit
- **THEN** each output sample equals the calibrated voltage converted to mV

#### Scenario: Preserve first fixture values through normalization
- **WHEN** either supported Philips fixture is parsed
- **THEN** its first decoded time point agrees with the fixture's calibrated values before the supported microvolt-to-millivolt conversion

#### Scenario: Reject an unknown required unit
- **WHEN** a required channel unit is missing or not in the supported voltage-unit mapping
- **THEN** the system raises a typed unsupported-unit error

### Requirement: Canonical SCPECG lead mapping
The system SHALL derive lead identity from SCPECG Channel Source Sequence codes
and order output as I, II, III, aVR, aVL, aVF, V1, V2, V3, V4, V5, V6 without
using vendor channel position as identity.

#### Scenario: Reorder shuffled source channels
- **WHEN** all required SCPECG lead codes are present in a non-canonical source order
- **THEN** the output channels are returned in canonical lead order with their original source codes

#### Scenario: Reject ambiguous lead layout
- **WHEN** a required lead is missing, duplicated, unknown, or cannot be identified unambiguously
- **THEN** the system raises a typed lead-layout error

### Requirement: Typed structural rejection
The system SHALL reject missing or empty Waveform Sequence data and other
unsupported structural layouts using domain-specific error types rather than
leaking incidental pydicom, indexing, or unpacking exceptions.

#### Scenario: Reject a missing Waveform Sequence
- **WHEN** a supported SOP dataset has no Waveform Sequence
- **THEN** the system raises a typed missing-waveform error

#### Scenario: Reject an empty Waveform Sequence
- **WHEN** a supported SOP dataset has an empty Waveform Sequence
- **THEN** the system raises a typed missing-waveform error

### Requirement: Display-safe metadata
The system SHALL construct normalized metadata from an explicit allowlist and
MUST NOT copy arbitrary DICOM attributes into renderer-facing output.

#### Scenario: Exclude identifying attributes
- **WHEN** a parsed dataset contains patient identity, accession, study description, or other non-allowlisted attributes
- **THEN** none of those attributes appear in normalized display-safe metadata

#### Scenario: Include reviewed technical attributes
- **WHEN** a parsed dataset contains allowlisted SOP, modality, waveform, or device technical attributes
- **THEN** their display-safe values are available in normalized metadata

### Requirement: Local-only fixture handling
The system's automated tests SHALL provide mandatory constructed-dataset
coverage and SHALL treat supplied DICOM fixture files as optional local
compatibility inputs that are never required in Git.

#### Scenario: Run tests without local fixtures
- **WHEN** the local `dicom-formats` directory is absent
- **THEN** mandatory constructed-dataset tests run and fixture-specific compatibility tests skip explicitly

#### Scenario: Verify available local fixtures
- **WHEN** both local Philips fixtures are available
- **THEN** the compatibility tests parse both files and verify their normalized shape, timing, lead order, calibration, and unit

