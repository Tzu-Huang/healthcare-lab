## 1. Renderer Contract and Dependencies

- [ ] 1.1 Add the presentation-layer ECG renderer module and test package with immutable render configuration, typed SVG result, and stable renderer/configuration errors.
- [ ] 1.2 Select and document bounded default SVG dimensions while retaining the agreed two-column, six-row canonical lead layout.
- [ ] 1.3 Declare and install a pinned compatible Matplotlib range; add NumPy only if implementation evidence shows immutable Python sequences are insufficient.
- [ ] 1.4 Add dependency/import checks proving production rendering requires neither Streamlit nor the prototype `ecg_plot` helper.

## 2. Deterministic SVG Rendering

- [ ] 2.1 Implement request-local object-oriented Matplotlib figure, axes, SVG canvas, and in-memory buffer ownership without `pyplot`, shared output paths, backend mutation, or `os.chdir()`.
- [ ] 2.2 Render the canonical 12 leads in the two-column, six-row layout with stable labels, ECG grid styling, and elapsed time derived from `EcgWaveform.sampling_frequency_hz`.
- [ ] 2.3 Apply the explicit 25 mm/s nominal paper speed and 10 mm/mV nominal voltage-gain defaults without claiming browser physical calibration.
- [ ] 2.4 Add the fixed visible demonstration-only, non-diagnostic disclaimer and return SVG bytes with `image/svg+xml`.
- [ ] 2.5 Implement opt-in per-lead baseline centering over renderer-owned display values while leaving the normalized waveform unchanged.

## 3. Validation and Resource Safety

- [ ] 3.1 Validate dimensions and nominal scale values for type, finiteness, positivity, and documented bounds before rendering.
- [ ] 3.2 Guarantee figure, canvas, and buffer cleanup in success and failure paths with no retained partial output.
- [ ] 3.3 Add repeated-render tests proving independent non-empty SVG results and no growth in retained Matplotlib figures.
- [ ] 3.4 Add concurrent-render tests proving waveform/configuration isolation and absence of shared paths or process working-directory mutation.

## 4. Behavioral Verification

- [ ] 4.1 Add a normalized 12-lead fixture test covering non-empty browser-displayable SVG, all canonical lead labels, media type, and the visible safety disclaimer.
- [ ] 4.2 Add tests proving non-default normalized sampling frequencies control time placement and no hard-coded prototype rate remains.
- [ ] 4.3 Add tests proving default and baseline-centered rendering do not mutate channels, calibrated mV samples, sampling frequency, or metadata.
- [ ] 4.4 Add typed-error tests for invalid dimensions, invalid paper speed, invalid voltage gain, and failures after resource allocation.
- [ ] 4.5 Run the ECG domain and renderer suites, complete project regression suite, dependency checks, and strict OpenSpec validation.
- [ ] 4.6 Audit the final implementation against the demo-only boundary and record that diagnostic display conformance, PNG/PDF, DICOM/JSON loading, Flask routes, frontend integration, Streamlit, and batch processing remain out of scope.
