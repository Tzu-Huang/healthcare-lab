## Context

The current Patient page supports protocol modes for HL7 v2, FHIR, GDT, and DICOM. FHIR mode builds a Patient resource preview, and `backend/lab_store.py` can persist generic FHIR workflow records with deterministic identifiers and Medplum sync state.

The missing workflow is the bridge between local Patient creation and the generic FHIR ledger. Users expect the Patient page to create a useful Medplum-backed FHIR Patient, not only a local JSON preview.

## Goals / Non-Goals

**Goals:**

- Create local Patient records first so the UI never loses user intent when Medplum fails.
- For FHIR mode, create a paired `Patient` FHIR workflow ledger record from the local Patient.
- Attempt Medplum sync immediately after local creation.
- Surface sync status, Medplum reference, failure details, and retry from Local Patients.
- Add common FHIR Patient fields without turning this ticket into a full Patient profile editor.

**Non-Goals:**

- Build a full Medplum Patient inventory read page. Live inventory reads are reserved for later FHIR inventory tickets.
- Add a background sync worker.
- Implement full TW Core or every FHIR Patient profile field.
- Change HL7 v2, GDT, or DICOM Patient create behavior except where shared UI structure must remain coherent.

## Decisions

1. FHIR Patient create attempts Medplum sync in the same request.

   The confirmed UX is that pressing Create in FHIR mode should create the local Patient and immediately attempt Medplum sync. A failed sync should not make the create request fail in a way that hides the local record; instead, the response and Local Patients table should show `Sync failed` and expose retry.

2. Local Patient remains the UI anchor for the Patient page.

   The Patient page's Local Patients table should continue to list local Patient records. For FHIR rows, it should join the paired FHIR ledger metadata, including sync status, Medplum reference, last sync time, and error text.

3. The FHIR ledger remains the retry and idempotency authority.

   The Patient row should not own one-off Medplum columns if the existing FHIR ledger can represent the same sync state. Retry should call the existing FHIR record sync behavior for the paired ledger record.

4. Common FHIR Patient fields are scoped.

   The form should include common fields that directly map to Patient without extra workflow dependencies: `active`, MRN/identifier policy, phone, email, structured address fields, and optional managing organization reference/display. More advanced fields such as contacts, links, multiple identifiers, communication preferences, and extensions should stay out of this ticket unless required by tests.

## Risks / Trade-offs

- [Risk] Create latency increases because FHIR mode performs a Medplum request. -> Mitigation: keep the local record and return sync status; users can retry if the request fails.
- [Risk] The local Patient payload and FHIR ledger resource can drift. -> Mitigation: create or update the ledger from the freshly persisted Patient record in the same create flow.
- [Risk] Structured address fields may overlap with the existing free-text address. -> Mitigation: keep backwards-compatible address text and map structured fields into the FHIR `address` object where provided.
- [Risk] Managing organization references can be invalid in a demo environment. -> Mitigation: make it optional and pass it through only when supplied.

## Open Questions

- Should retry update the local Patient payload from current form values, or only retry the existing ledger resource?
- Should successful sync store the canonical Medplum response beyond the existing sync attempt response payload?

