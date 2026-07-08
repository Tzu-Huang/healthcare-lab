## 1. Backend API

- [x] 1.1 Add a dcm4chee sync/retry endpoint for local Healthcare Lab orders.
- [x] 1.2 Add a dcm4chee attempt-history endpoint for local Healthcare Lab orders.
- [x] 1.3 Return clear 404/400 responses for unknown orders and non-dcm4chee-incompatible order states where applicable.
- [x] 1.4 Ensure retry responses include the updated order, latest MWL mapping, latest attempt, and success/retryable metadata.

## 2. Status Model

- [x] 2.1 Add response-level `retryable` metadata for dcm4chee MWL sync state.
- [x] 2.2 Add display-oriented status metadata that can map existing stored statuses to clearer UI labels such as pending, synced, failed, retry needed, or reconciled.
- [x] 2.3 Distinguish retryable infrastructure/read-back failures from non-retryable patient precondition or profile validation failures unless the underlying data changes.
- [x] 2.4 Preserve existing local order records and canonical mapping rows when dcm4chee sync fails.

## 3. Frontend

- [ ] 3.1 Add a Retry action to DICOM MWL order rows when the backend marks the dcm4chee sync state retryable.
- [ ] 3.2 Show latest dcm4chee sync details for the selected DICOM order, including status, retry count, timestamps, HTTP status, error type/text, and key identifiers.
- [ ] 3.3 Show dcm4chee attempt history for the selected DICOM order, including operation type, status, request target, HTTP status, error, and response payload.
- [ ] 3.4 Refresh the order list and selected-order inspection state after retry.

## 4. Verification

- [x] 4.1 Add backend tests for successful retry from a failed dcm4chee sync without duplicate MWL POST after an existing successful mapping.
- [x] 4.2 Add backend tests for retry failure preserving the local order and exposing latest error/status metadata.
- [x] 4.3 Add backend tests for dcm4chee attempt-history API output.
- [ ] 4.4 Add frontend/API contract coverage for retryable metadata and DICOM order row actions where practical.
- [ ] 4.5 Run OpenSpec validation and the relevant Healthcare Lab Python test suite.
