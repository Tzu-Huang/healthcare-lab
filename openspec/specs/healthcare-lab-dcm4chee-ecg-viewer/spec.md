# healthcare-lab-dcm4chee-ecg-viewer Specification

## Purpose
TBD - created by archiving change add-dcm4chee-ecg-viewer. Update Purpose after archive.
## Requirements
### Requirement: Supported ECG results expose a dedicated graph action
Healthcare Lab SHALL expose `View ECG Graph` only for persisted instance results that explicitly advertise ECG rendering capability and provide the identity required to address the result-scoped viewer.

#### Scenario: Supported ECG instance shows the action
- **GIVEN** a result has a persisted result ID and explicit ECG rendering capability
- **WHEN** Healthcare Lab renders the Instance result actions
- **THEN** it shows an accessible `View ECG Graph` action
- **AND** the action targets `/viewer/ecg/<result-id>`

#### Scenario: Generic DICOM result does not imply ECG support
- **GIVEN** a result is associated with an ECG patient or order but lacks explicit ECG rendering capability
- **WHEN** Healthcare Lab renders its result actions
- **THEN** it does not show `View ECG Graph`
- **AND** it does not infer support from modality, association, artifact label, or generic viewer availability alone

#### Scenario: ECG action opens safely
- **GIVEN** a supported ECG result action is visible
- **WHEN** the user activates `View ECG Graph`
- **THEN** Healthcare Lab opens the dedicated viewer in a new tab or window
- **AND** the new browsing context is opened with `noopener`

### Requirement: ECG viewer supports direct result navigation
Healthcare Lab SHALL serve a focused ECG viewer at `/viewer/ecg/<result-id>` whose state can be reconstructed from the persisted result ID without requiring state from the originating console.

#### Scenario: User navigates directly to a result viewer
- **WHEN** a user opens a valid ECG viewer URL directly
- **THEN** the page requests the result-scoped ECG metadata and rendered graph
- **AND** it does not require an originating Patient or dcm4chee console session state

#### Scenario: User reloads the viewer
- **GIVEN** a user is viewing a valid ECG result
- **WHEN** the user reloads the page
- **THEN** Healthcare Lab reloads the same result from the result ID in the route

#### Scenario: Viewer does not disclose retrieval details
- **WHEN** the ECG viewer renders loading, success, or failure state
- **THEN** it does not display raw WADO-RS URLs, configured credentials, internal filesystem paths, or upstream response fragments

### Requirement: ECG viewer presents graph and display summary
Healthcare Lab SHALL show the application-rendered 12-lead ECG graph with display-safe lead, sample-rate, unit, and duration summary fields after successful loading.

#### Scenario: Valid ECG renders successfully
- **GIVEN** the metadata and SVG endpoints succeed for a supported result
- **WHEN** viewer loading completes
- **THEN** the page shows the rendered 12-lead graph
- **AND** it shows the available lead names, sampling frequency, normalized unit, and duration
- **AND** graph alternative text and summary labels identify the content accessibly

#### Scenario: Viewer shows loading state
- **WHEN** the viewer is waiting for ECG metadata or graph output
- **THEN** it shows a meaningful loading status
- **AND** it does not show stale success content

### Requirement: ECG viewer failures are controlled and actionable
Healthcare Lab SHALL convert result lookup, unsupported content, invalid waveform, and upstream retrieval failures into stable viewer states without exposing raw backend or dcm4chee details.

#### Scenario: Result is unsupported
- **GIVEN** the result exists but cannot be rendered as a supported ECG
- **WHEN** the metadata or graph request returns an unsupported or invalid-waveform response
- **THEN** the viewer explains that this result cannot be displayed as an ECG graph
- **AND** it does not present a broken graph as success

#### Scenario: Result is missing
- **WHEN** the viewer is opened for an unknown result ID
- **THEN** the viewer shows a controlled not-found message

#### Scenario: Upstream retrieval fails
- **WHEN** dcm4chee retrieval times out or fails upstream
- **THEN** the viewer shows a controlled upstream failure message suitable for retry
- **AND** it does not expose the upstream URL, credentials, PHI-heavy payload, or raw exception text

#### Scenario: Status changes are announced
- **WHEN** the viewer changes from loading to success or failure
- **THEN** assistive technology can perceive the updated status through meaningful live-region semantics
