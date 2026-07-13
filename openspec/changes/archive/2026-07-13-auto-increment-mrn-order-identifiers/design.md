## Context

Patient creation currently requires an MRN, and the browser demo preset supplies the same `MRN-A04-001` value every time. `local_patient_records.mrn` is required but not unique, while inbound ORU matching selects the newest Patient with a matching MRN. Reusing the preset can therefore make patient and result attribution ambiguous. Orders already persist Patient MRN, visit number, placer order number, and timestamps, but Local Orders and patient-centered OIE Orders expose different subsets of those values.

The change spans the SQLite store, Patient API validation, protocol payload generation, browser preview behavior, and two worklist presentations. Existing local databases may already contain duplicate MRNs and persisted messages whose identifiers must not be silently rewritten.

## Goals / Non-Goals

**Goals:**

- Allocate stable, monotonic demo MRNs when Patient creation omits MRN.
- Preserve manual MRN entry for external-system and edge-case testing.
- Reject newly requested duplicate local MRNs before creating dependent protocol resources.
- Keep identifier allocation server-authoritative and persistent across application restarts.
- Present the same core order identity in Local Orders and patient-centered OIE Orders.
- Use precise HL7 names and mappings for PID-3, PV1-19, ORC-2, and OBR-2.

**Non-Goals:**

- Introducing an Encounter table or supporting multiple visits per local Patient.
- Renumbering existing duplicate Patients or rewriting their persisted ADT, ORM, ORU, FHIR, GDT, or DICOM payloads.
- Implementing enterprise assigning-authority or MPI reconciliation.
- Replacing placer and filler order identifiers with one ambiguous generic database field.

## Decisions

### Allocate automatic MRNs in the SQLite store

The store will own a persistent named sequence and allocate `MRN-` followed by a minimum of six decimal digits. Allocation and Patient insertion will occur in the same store-controlled transaction. A candidate already used by an explicitly supplied MRN will be skipped.

This is preferred over browser-side allocation because multiple tabs can predict the same value, and over `MAX(mrn) + 1` because manual identifiers and concurrent requests make that calculation fragile. The sequence is local to the demo database, survives application restarts, never decrements after Patient deletion, and resets only when the database is recreated.

### Treat blank MRN as an explicit request for automatic allocation

The Patient API will accept an omitted or blank MRN and allocate it before building any protocol-specific payload or dependent sync record. A supplied MRN will be trimmed and preserved without case conversion so external identifier fidelity is retained.

The browser preset will leave MRN blank and render `Generated on create` in previews. It will not display a speculative next number. Manual entry remains available in the same field.

### Reject new exact duplicate MRNs at the application boundary

Before insertion, the store will reject an exact MRN already present in `local_patient_records` and return a validation response that identifies the conflicting value. The check applies to both generated and manual values and occurs before FHIR or dcm4chee synchronization begins.

The first implementation will not add a database unique index because an existing demo database may already contain duplicates and startup migration must not fail or silently mutate clinical identifiers. Existing duplicates remain readable; a database reset is the supported cleanup path for demo data. The store lock and transaction remain the application concurrency boundary.

### Preserve Patient and visit values as Order snapshots

Order creation will continue copying the selected Patient MRN and current visit number into the Order record and persisted payload. The Patient MRN is not regenerated per Order. The current visit number remains associated with the local Patient for this MVP, while UI and API naming will prefer `visitNumber` and retain compatibility with the existing `visitId` response field where required.

### Keep precise identifier semantics in worklists

The primary order identity is the placer order number persisted in `localOrderNumber` and emitted consistently in `ORC-2` and `OBR-2`. A filler order number remains a separate field when supplied by a downstream system. Visit Number maps to `PV1-19`; `PV1-1` remains the Set ID value `1`.

Local Orders and patient-centered OIE Orders will expose Order ID, MRN, Visit Number, order code, status, and Order Created At. The creation value comes from the persisted Order `createdAt` and is rendered as an unambiguous Taipei timestamp. ACK and sent-time columns remain OIE-specific operational context.

## Risks / Trade-offs

- [Legacy databases can retain duplicate MRNs] -> Reject all new duplicates, document database reset as the demo cleanup path, and do not silently reassign persisted clinical identifiers.
- [Application-level uniqueness is weaker than a database unique index] -> Keep allocation and insertion inside the store lock/transaction and defer a unique index until a deliberate duplicate-data migration exists.
- [Sequential identifiers expose record volume] -> Accept this for a local demonstration environment; do not present the allocator as a production MRN authority.
- [Wide OIE tables can become harder to scan] -> Use concise labels, existing responsive table scrolling, and keep the selected Patient context while still showing MRN for screenshots and independent row verification.
- [Visit terminology changes can break frontend assumptions] -> Prefer `visitNumber` in new presentation code while maintaining the existing API alias during this change.

## Migration Plan

1. Add and initialize the local MRN sequence without modifying existing Patient rows.
2. Update Patient validation and creation so blank MRN allocation and duplicate rejection happen before payload creation or downstream sync.
3. Update the preset, preview, and both order worklists.
4. Add regression coverage for a fresh database, restart persistence, manual identifiers, collision skipping, duplicate rejection, payload propagation, and worklist columns.
5. Roll back by reverting the application change; existing generated MRNs remain ordinary valid MRN strings and require no data rollback.

## Open Questions

None for this proposal. A future Encounter-focused change must decide how multiple Visit Numbers relate to one Patient.
