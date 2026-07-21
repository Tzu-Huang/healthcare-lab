## 1. Characterize and migrate MRN persistence

- [ ] 1.1 Add focused characterization for global cross-mode allocation, canonical explicit-MRN validation, normalized duplicates, collision skipping, restart, deletion, and rollback behavior.
- [ ] 1.2 Add a schema migration that audits existing MRNs, reports normalized collisions without partial mutation, preserves unique nonconforming legacy identities, and installs database-enforced normalized uniqueness.
- [ ] 1.3 Centralize canonical MRN normalization and format validation, then map database uniqueness failures to the existing Patient validation error without Patient or downstream side effects.

## 2. Propagate canonical MRN through protocols

- [ ] 2.1 Verify and pin HL7 `PID-3`, FHIR `urn:healthcare-lab:mrn`, and DICOM Patient ID/MWL mappings to the Patient's canonical MRN while preserving their separate assigning authority, workflow, Medplum, issuer, accession, and UID identities.
- [ ] 2.2 Change new GDT Patient and Order field `3000` payloads and snapshots to use canonical MRN while retaining any required `GDT-PAT-*` value only as internal correlation metadata.
- [ ] 2.3 Update GDT result matching so exact Order identifiers retain precedence, canonical MRN supports Patient matching, and previously persisted `GDT-PAT-*` aliases remain compatible.

## 3. Correct API projections and console labels

- [ ] 3.1 Make Medplum Patient MRN projection select the `urn:healthcare-lab:mrn` identifier by system instead of identifier order or deterministic workflow identifier fallback.
- [ ] 3.2 Audit Patient, Order, OIE, Medplum, GDT, and dcm4chee tables/details so `MRN` always displays canonical MRN and protocol-specific identifiers use explicit labels.
- [ ] 3.3 Update previews, placeholders, validation messages, and documentation to describe the global sequence, canonical `MRN-NNNNNN` format, and expected per-server gaps.

## 4. Verify the unified contract

- [ ] 4.1 Add repository and migration tests for database-enforced uniqueness, legacy database behavior, sequence monotonicity, and concurrent or collision writes.
- [ ] 4.2 Add API/template/service tests covering all four Patient modes plus GDT new/legacy matching and FHIR identifier selection.
- [ ] 4.3 Add frontend tests that distinguish canonical MRN from Medplum, GDT, and DICOM identifiers in every affected console.
- [ ] 4.4 Run focused suites, the full automated test suite, syntax/format checks, and strict OpenSpec validation; record any live OIE, Medplum, GDT, or dcm4chee verification deferred to `/dev-test`.
