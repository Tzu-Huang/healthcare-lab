## ADDED Requirements

### Requirement: ECG retrieval is scoped to a persisted result
Healthcare Lab SHALL initiate ECG retrieval only from a persisted dcm4chee
result ID and MUST NOT accept a caller-provided upstream URL or filesystem path.

#### Scenario: Resolve an instance result
- **WHEN** a client requests ECG output for a persisted result containing study, series, and SOP Instance retrieval identifiers
- **THEN** the system constructs the retrieval target from those identifiers and the authoritative dcm4chee profile

#### Scenario: Reject an unknown result
- **WHEN** a client requests ECG output for a result ID that does not exist
- **THEN** the system returns a controlled 404 error without making an upstream request

#### Scenario: Reject a non-instance result
- **WHEN** a persisted result does not identify one retrievable SOP Instance
- **THEN** the system returns a controlled 409 error without making an upstream request

#### Scenario: Public input cannot select a fetch target
- **WHEN** a client calls either ECG route
- **THEN** no request parameter, query value, or body field can supply an upstream URL or filesystem path

### Requirement: WADO-RS retrieval reuses the dcm4chee profile
Healthcare Lab SHALL retrieve the selected instance through the configured
dcm4chee WADO-RS endpoint and SHALL reuse the profile's authentication, TLS
verification, and timeout behavior.

#### Scenario: Configured transport behavior is applied
- **WHEN** the service retrieves a valid instance
- **THEN** the WADO-RS request uses the configured endpoint, credentials or authentication mode, TLS verification setting, and timeout

#### Scenario: Upstream timeout is controlled
- **WHEN** dcm4chee does not respond within the configured timeout
- **THEN** the system aborts the request and returns a controlled 502 error without exposing the upstream endpoint or credentials

#### Scenario: Upstream HTTP failure is controlled
- **WHEN** dcm4chee rejects or fails the WADO-RS request
- **THEN** the system returns a controlled 502 error without copying PHI-heavy response content into the API error

### Requirement: Retrieved response bytes are bounded
Healthcare Lab SHALL enforce an application-controlled maximum WADO-RS
response size while reading the response and MUST stop processing once that
limit is exceeded.

#### Scenario: Response within the limit is accepted
- **WHEN** a valid DICOM response remains within the configured maximum size
- **THEN** the complete payload is made available to DICOM decoding

#### Scenario: Response exceeds the limit
- **WHEN** the declared or streamed response size exceeds the configured maximum
- **THEN** retrieval is aborted before parsing and the system returns a controlled 502 error

### Requirement: Bare and multipart DICOM responses are normalized
Healthcare Lab SHALL accept a bare `application/dicom` instance and a valid
single-instance `multipart/related` response whose related type is
`application/dicom`, and SHALL reject unsupported or ambiguous content.

#### Scenario: Accept bare DICOM
- **WHEN** WADO-RS returns a non-empty `application/dicom` response
- **THEN** the response bytes are passed as one DICOM instance to the decoder

#### Scenario: Accept one multipart DICOM part
- **WHEN** WADO-RS returns a valid `multipart/related` response with a boundary and exactly one non-empty `application/dicom` part
- **THEN** that part's bytes are passed as one DICOM instance to the decoder

#### Scenario: Reject malformed multipart
- **WHEN** a multipart response has a missing or invalid boundary, malformed framing, no DICOM part, or more than one candidate DICOM part
- **THEN** the system returns a controlled 422 error and does not invoke the ECG parser

#### Scenario: Reject unsupported media type
- **WHEN** WADO-RS returns a media type outside the supported bare or related DICOM forms
- **THEN** the system returns a controlled 415 error

### Requirement: Retrieved ECG uses normalized parsing and rendering
Healthcare Lab SHALL decode the retrieved DICOM instance in memory, pass it to
the normalized ECG parser, and use the framework-independent ECG renderer for
graph output.

#### Scenario: Valid reconciled ECG renders end to end
- **WHEN** a persisted instance result resolves to a valid supported DICOM ECG response
- **THEN** the graph route returns a non-empty SVG produced from the normalized waveform

#### Scenario: Unsupported ECG SOP Class is controlled
- **WHEN** the retrieved instance declares a SOP Class outside the parser's supported ECG allowlist
- **THEN** the system returns a controlled 415 error

#### Scenario: Invalid DICOM or waveform is controlled
- **WHEN** the retrieved payload cannot be decoded as DICOM or fails normalized waveform validation
- **THEN** the system returns a controlled 422 error without exposing raw metadata or exception text

### Requirement: Result-scoped ECG APIs are stable and disclosure-safe
Healthcare Lab SHALL expose `GET /api/dcm4chee/results/<result-id>/ecg` for
display metadata and capability and
`GET /api/dcm4chee/results/<result-id>/ecg/render.svg` for the graph. Responses
MUST exclude non-allowlisted DICOM metadata, credentials, and internal
retrieval details.

#### Scenario: Metadata response is display-safe
- **WHEN** a valid ECG metadata request succeeds
- **THEN** the response contains stable result and normalized waveform display fields but excludes patient-identifying raw tags, retrieve URLs, and profile secrets

#### Scenario: SVG response uses the renderer media type
- **WHEN** a valid ECG graph request succeeds
- **THEN** the response body is the rendered graph with media type `image/svg+xml`

#### Scenario: Error response is disclosure-safe
- **WHEN** either route fails
- **THEN** the response contains a stable application error code and safe summary without raw DICOM values, credentials, internal URLs, or upstream payload fragments

### Requirement: Existing dcm4chee result behavior remains compatible
Healthcare Lab SHALL add ECG retrieval without changing existing result
refresh, reconciliation, or generic viewer-link behavior.

#### Scenario: Existing result workflows are unchanged
- **WHEN** dcm4chee result refresh and reconciliation run after ECG routes are added
- **THEN** their existing records, snapshots, and viewer URLs retain their prior behavior
