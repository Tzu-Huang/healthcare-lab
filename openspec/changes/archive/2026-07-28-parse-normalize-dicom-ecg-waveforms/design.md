## Context

The dcm4chee result flow currently handles DICOM metadata but has no owner for
decoding ECG Waveform instances. ZAC-92 supplies that domain boundary for the
viewer work in ZAC-91, ZAC-93, ZAC-94, and ZAC-96.

The two known Philips fixtures use different supported SOP Classes but share a
single Waveform Sequence item with 12 channels, 10,000 samples per channel,
1,000 Hz sampling, signed 16-bit multiplexed data, and SCPECG channel source
definitions. The fixture directory is local-only and MUST remain outside Git.

## Goals / Non-Goals

**Goals:**

- Produce one calibrated, canonical, renderer-independent ECG model from either
  supported SOP Class.
- Validate structural assumptions before decoding untrusted byte payloads.
- Preserve signal offsets and expose only explicitly safe metadata.
- Keep domain tests deterministic while allowing real local fixtures to provide
  high-value compatibility coverage.

**Non-Goals:**

- WADO-RS retrieval, Flask routes, JSON serialization, caching, and persistence.
- Plotting, layout, filtering, median centering, or other signal processing.
- Supporting arbitrary DICOM Waveform SOP Classes, sample interpretations,
  lead systems, or physical units.
- Committing or redistributing the supplied DICOM fixtures.

## Decisions

### Use a focused domain module with immutable value objects

`backend/domain/ecg_waveform.py` will own the normalized model, typed error
hierarchy, SOP/unit/lead mappings, and parser entry point. The parser will
accept a `pydicom.Dataset`; a thin convenience entry point may read bytes or a
binary stream through pydicom without depending on Flask or paths.

The model will contain canonical channel records, calibrated samples in mV,
sampling frequency, duration, SOP Class UID, and allowlisted metadata.
Read-only tuples are preferred over mutable lists so downstream renderers
cannot accidentally alter the source signal.

Alternative considered: add waveform behavior to `backend/domain/dicom.py`.
That module already owns identifiers and dcm4chee metadata rules; waveform
decoding is a sufficiently distinct bounded responsibility to justify a
focused module.

### Decode multiplexed samples explicitly

The parser will validate the channel count, sample count, bits allocated,
sample interpretation, and exact byte length before unpacking. Samples are
time-point-major in DICOM Waveform Data and will be deinterleaved into
channel-major output.

The first implementation will support signed 16-bit samples (`SS`) explicitly.
Using a small standard-library decoder avoids making NumPy an undeclared
runtime dependency. pydicom remains responsible for DICOM dataset decoding and
transfer syntax handling.

Alternative considered: pydicom's NumPy waveform helpers. They introduce an
additional runtime dependency and can obscure which calibration and layout
rules form the Healthcare Lab contract.

### Apply DICOM calibration before unit normalization

For each channel and raw sample, the parser will calculate:

`calibrated = raw * ChannelSensitivity * ChannelSensitivityCorrectionFactor + ChannelBaseline`

The correction factor and baseline will use their DICOM-defined defaults when
optional. The resulting channel unit will then be converted through an
explicit supported-unit table to mV. No centering or offset removal occurs.

### Resolve leads from coded channel definitions

Each channel will be identified from its SCPECG Channel Source Sequence code.
An explicit mapping will convert the supported source codes to the canonical
order I, II, III, aVR, aVL, aVF, V1-V6. Vendor channel position will never
determine lead identity.

Missing, duplicate, unknown, or otherwise ambiguous required lead definitions
will reject the dataset rather than guessing.

### Treat metadata as an allowlist

The normalized model will construct a new metadata mapping from reviewed
non-patient fields only, such as modality, manufacturer/device descriptors,
waveform dimensions, and SOP identifiers. It will not pass through arbitrary
dataset attributes, patient demographics, identifiers, accessions, study
descriptions, or free text.

### Use constructed datasets for mandatory tests and local fixtures for compatibility

Unit tests will construct minimal pydicom datasets covering calibration,
ordering, and every typed rejection path. Tests that depend on
`dicom-formats/` will skip with an explicit reason when fixtures are absent, so
CI does not require or redistribute local files. When present locally, both
fixtures must satisfy the complete acceptance shape and first-time-point
assertions.

## Risks / Trade-offs

- [DICOM calibration semantics vary across producers] → Keep mappings explicit,
  test the known fixtures, and reject rather than infer unknown units or codes.
- [Large immutable Python tuples use more memory than NumPy arrays] → The known
  120,000-sample datasets are bounded and acceptable; revisit only with measured
  viewer workloads.
- [Optional local fixtures could hide CI regressions] → Constructed datasets
  provide mandatory CI coverage for all behavioral rules; local fixtures add
  vendor compatibility evidence.
- [Display metadata could expose PHI] → Build a narrow allowlist and test that
  patient and study-identifying attributes never enter the normalized model.

## Migration Plan

1. Add the dependency, domain model/parser, and focused tests.
2. Build the container and run focused plus full quality gates.
3. Verify both local fixtures without staging them.
4. Downstream retrieval and renderer tickets consume the new model separately.

Rollback removes the new dependency and focused module/tests; no schema,
stored-data, public API, or migration rollback is required.

## Open Questions

- Whether later tickets require a stable JSON projection of the normalized
  model; ZAC-92 intentionally does not define one.
- Whether multiple Waveform Sequence items should eventually be supported;
  this change rejects layouts that cannot produce one unambiguous canonical
  12-lead signal.
