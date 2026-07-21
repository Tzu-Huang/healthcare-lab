## Why

Healthcare Lab allocates Patient MRNs from one local sequence, but protocol consoles and payload paths can expose protocol-specific identifiers as if they were MRNs, most notably the generated GDT Patient Number. A single canonical MRN contract is needed so every Patient has one globally unique, recognizable MRN regardless of whether its creation mode is HL7 v2, FHIR, GDT, or DICOM.

## What Changes

- Define one global, persistent Patient MRN sequence shared by all four Patient modes; per-server views may therefore contain gaps in their visible MRN numbers.
- Normalize and validate MRNs at Patient creation and enforce uniqueness at the SQLite boundary, including collision-safe automatic allocation and explicit-MRN handling.
- Carry the canonical MRN in HL7 `PID-3`, the FHIR Patient MRN identifier, GDT field `3000`, and DICOM Patient ID `(0010,0020)`.
- Keep server- or protocol-owned identifiers such as Medplum resource references, GDT workflow identifiers, and DICOM issuer/UID values distinct from MRN in payload mappings and UI labels.
- Change GDT order payloads so field `3000` identifies the Patient by canonical MRN rather than by the generated `GDT-PAT-*` workflow identifier; retain any needed GDT workflow identifier as internal correlation metadata.
- Define safe behavior for existing databases, including pre-migration collision detection and preservation of previously issued sequence values.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `healthcare-lab-patient-mrn-allocation`: Strengthen the existing allocator into a normalized, database-enforced global MRN contract and define propagation and presentation across all Patient modes.
- `healthcare-lab-dashboard-gdt-order-flow`: Require GDT Patient and Order field `3000` to carry the canonical MRN while keeping GDT workflow identifiers separate.

## Impact

- Patient validation, allocation, SQLite schema/migration, and repository transactions.
- HL7, FHIR, GDT, and DICOM Patient/Order payload builders and matching behavior.
- OIE, Medplum, GDT, dcm4chee, Patient, and Order projections or table labels that expose MRN or protocol-specific identifiers.
- Existing MRN and GDT workflow tests, migration characterization, and cross-protocol integration coverage.
- No Linear issue or external dependency is linked to this proposal.
