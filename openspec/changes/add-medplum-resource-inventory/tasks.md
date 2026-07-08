## 1. Medplum Inventory API

- [x] 1.1 Add or reuse API support for listing FHIR ledger records with resource type, sync status, Medplum reference, Patient relation metadata, and local submitted JSON.
- [x] 1.2 Add API support for fetching Medplum live JSON for a selected synced resource reference.
- [x] 1.3 Return clear fallback metadata when Medplum live fetch fails and local submitted JSON is used.
- [x] 1.4 Ensure retry from the Medplum page uses the existing idempotent `/api/fhir/records/<id>/sync` path.

## 2. Patient-Centered Inventory UI

- [ ] 2.1 Enable the Medplum sidebar navigation item and add a Medplum view.
- [ ] 2.2 Add resource-type and sync-status filtering for the supported resource types.
- [ ] 2.3 Add Patient selection and show resources that directly reference the selected Patient.
- [ ] 2.4 Display sync status, Medplum reference, last error, and source label for each row.

## 3. Raw JSON And Retry UX

- [ ] 3.1 Show raw Medplum live JSON for selected synced resources when live fetch succeeds.
- [ ] 3.2 Show local submitted JSON for pending/failed records and for synced records when live fetch fails.
- [ ] 3.3 Label fallback previews clearly so local submitted JSON is not presented as live Medplum data.
- [ ] 3.4 Expose Retry for `Pending sync` and `Sync failed` rows, disable concurrent retry for `Syncing`, and refresh row state after retry.

## 4. Verification

- [x] 4.1 Add backend tests for live JSON fetch success, fetch failure fallback metadata, and retry behavior.
- [ ] 4.2 Add frontend or API regression coverage for Medplum page row rendering, Patient filtering, raw JSON preview source labels, and retry visibility.
- [ ] 4.3 Run OpenSpec validation.
- [ ] 4.4 Run the Healthcare Lab Python test suite.
