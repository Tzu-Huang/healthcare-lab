## ADDED Requirements

### Requirement: GDT orders use canonical MRN as Patient Number

Healthcare Lab SHALL use the selected Patient's canonical MRN in GDT field `3000` for newly created and exported GDT ECG orders while retaining protocol-specific workflow identifiers only for correlation and compatibility.

#### Scenario: New GDT ECG order is rendered

- **WHEN** Healthcare Lab renders a new GDT ECG order for a selected Patient
- **THEN** field `3000` equals the Patient's canonical MRN
- **AND** the Order snapshot contains that same MRN
- **AND** a `GDT-PAT-*` workflow identifier does not replace the MRN in field `3000`

#### Scenario: New GDT result matches by canonical MRN

- **WHEN** a GDT result contains a canonical MRN in field `3000`
- **THEN** Healthcare Lab can match it to the corresponding Patient
- **AND** an exact GDT Order identifier remains higher precedence than Patient-only matching

#### Scenario: Legacy GDT result uses prior workflow Patient Number

- **GIVEN** a previously persisted GDT context or emitted artifact used a `GDT-PAT-*` value in field `3000`
- **WHEN** a corresponding legacy result is processed
- **THEN** Healthcare Lab can resolve the legacy value through retained correlation metadata
- **AND** the Patient is still presented with its canonical MRN
