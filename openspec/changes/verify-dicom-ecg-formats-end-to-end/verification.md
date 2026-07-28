## Automated verification

- Date: 2026-07-28
- Tested product commit: `5cc6a47`
- Result: pass
- ECG and dcm4chee unit/integration/frontend/documentation suite: 96 tests
  passed.
- Fixture manifest validator: passed for both local-only source files with PHI
  values suppressed.
- Runtime dependency import: pydicom 3.0.2 and Matplotlib 3.11.1.
- OpenSpec strict validation: passed.
- Git diff hygiene: passed.

## Environment-dependent manual verification

- Status: blocked, not executed.
- Reason: both supplied source DICOM files contain identifying attributes and
  have no positive de-identification declaration or documented method.
- Safety decision: the sources remain local-only and excluded from source
  control and acceptance evidence. They MUST NOT be uploaded to a shared
  dcm4chee instance.
- Unblock condition: produce or obtain reviewed sanitized synthetic derivatives
  for both SOP Classes, record their hashes and invariant checks in the
  manifest, then execute the bounded checklist in
  `docs/ecg-viewer-verification.md`.
