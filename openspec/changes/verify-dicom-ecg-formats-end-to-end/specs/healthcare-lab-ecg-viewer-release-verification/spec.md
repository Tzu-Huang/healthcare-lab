## ADDED Requirements

### Requirement: ECG fixtures have an explicit safe-use contract
Healthcare Lab SHALL use the supplied 12-lead and General ECG Waveform Storage
instances as packaged verification fixtures only after recording provenance,
cryptographic identity, de-identification review, SOP Class, and expected
normalized waveform invariants. If a source instance is not proven
de-identified, the system MUST use a documented sanitized derivative or keep
the source outside packaged test artifacts.

#### Scenario: Reviewed fixture is eligible for packaged tests
- **WHEN** a fixture manifest confirms de-identification and records its identity and expected waveform invariants
- **THEN** automated verification may load that exact fixture as a packaged test input

#### Scenario: Fixture safety is unresolved
- **WHEN** a source fixture cannot be positively certified as de-identified
- **THEN** it is excluded from packaged artifacts unless a documented sanitized derivative preserves the required waveform and channel metadata

### Requirement: Both supported ECG formats pass the assembled release gate
Healthcare Lab SHALL provide automated end-to-end verification for 12-lead ECG
Waveform Storage and General ECG Waveform Storage from a persisted reconciled
result through WADO-RS response extraction, normalized parsing, SVG rendering,
result-scoped APIs, and the dedicated viewer route.

#### Scenario: Twelve-lead waveform renders end to end
- **WHEN** a persisted result retrieves the reviewed 12-lead ECG Waveform Storage fixture
- **THEN** the viewer displays a non-empty graph and display-safe summary for that result

#### Scenario: General ECG waveform renders end to end
- **WHEN** a persisted result retrieves the reviewed General ECG Waveform Storage fixture
- **THEN** the viewer displays a non-empty graph and display-safe summary for that result

### Requirement: Release verification asserts normalized waveform and display invariants
The release gate SHALL verify both fixtures produce 12 canonical leads, 10,000
samples per channel, a 1,000 Hz sampling frequency, a 10-second duration,
microvolt-calibrated values normalized to mV, all canonical graph labels, and
the demonstration-only/non-diagnostic classification.

#### Scenario: Known fixture invariants agree across boundaries
- **WHEN** either supported fixture completes parsing, rendering, and viewer loading
- **THEN** its normalized model, API summary, SVG labels, and safety classification agree with the declared fixture invariants

### Requirement: ECG release regressions fail safely
The release gate SHALL cover non-ECG DICOM, missing Waveform Sequence, unknown
units, truncated sample data, malformed multipart data, upstream timeout or
failure, unknown results, and unauthorized or unconfigured dcm4chee profiles.
API and viewer failures MUST remain controlled and MUST NOT disclose PHI,
credentials, internal paths, raw DICOM metadata, or upstream payload fragments.

#### Scenario: Invalid waveform content is rejected safely
- **WHEN** retrieved content has missing waveform data, unknown units, or truncated samples
- **THEN** the API and viewer expose a stable unsupported or invalid-waveform state without sensitive implementation details

#### Scenario: Retrieval or profile failure is rejected safely
- **WHEN** retrieval fails upstream or the active profile is unauthorized or unconfigured
- **THEN** the API and viewer expose a stable actionable failure without credentials, internal endpoints, or upstream response content

### Requirement: Existing dcm4chee result workflows remain verified
The ECG release gate SHALL verify that result refresh, reconciliation and
grouping, generic viewer links, artifact actions, and capability-gated ECG
actions retain their documented behavior for ECG and non-ECG results.

#### Scenario: Mixed results retain compatible actions
- **WHEN** refreshed results contain supported ECG instances and generic non-ECG artifacts
- **THEN** grouping and existing generic actions remain available while `View ECG Graph` appears only on explicitly capable ECG results

### Requirement: The supported deployment path includes ECG runtime dependencies
Healthcare Lab SHALL verify that the supported runtime and container dependency
installation path can parse and render ECG instances without undeclared manual
package installation.

#### Scenario: Supported deployment renders an ECG
- **WHEN** Healthcare Lab is installed or built through the documented supported deployment path
- **THEN** both supported ECG formats can be parsed and rendered without installing an additional runtime dependency manually

### Requirement: Operators have a bounded ECG acceptance and troubleshooting guide
Healthcare Lab SHALL document supported SOP Class UIDs, configuration,
dependency expectations, the manual `View ECG Graph` verification sequence,
stable failure categories and recovery actions, display limitations, and the
demonstration-only/non-diagnostic classification.

#### Scenario: Operator verifies the visible workflow
- **WHEN** an operator follows the checklist with a configured synthetic result for each supported SOP Class
- **THEN** the checklist demonstrates result refresh, `View ECG Graph`, the dedicated viewer, graph labels, display summary, and safety notice

#### Scenario: Deferred interactions remain outside MVP
- **WHEN** an operator needs zoom, calipers, annotations, print layout, or export
- **THEN** the guide identifies those interactions as unsupported follow-up scope rather than implying current availability
