## 1. Backend DiagnosticReport Read API

- [x] 1.1 Add a read-only Medplum DiagnosticReport search/fetch helper.
- [x] 1.2 Add an API route for selected Patient DiagnosticReport fetch.
- [x] 1.3 Support selected ServiceRequest narrowing with `based-on` search.
- [x] 1.4 Fallback from unsupported `based-on` search to Patient search plus server-side `basedOn[]` filtering.
- [x] 1.5 Return raw FHIR Bundle JSON plus parsed summary metadata.
- [x] 1.6 Parse DiagnosticReport relationships for `subject`, `basedOn`, `result`, `media`, `presentedForm`, and related references.
- [x] 1.7 Preserve clear auth, upstream HTTP, empty Bundle, and malformed response handling.
- [x] 1.8 Update Medplum smoke/check behavior to include DiagnosticReport fetch status without treating empty results as outage.

## 2. Medplum Console UI

- [ ] 2.1 Rework the Medplum DiagnosticReport area toward the GDT console patient-rollup pattern.
- [ ] 2.2 Auto-fetch live DiagnosticReports when a Patient is selected.
- [ ] 2.3 Auto-narrow displayed reports when a ServiceRequest is selected.
- [ ] 2.4 Keep patient-level DiagnosticReports visible and clearly labeled.
- [ ] 2.5 Render scan-friendly DiagnosticReport rows with code/display, status, date, linked order, result count, and attachment/reference count.
- [ ] 2.6 Update the raw JSON panel with live Medplum JSON when a report is selected.
- [ ] 2.7 Render related Observation, DocumentReference, and Binary references as lightweight rows.
- [ ] 2.8 Fetch related resource previews lazily when a related row is selected.
- [ ] 2.9 Clearly label live Medplum data, local submitted fallback, local-only workflow intent, fetch failed, and empty-result states.

## 3. Verification

- [x] 3.1 Add backend tests for Patient DiagnosticReport search URL and empty Bundle handling.
- [x] 3.2 Add backend tests for ServiceRequest `based-on` search and fallback filtering.
- [x] 3.3 Add backend tests for unauthorized/auth failure, upstream FHIR errors, and malformed Bundle responses.
- [x] 3.4 Add backend tests for DiagnosticReport summary and relationship parsing.
- [ ] 3.5 Add frontend/template tests for GDT-style DiagnosticReport controls and raw JSON preview behavior.
- [ ] 3.6 Run OpenSpec validation and the Healthcare Lab Python test suite.
