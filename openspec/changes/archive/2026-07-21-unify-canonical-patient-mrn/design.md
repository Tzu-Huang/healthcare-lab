## Context

Patient creation already allocates `MRN-000001`, `MRN-000002`, and later values from the transaction-bound `patient_mrn` sequence before rendering a protocol payload. The selected Patient mode determines whether the payload is HL7 v2, FHIR, GDT, or DICOM, so a Patient normally belongs to one server console and gaps in any individual console are expected.

The shared contract is incomplete. SQLite does not enforce MRN uniqueness, explicit values accept arbitrary trimmed text, and the GDT order workflow substitutes a generated `GDT-PAT-*` value into field `3000`. Medplum and dcm4chee also return or manage identifiers that are valid technical identities but are not MRNs. The change crosses persistence, migrations, payload builders, matching, projections, and console labels.

## Goals / Non-Goals

**Goals:**

- Make `MRN-` plus at least six decimal digits the canonical format for newly created Patients in every mode.
- Allocate from one monotonic sequence across all modes and accept gaps within a server-specific view.
- Enforce normalized MRN uniqueness transactionally and at the SQLite boundary.
- Put the canonical MRN in HL7 `PID-3`, FHIR Patient MRN identifier, GDT field `3000`, and DICOM Patient ID.
- Keep protocol-specific identifiers available under accurate names and preserve compatibility for previously emitted GDT artifacts.
- Migrate safely without silently changing a Patient's externally observed identity.

**Non-Goals:**

- Create separate MRN sequences per server or encode the Patient mode in the MRN.
- Make OIE, Medplum, a GDT device, or dcm4chee responsible for allocating Healthcare Lab MRNs.
- Replace Medplum resource ids, GDT order/correlation ids, DICOM issuers, accession numbers, or UIDs.
- Merge Patients or automatically repair ambiguous legacy duplicate identities.

## Decisions

### Use one global canonical sequence

All Patient modes consume the existing `patient_mrn` sequence. The canonical rendered value is `MRN-{number:06d}`; values naturally expand beyond six digits. A server console can therefore show non-contiguous values because Patients assigned to other modes consumed intervening values.

Separate per-server sequences were rejected because the same textual MRN could then identify different Patients across Healthcare Lab and would make future cross-server correlation unsafe. Encoding mode in the MRN was rejected because mode is routing metadata, not part of patient identity.

### Validate new explicit MRNs against the canonical format

New explicit values remain available for deterministic integration tests but are trimmed, uppercased, and required to match `^MRN-[0-9]{6,}$`. Duplicate comparison uses the normalized value. Automatic allocation uses the same normalization path and advances past collisions without reusing deleted values.

Allowing arbitrary external identifiers in the canonical MRN field was rejected because it prevents a uniform format. A future external-identity feature can add an assigning-authority-qualified identifier rather than overloading MRN.

### Enforce uniqueness in both repository logic and SQLite

Repository validation continues to produce a clear domain error before side effects. A case-insensitive unique SQLite index or equivalent normalized uniqueness key provides the final concurrency and alternate-write-path guarantee. Allocation and Patient insertion remain in one locked transaction, and integrity errors are mapped to the same stable validation outcome.

The migration audits existing rows before creating the constraint. It can normalize conforming values that differ only by case or surrounding whitespace only when doing so is unambiguous. It MUST stop with actionable diagnostics when normalized duplicates exist, and it MUST grandfather unique nonconforming legacy values rather than silently assigning a different MRN that would break downstream identity. New writes still follow the canonical format.

### Carry MRN in protocol patient-identity fields

- HL7 v2 uses canonical MRN in `PID-3` with assigning authority `HEALTHCARE_LAB`.
- FHIR Patient keeps canonical MRN under `urn:healthcare-lab:mrn`; the deterministic workflow identifier and Medplum `Patient/<id>` remain separate.
- GDT Patient and newly emitted GDT Order messages use canonical MRN in field `3000`. `GDT-PAT-*` may remain internal correlation metadata but is not rendered or labelled as MRN.
- DICOM and dcm4chee use canonical MRN as Patient ID while issuer, archive identity, accession numbers, and UIDs remain separate.

Order snapshots preserve the Patient's MRN and never consume a new Patient MRN.

### Preserve GDT result compatibility

New GDT orders and results correlate field `3000` through canonical MRN, with exact order identifiers retaining higher matching precedence. Previously persisted GDT contexts and artifacts that used `GDT-PAT-*` remain matchable through a legacy alias lookup. No new `GDT-PAT-*` value is presented as MRN.

### Label identities by meaning

Every table column or detail row named `MRN` reads the canonical Patient MRN. Protocol-specific identifiers use explicit labels such as `Medplum Reference`, `GDT Workflow Patient ID`, `Patient ID Issuer`, or the applicable DICOM UID. The API may retain compatibility fields during migration, but MRN projections must not fall back to an unrelated identifier.

## Risks / Trade-offs

- [A single sequence produces gaps in each server console] → Document gaps as expected global allocation behavior and test filtered views without assuming contiguity.
- [A legacy database contains normalized duplicates] → Abort the uniqueness migration with the conflicting row ids and values; require explicit operator resolution instead of guessing.
- [Strict format validation rejects formerly accepted external strings] → Grandfather stored legacy values and reserve a future assigning-authority-qualified external identifier capability.
- [Changing GDT field `3000` could orphan older results] → Retain legacy GDT Patient Number aliases for read/match compatibility and test both old and new artifacts.
- [FHIR inventory chooses the deterministic workflow identifier as MRN] → Select the MRN by identifier system rather than list position and display Medplum references separately.
- [Database and application uniqueness rules diverge] → Centralize normalization and cover repository, migration, API, and concurrent/collision behavior with characterization tests.

## Migration Plan

1. Add migration-time MRN audit and normalized uniqueness support without changing protocol output.
2. Detect and report normalized duplicates before installing the unique constraint; do not partially rewrite or merge rows.
3. Normalize only unambiguous conforming legacy values and preserve unique nonconforming values as grandfathered records.
4. Update Patient validation/allocation and verify all four Patient payload mappings.
5. Change new GDT Order field `3000` output and result matching while retaining legacy aliases.
6. Correct server-console projections and labels, then run repository, API, frontend, migration, and cross-protocol tests.

Rollback removes the new uniqueness structure and restores prior payload selection logic, but MRNs allocated while the change is active remain issued and MUST NOT be reused. Already transmitted canonical MRNs are not rewritten on rollback.

## Open Questions

- None for proposal scope. Supporting arbitrary upstream patient identifiers with assigning authorities remains a separate future capability.
