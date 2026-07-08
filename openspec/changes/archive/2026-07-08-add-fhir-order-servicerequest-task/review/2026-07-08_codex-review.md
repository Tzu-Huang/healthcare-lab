# Code Review: add-fhir-order-servicerequest-task

## Findings

### P1 - FHIR datetime-local occurrence blocks ServiceRequest preview

File: `frontend/static/app.js:1320`

FHIR mode stores `fhir-occurrence` from a `datetime-local` input as values like `2026-07-08T10:30` (`frontend/templates/index.html:448`, `frontend/static/app.js:1173`, `frontend/static/app.js:1214`). `validateOrderPayload` still applies the HL7-only `YYYYMMDD[HHMM[SS]]` regex to every non-empty `payload.requestedAt`, including FHIR orders. As soon as the demo preset or user enters an occurrence through the provided FHIR control, validation adds `Requested time must be YYYYMMDD...`, and `refreshOrderPreview` suppresses the ServiceRequest JSON preview. This breaks the FHIR preview/demo-preset acceptance path even though the backend accepts ISO-ish FHIR dateTime values.

Recommendation: Skip the HL7 timestamp regex for `payload.mode === "fhir"` or validate FHIR occurrence/authoredOn with a FHIR dateTime-compatible rule.

## Open Questions

- None.

## Test Gaps / Residual Risk

- Existing tests assert the FHIR fields and script strings are present, but do not exercise browser-side FHIR preview validation with a `datetime-local` occurrence value.
- Manual browser/real Medplum smoke remains skipped from `/dev-test`; automated API tests mock Medplum.

## Verdict

Changes requested.

