## Automated verification

- Date: 2026-07-28
- Tested product commit: `5cc6a47`
- Result: pass
- ECG and dcm4chee unit/integration/frontend/documentation suite: 96 tests
  passed.
- Fixture manifest validator: passed for both synthetic local-test source files
  with attribute values suppressed.
- Runtime dependency import: pydicom 3.0.2 and Matplotlib 3.11.1.
- OpenSpec strict validation: passed.
- Git diff hygiene: passed.

## Fixture safety clarification

- The user confirmed on 2026-07-28 that both supplied files contain synthetic
  test identities and no real patient data.
- The source binaries remain excluded from source control, while their hashes,
  synthetic confirmation, identifying-attribute names, and waveform invariants
  remain recorded in the manifest.

## Live dcm4chee and browser verification

- Date: 2026-07-28
- Tested commit: `46c7326`
- Environment: local `deploy/docker-compose.yml` stack with dcm4chee and
  Healthcare Lab running.
- Fixture preparation: generated local-only derivatives with canonical
  Healthcare Lab MRN and order mapping identifiers; waveform/channel content
  remained unchanged and derivative binaries were not committed.
- STOW-RS: HTTP 200 for both 12-lead ECG Waveform Storage and General ECG
  Waveform Storage derivatives.
- Result refresh: succeeded for synthetic patient record 19 and mapped both
  ECG instances with `ecgGraph=true`.
- Result IDs: General ECG 15; 12-lead ECG 16.
- Metadata and SVG endpoints: HTTP 200 for both results.
- Browser verification: both `/viewer/ecg/<result-id>` pages reached
  `ECG graph loaded.` with no console errors.
- Display contract: 12 canonical lead labels, 1,000 Hz, mV, 10 seconds, visible
  graph, and `For demonstration only - not for diagnostic use` all passed for
  both SOP Classes.
- Focused verification: 13 tests passed, fixture validator passed, strict
  OpenSpec validation passed, and Git diff hygiene passed.
