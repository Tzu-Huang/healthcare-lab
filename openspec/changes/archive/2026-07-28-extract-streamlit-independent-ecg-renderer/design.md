## Context

ZAC-92 established `EcgWaveform`, an immutable, renderer-independent domain model containing canonical 12-lead channels calibrated to mV, sampling frequency, duration, and display-safe metadata. The plotting reference in `tmp/04_plot_service/04_plot_service.py` predates that boundary: it reads JSON, authenticates Streamlit users, selects and batches files, mutates the process working directory, subtracts per-lead medians in place, assumes a 1,000 Hz sample rate, and delegates plotting through global `matplotlib.pyplot` state and `ecg_plot`.

ZAC-93 must create a small presentation boundary that Flask can call later without reopening DICOM or importing Streamlit. It must work under repeated and concurrent Gunicorn requests, preserve the calibrated domain input, and avoid suggesting that a browser SVG is a validated diagnostic ECG display.

## Goals / Non-Goals

**Goals:**

- Render an immutable normalized 12-lead waveform into deterministic browser-safe SVG bytes.
- Preserve a useful two-column, six-row lead layout with explicit lead labels.
- Make paper speed, voltage gain, output dimensions, and optional display-only baseline centering explicit and validated.
- Read timing from `EcgWaveform.sampling_frequency_hz` and keep calibrated mV samples separate from display transforms.
- Avoid shared files, working-directory changes, shared figures, and retained Matplotlib resources.
- Provide a stable result and typed error boundary suitable for a later Flask route.
- Mark every output as demonstration-only and not for diagnostic use.

**Non-Goals:**

- Diagnostic-display conformance, clinical interpretation, measurement, annotation, rhythm analysis, or print calibration.
- Guaranteeing physical millimetre dimensions on arbitrary browsers, screens, or printers.
- Reading DICOM or JSON, selecting files, authenticating users, hosting Streamlit widgets, or batch processing.
- Adding a Flask route or integrating the graph into a frontend view.
- Supporting PNG, PDF, interactive graphs, non-12-lead layouts, or arbitrary lead derivation in the MVP.

## Decisions

### Accept the normalized domain model at the renderer boundary

The renderer will accept `EcgWaveform` directly. It will use the canonical channel order, mV samples, and waveform sampling frequency already established by the domain parser. It will not accept DICOM datasets, paths, JSON payloads, or uncalibrated arrays.

This keeps parsing, calibration, lead resolution, and validation in the domain layer and makes renderer tests independent of DICOM I/O. A generic array-based API was considered but rejected because it would duplicate unit, lead-order, and sampling contracts at each caller.

### Return an in-memory typed SVG result

The rendering operation will return an immutable result containing SVG bytes and the `image/svg+xml` media type. Each call will serialize through its own in-memory buffer and will not create or expose an output path.

SVG is the only MVP output because it remains sharp in the browser, carries testable labels and disclaimer text, and avoids DPI-driven raster ambiguity. PNG can be added later behind an explicit format extension if a compatibility consumer requires it.

### Use Matplotlib's object-oriented figure API without `ecg_plot`

The implementation will construct a request-local `Figure`, axes, grid, labels, and traces using Matplotlib's object-oriented API and an SVG canvas. It will avoid `matplotlib.pyplot`, global current-figure state, global backend mutation during rendering, and the prototype's `ecg_plot` helper.

Owning the small 12-lead layout avoids an undeclared helper dependency and gives the application direct control over calibrated units, disclaimer content, cleanup, and concurrency. The implementation will declare a pinned compatible Matplotlib range and the NumPy range only if production rendering actually requires NumPy rather than immutable Python sequences.

### Model display settings as an immutable validated configuration

An immutable render configuration will expose width, height, paper speed, voltage gain, and baseline-centering selection. Defaults will be:

- two columns by six rows in canonical lead order;
- 25 mm/s nominal paper speed;
- 10 mm/mV nominal voltage gain;
- baseline centering disabled;
- bounded browser-oriented dimensions chosen during implementation and recorded in tests.

