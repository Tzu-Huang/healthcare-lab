## 1. Integration Route And Configuration

- [ ] 1.1 Confirm the local dcm4chee MWL REST create endpoint and required payload shape against the Docker runtime.
- [x] 1.2 Add configurable dcm4chee UID root support for Study Instance UID generation.
- [x] 1.3 Add backend helpers that resolve and validate the selected dcm4chee profile before outbound MWL creation.
- [x] 1.4 Keep HL7 ORM feeding out of scope for this implementation.

## 2. Identifier And Payload Mapping

- [x] 2.1 Generate namespace-aware local dcm4chee identifiers for local order, accession, requested procedure, scheduled procedure step, and Study Instance UID.
- [x] 2.2 Build DICOM JSON MWL payloads with required Patient demographic fields.
- [x] 2.3 Build DICOM JSON MWL payloads with required Scheduled Procedure Step/order fields.
- [x] 2.4 Map Scheduled Station AE Title and MWL AE title from the selected dcm4chee profile.

## 3. Local Persistence And Audit

- [x] 3.1 Persist dcm4chee mapping metadata for the local Healthcare Lab order.
- [x] 3.2 Persist outbound MWL request payloads and dcm4chee response status/body.
- [x] 3.3 Persist attempt status, timestamps, generated identifiers, profile name, and error details.
- [x] 3.4 Preserve local Healthcare Lab orders when dcm4chee creation fails.

## 4. dcm4chee MWL Creation

- [x] 4.1 Implement `POST /dcm4chee-arc/aets/{AETitle}/rs/mwlitems` creation using `application/dicom+json`.
- [x] 4.2 Handle profile validation failures without sending an outbound request.
- [x] 4.3 Handle missing-patient/precondition failures with a clear status and retained response body.
- [x] 4.4 Handle HTTP/network/payload failures without rolling back the local order.
- [x] 4.5 Return dcm4chee sync metadata from the order creation path or a related status endpoint.

## 5. UI / Documentation

- [x] 5.1 Surface dcm4chee MWL sync status where local order status is shown, if practical for this ticket.
- [x] 5.2 Document the MWL REST route, local UID root default, and patient precondition behavior.
- [x] 5.3 Clarify that AP MWL query, C-STORE reconciliation, and viewer-link consumption remain future work.

## 6. Verification

- [x] 6.1 Add tests for UID and identifier generation.
- [x] 6.2 Add tests for DICOM JSON patient and Scheduled Procedure Step payload mapping.
- [x] 6.3 Add tests for successful dcm4chee MWL create with recorded request/response metadata.
- [x] 6.4 Add tests for profile validation failure and missing-patient/precondition failure.
- [x] 6.5 Add tests proving local orders are preserved when dcm4chee sync fails.
- [x] 6.6 Run OpenSpec validation and the relevant Healthcare Lab Python test suite.
