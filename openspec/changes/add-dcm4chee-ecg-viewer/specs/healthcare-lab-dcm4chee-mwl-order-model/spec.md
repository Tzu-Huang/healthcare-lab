## MODIFIED Requirements

### Requirement: DICOM result actions preserve viewer and retrieve access
Healthcare Lab SHALL expose dcm4chee viewer and retrieve actions from the PACS-style result browser when URLs are available, and SHALL add a Healthcare Lab ECG graph action only when a persisted instance result explicitly advertises ECG rendering capability.

#### Scenario: User opens a matched study
- **GIVEN** a matched Study row has a dcm4chee viewer URL
- **WHEN** the user activates the viewer action
- **THEN** Healthcare Lab opens the configured dcm4chee viewer link for that study

#### Scenario: User copies retrieve links
- **GIVEN** a Study, Series, or Instance row has a retrieve URL
- **WHEN** the user activates the copy/retrieve action
- **THEN** Healthcare Lab exposes the corresponding dcm4chee retrieve URL without changing the local reconciliation state

#### Scenario: User opens a supported ECG graph
- **GIVEN** an Instance row has a persisted result ID and explicit ECG rendering capability
- **WHEN** the user activates `View ECG Graph`
- **THEN** Healthcare Lab opens `/viewer/ecg/<result-id>` in a new tab or window with `noopener`
- **AND** the existing configured dcm4chee viewer action remains available when its URL is present

#### Scenario: Unsupported result preserves generic actions
- **GIVEN** a Study, Series, or Instance result does not explicitly advertise ECG rendering capability
- **WHEN** Healthcare Lab renders its available result actions
- **THEN** it does not show `View ECG Graph`
- **AND** existing artifact, generic viewer, and retrieve actions remain governed by their existing URLs
