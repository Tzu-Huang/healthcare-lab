## 1. Retrieval Boundary

- [ ] 1.1 Add result-repository/service lookup that distinguishes missing results from rows without complete study, series, and instance identifiers
- [ ] 1.2 Add a typed WADO-RS transport result and error model for timeout, upstream HTTP, size, media-type, and multipart failures
- [ ] 1.3 Implement profile-owned instance URL construction and request behavior with authentication, TLS verification, timeout, DICOM Accept headers, and bounded streaming

## 2. DICOM Response Normalization

- [ ] 2.1 Implement strict bare `application/dicom` extraction
- [ ] 2.2 Implement standards-aware single-instance `multipart/related` extraction with boundary, part media-type, count, and empty-payload validation
- [ ] 2.3 Add transport/content tests for bare, multipart, malformed multipart, unsupported media, timeout, upstream failure, and declared or streamed oversize responses

## 3. ECG Application Service

- [ ] 3.1 Compose result lookup, WADO-RS retrieval, in-memory DICOM decoding, and normalized ECG parsing behind a result-ID service
- [ ] 3.2 Define the display-safe metadata/capability projection without raw tags, PHI-heavy fields, retrieve URLs, or secrets
- [ ] 3.3 Compose the existing SVG renderer and add service tests for valid output, unsupported SOP Class, invalid DICOM, and malformed waveform errors

## 4. Result-Scoped APIs

- [ ] 4.1 Add `GET /api/dcm4chee/results/<result-id>/ecg` with the stable safe metadata response
- [ ] 4.2 Add `GET /api/dcm4chee/results/<result-id>/ecg/render.svg` with `image/svg+xml` output
- [ ] 4.3 Add typed API error translation for controlled 404, 409, 415, 422, and 502 responses
- [ ] 4.4 Add API tests proving arbitrary URL/path input is unavailable and errors disclose no credentials, internal URLs, raw metadata, or upstream payloads

## 5. End-to-End Compatibility

- [ ] 5.1 Add mocked reconciled-result end-to-end tests for both bare and multipart WADO-RS responses
- [ ] 5.2 Run focused ECG, dcm4chee result, settings/profile, and API tests and record verification evidence
- [ ] 5.3 Run the full automated test suite and confirm result refresh, reconciliation, and generic viewer URLs remain unchanged
