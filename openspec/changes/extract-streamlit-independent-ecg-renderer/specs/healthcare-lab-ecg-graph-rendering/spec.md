## ADDED Requirements

### Requirement: Normalized ECG waveforms render without prototype runtimes
Healthcare Lab SHALL provide a framework-independent graph renderer that consumes the normalized immutable `EcgWaveform` model and SHALL NOT require Streamlit, DICOM parsing, JSON or file selection, authentication widgets, batch processing, or process working-directory changes.

#### Scenario: Normalized waveform is rendered
- **WHEN** a caller supplies a valid normalized 12-lead ECG waveform
- **THEN** the renderer produces a non-empty browser-displayable graph without reading another input source

#### Scenario: Renderer runs without Streamlit
- **WHEN** the renderer is imported and called in the Flask application runtime
- **THEN** rendering does not import or require a Streamlit runtime

### Requirement: ECG graphs use normalized timing and calibrated samples
The renderer SHALL read lead names, calibrated mV samples, and sampling frequency from the normalized waveform, SHALL derive elapsed time from that sampling frequency, and MUST NOT replace it with a hard-coded sample rate.

#### Scenario: Non-default sampling frequency is rendered
- **WHEN** a normalized waveform declares a supported sampling frequency other than the prototype's hard-coded rate
- **THEN** the graph time axis and trace placement use the declared sampling frequency

#### Scenario: Calibrated source samples are plotted
- **WHEN** baseline centering is disabled
- **THEN** the renderer uses the normalized mV samples without applying an implicit source-data correction

### Requirement: SVG output is browser-safe and demonstration-only
The MVP renderer SHALL return SVG bytes with media type `image/svg+xml`, SHALL include every canonical 12-lead label, and SHALL visibly classify the graph as demonstration-only and not for diagnostic use.

#### Scenario: Twelve-lead SVG is produced
- **WHEN** a valid normalized fixture is rendered with default configuration
- **THEN** the result is non-empty SVG containing labels for I, II, III, aVR, aVL, aVF, and V1 through V6

#### Scenario: Standalone graph communicates its safety classification
- **WHEN** a generated SVG is displayed independently of its surrounding Flask page
- **THEN** the SVG visibly states that it is for demonstration only and not for diagnostic use

### Requirement: ECG display configuration is explicit and validated
The renderer SHALL expose immutable configuration for output dimensions, nominal paper speed, nominal voltage gain, and optional display-only baseline centering. It SHALL default to a two-column, six-row 12-lead layout, 25 mm/s nominal paper speed, 10 mm/mV nominal gain, and disabled baseline centering.

#### Scenario: Default layout is rendered
- **WHEN** a caller renders a waveform without overriding configuration
- **THEN** the graph uses the canonical two-column, six-row lead layout and documented nominal scale defaults

#### Scenario: Invalid dimensions are rejected
- **WHEN** width or height is non-numeric, non-finite, non-positive, or outside documented renderer bounds
- **THEN** the renderer raises a stable typed configuration error before producing an output

#### Scenario: Invalid nominal scale is rejected
- **WHEN** paper speed or voltage gain is non-numeric, non-finite, or non-positive
- **THEN** the renderer raises a stable typed configuration error

### Requirement: Display transforms preserve normalized input
The renderer MUST NOT mutate the waveform, its channels, or their calibrated samples. Optional baseline centering SHALL operate only on renderer-owned display values and SHALL be disabled by default.

#### Scenario: Default rendering preserves the caller waveform
- **WHEN** the same normalized waveform is inspected before and after default rendering
- **THEN** its channels, calibrated samples, sampling frequency, and metadata remain unchanged

#### Scenario: Optional centering preserves the caller waveform
- **WHEN** baseline centering is explicitly enabled
- **THEN** the displayed traces use the documented per-lead centering transform while the caller's waveform remains unchanged

### Requirement: Rendering owns and cleans up per-call resources
Each render call SHALL own its figure, canvas, buffer, and output, SHALL close or release those resources deterministically on success and failure, and SHALL NOT share mutable output paths or process-global working-directory state.

#### Scenario: Repeated rendering does not leak figures
- **WHEN** a valid waveform is rendered repeatedly
- **THEN** every call returns an independent non-empty SVG and the number of retained Matplotlib figures does not grow

#### Scenario: Failed rendering cleans up
- **WHEN** rendering fails after per-call resources have been allocated
- **THEN** those resources are released and no partial shared output remains

#### Scenario: Concurrent rendering remains independent
- **WHEN** multiple Flask or Gunicorn workers or threads render waveforms concurrently
- **THEN** each call returns output for its own waveform and configuration without shared filenames, cross-call graph content, or working-directory mutation

### Requirement: Plotting dependencies are runtime-compatible
Healthcare Lab SHALL declare pinned compatible ranges for every plotting dependency required by the renderer and SHALL exclude the prototype helper when its runtime, licensing, maintenance, or concurrency contract is not needed.

#### Scenario: Production dependencies are installed
- **WHEN** Healthcare Lab dependencies are installed from the project declaration
- **THEN** the renderer can generate its SVG without separately installing Streamlit or an undeclared plotting helper

#### Scenario: Dependency scope is minimized
- **WHEN** the renderer can operate correctly over immutable Python sample sequences
- **THEN** NumPy is not added solely because the prototype used it
