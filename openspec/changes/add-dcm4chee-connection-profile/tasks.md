## 1. Connection Profile Model

- [x] 1.1 Add a dcm4chee connection profile shape with local Docker defaults.
- [x] 1.2 Include DIMSE, MWL, DICOMweb, viewer, auth, TLS, and security-placeholder fields.
- [x] 1.3 Keep the profile keyed by `local-dcm4chee` and expose display/environment names.

## 2. Backend Loading And Validation

- [x] 2.1 Add backend profile loading for the named dcm4chee profile.
- [x] 2.2 Add validation that reports missing or invalid required values clearly.
- [x] 2.3 Add a diagnostic endpoint or equivalent backend output for profile status.
- [x] 2.4 Ensure future MWL/order code can consume the profile without reading generic server fields directly.

## 3. Documentation And Defaults

- [ ] 3.1 Document the local dcm4chee profile defaults in `.env.example` or README context.
- [ ] 3.2 Clarify that local auth/TLS defaults are lab-only and not production security.

## 4. Verification

- [x] 4.1 Add focused tests for profile loading and validation errors.
- [ ] 4.2 Run the relevant Python test suite.
- [ ] 4.3 Run OpenSpec validation for this change.