Dimensions and finite positive scale values will be validated before figure allocation. The paper-speed and gain names describe conventional ECG visual scaling, but the output disclaimer and documentation will state that physical on-screen millimetres are not guaranteed.

### Treat baseline centering as a display-only copy transform

When centering is disabled, the renderer will plot calibrated mV samples without baseline subtraction. When enabled, it will derive renderer-owned values by subtracting a per-lead median or another explicitly documented robust centre without modifying channel tuples or the `EcgWaveform`.

Making centering opt-in prevents a useful prototype display transform from silently becoming domain data. Renderer tests will compare the caller's waveform before and after both rendering modes.

### Derive the time axis from normalized sampling frequency

Each sample position will be converted to elapsed seconds using `sample_index / sampling_frequency_hz`. Paper speed then controls the nominal horizontal scale of the rendered view. No renderer constant may substitute for the waveform sampling frequency.

The default layout will show each lead's available normalized duration within its panel rather than inventing or resampling missing data. Cropping or rhythm-strip policies can be specified separately if later viewer requirements need them.

### Guarantee per-call resource ownership and cleanup

Every call will own its figure, axes, canvas, and buffer. Cleanup will run in a `finally` path for successful serialization and all renderer failures. There will be no `os.chdir()`, shared output filename, module-level mutable figure, or caller-visible temporary path.

Focused tests will execute repeated and concurrent calls, verify independent non-empty results, and inspect Matplotlib figure/resource cleanup through the narrowest stable test seam available. The renderer will not promise bit-for-bit SVG identity because Matplotlib may emit generated identifiers; determinism means equivalent input/configuration produces equivalent graph content without shared-state interference.

### Make the safety classification part of the output contract

Every SVG will visibly contain `For demonstration only — not for diagnostic use` or an equivalent fixed product-approved phrase. The renderer API and capability specification will carry the same classification.

This is preferred over relying only on a surrounding Flask page because SVG can be opened or embedded independently. Diagnostic-grade rendering would require a separately agreed contract for physical calibration, layout, fidelity, browser/print behavior, and clinical validation.

## Risks / Trade-offs

- **[SVG output varies across Matplotlib patch versions]** → Pin a compatible dependency range and assert stable semantic content rather than byte-for-byte snapshots.
- **[Nominal paper speed and gain are mistaken for physical calibration]** → Include the visible non-diagnostic disclaimer and document that browser physical dimensions are not guaranteed.
- **[Large or long waveforms consume excessive CPU or SVG size]** → Keep dimensions bounded, characterize fixture size and render time, and defer explicit decimation until a measured need and fidelity policy exist.
- **[Matplotlib internals retain resources or expose global behavior]** → Use request-local object-oriented figures/canvases, deterministic cleanup, and repeated/concurrent tests without runtime backend mutation.
- **[Baseline centering obscures source offsets]** → Default it off, keep it display-only, and prove input immutability.
- **[Reimplementing the ECG grid differs visually from the prototype]** → Preserve the two-column 12-lead ownership and verify labels/scales; visual redesign and diagnostic parity are not required.

## Migration Plan

1. Declare the minimum pinned plotting dependency range and add the presentation module/test package.
2. Add immutable configuration, typed result/error boundaries, validation, and SVG serialization.
3. Implement the 12-lead grid, time scaling, voltage scaling, labels, and fixed safety disclaimer.
4. Add opt-in baseline centering over renderer-owned values.
5. Verify normalized-frequency use, all labels, non-empty SVG, invalid settings, input immutability, repeated/concurrent calls, and cleanup.
6. Run the focused domain/renderer suites, full regression suite, dependency checks, and strict OpenSpec validation.

Rollback removes the new renderer, tests, and plotting dependencies. Existing parsing and application workflows remain unchanged because this change adds no route or caller migration.

## Open Questions

- What bounded default SVG width and height best fit the later Flask viewer while keeping all 12 panels legible? Implementation should select and test one default without claiming physical display calibration.
- Can the renderer remain NumPy-free using the immutable channel tuples and standard-library median, or does measured rendering performance justify declaring NumPy? Prefer no NumPy dependency unless implementation evidence requires it.
