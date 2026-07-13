## 1. Persisted MRN Allocation

- [ ] 1.1 Add a non-destructive SQLite migration for a named local identifier sequence and initialize the MRN sequence for new and existing demo databases.
- [ ] 1.2 Implement transactional allocation of `MRN-` identifiers with minimum six-digit padding, monotonic restart behavior, and collision skipping.
- [ ] 1.3 Update Patient validation and creation to accept blank MRN, preserve explicit MRN values, and reject exact duplicates before payload creation or downstream sync.

## 2. Patient Preset and Protocol Propagation

- [ ] 2.1 Change the Patient demo preset and form validation so blank MRN requests automatic allocation while manual MRN entry remains supported.
- [ ] 2.2 Render `Generated on create` in unsaved Patient previews and show the persisted allocated MRN after creation.
- [ ] 2.3 Verify generated MRNs propagate through HL7, FHIR, GDT, and DICOM Patient payloads and remain unchanged when copied into Orders.

## 3. Consistent Order Identity Presentation

- [ ] 3.1 Add Visit Number to Local Orders and standardize its core columns as Order ID, mode, MRN, Visit Number, patient name, code, status, and Taipei Order Created At.
- [ ] 3.2 Add Order ID, MRN, Visit Number, and Taipei Order Created At to patient-centered OIE Order rows while preserving ACK, sent time, selection, and send actions.
- [ ] 3.3 Align new UI and response naming on Visit Number while retaining compatibility with the existing `visitId` Order field.

## 4. Verification and Documentation

- [ ] 4.1 Add store tests for fresh allocation, restart persistence, deletion non-reuse, manual MRNs, collision skipping, and duplicate rejection without side effects.
- [ ] 4.2 Add API and frontend contract tests for blank-MRN creation, generated preview behavior, protocol propagation, and both order-table column sets.
- [ ] 4.3 Update user-facing documentation with automatic MRN behavior, identifier formats, uniqueness scope, and the PID-3/PV1-19/ORC-2/OBR-2 mappings.
- [ ] 4.4 Run the complete test suite and OpenSpec validation, recording any environment-dependent verification separately.
