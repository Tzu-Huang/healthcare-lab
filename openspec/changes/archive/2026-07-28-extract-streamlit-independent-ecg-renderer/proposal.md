## Why

Healthcare Lab can normalize DICOM ECG waveforms, but its only graphing reference is a Streamlit prototype that combines plotting with authentication, JSON and file selection, batch processing, process-wide working-directory changes, and hard-coded sampling assumptions. ZAC-93 needs a deterministic rendering boundary so the Flask application can display normalized 12-lead waveforms safely without importing the prototype runtime or implying a diagnostic-grade display contract.

## What Changes

- Add a framework-independent renderer that accepts the immutable normalized ECG waveform model and explicit display configuration.
- Produce a browser-displayable SVG entirely in memory, with all 12 lead labels and a visible demonstration-only, non-diagnostic disclaimer.
- Preserve the prototype's useful two-column 12-lead layout while making paper speed, voltage gain, dimensions, and optional display-only baseline centering explicit.
- Keep calibrated source samples unchanged and apply any display transform only to renderer-owned values.
- Use each waveform's normalized sampling frequency instead of a hard-coded rate.
- Make repeated and concurrent rendering independent of shared output paths, process working directories, and shared Matplotlib figures, with deterministic cleanup.
- Validate unsupported dimensions and configuration with stable renderer errors.
- Declare pinned compatible plotting dependencies needed by the Flask/Gunicorn runtime; Streamlit and the prototype's file, authentication, widget, and batch concerns remain outside the renderer.
- Limit the MVP to SVG output. PNG and diagnostic-grade display conformance remain outside this change.

## Capabilities

### New Capabilities

- `healthcare-lab-ecg-graph-rendering`: Defines deterministic, browser-safe rendering of normalized 12-lead ECG waveforms for demonstration-only use.

### Modified Capabilities

None.

## Impact

- Affected production areas: a new presentation-layer ECG renderer consuming `backend/domain/ecg_waveform.py`, plus plotting dependency declarations in `requirements.txt`.
- Affected verification areas: new presentation-layer tests for SVG content, labels, normalized sampling frequency, dimensions, input immutability, optional centering, cleanup, and concurrent calls.
- Runtime impact: Flask/Gunicorn may render SVG bytes in memory without Streamlit, DICOM parsing, JSON selection, temporary output files, or working-directory mutation.
- Compatibility: no existing API, persistence, normalized waveform, DICOM parsing, or frontend behavior changes in this proposal.
- Safety statement: generated graphs are explicitly demonstration-only and not suitable for diagnostic use.
