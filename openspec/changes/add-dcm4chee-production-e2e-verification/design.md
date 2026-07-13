## Context

Recent archived work added the durable dcm4chee order model, connection profile, patient precondition handling, MWL create/read-back/retry, explicit MWL verification, C-STORE result reconciliation through dcm4chee QIDO, and PACS-style frontend result browsing.

ZAC-42 is not another isolated integration primitive. It is an acceptance layer that proves the complete workflow can be repeated in the lab and that Healthcare Lab operators can see the AP-returned result in the UI.

The user also requested a simulated AP-return record with uploaded PDF or DICOM data so Healthcare Lab UI display can be verified without waiting for a live AP run.

## Goals / Non-Goals

**Goals:**

- Provide a repeatable production-like E2E verification path from Healthcare Lab DICOM patient/order creation to frontend result display.
- Create or expose demo presets/fixtures that produce deterministic patient/order data and capture the identifiers needed for AP and dcm4chee checks.
- Verify dcm4chee MWL creation and AP-facing MWL queryability using the existing dcm4chee profile and canonical PACS/MWL ledger.
- Support a simulated AP-return fixture that can attach or record a PDF artifact and/or DICOM result metadata/object for UI and reconciliation verification.
- Capture evidence from the verification run: patient ID, issuer, accession number, requested procedure ID, scheduled procedure step ID, study/series/SOP UIDs when available, MWL endpoint, archive endpoint, AP AE title, statuses, and timestamps.
- Provide an operator SOP with startup, ports, AE titles, expected identifiers, manual live AP steps, automated checks, and troubleshooting.

**Non-Goals:**

- Implement AP-side MWL query or C-STORE logic inside Healthcare Lab.
- Replace dcm4chee-arc as the PACS/MWL source of truth.
- Add background polling or callbacks beyond the current explicit refresh/reconciliation model unless required by the proposal tasks.
- Store real PHI or production artifacts in fixtures.

## Proposed Flow

1. Operator starts the lab services and confirms the dcm4chee profile diagnostics are valid.
2. Healthcare Lab creates a demo DICOM patient and order from a preset or fixture.
3. Healthcare Lab syncs the patient precondition to dcm4chee, creates the MWL item, and records canonical identifiers.
4. Healthcare Lab verifies MWL queryability against the configured `WORKLIST` MWL REST target.
5. For the live path, AP queries MWL and C-STOREs the DICOM result back to dcm4chee using the agreed AE titles and identifiers.
6. For the simulated path, Healthcare Lab records an AP-returned fixture containing either a PDF artifact link/upload record or DICOM result metadata/object record tied to the canonical order identifiers.
7. Healthcare Lab refreshes/reconciles dcm4chee results or the simulated AP-return fixture.
8. Operator confirms the frontend shows AP C-STORE/result status, reconciliation status, PDF or DICOM access link, and DICOM identifiers in the patient/order result browser.
9. Verification output records the exact identifiers and status evidence needed to repeat or troubleshoot the run.

## Data / Fixture Direction

The fixture should use virtual lab data only. It should provide predictable values for:

- patient name, Patient ID, issuer, birth date, sex
- local order ID, accession number, requested procedure ID, scheduled procedure step ID
- scheduled station AE title, AP calling AE title, archive called AE title
- Study Instance UID, Series Instance UID, SOP Instance UID for DICOM-style simulated results
- PDF artifact name, URL/path, media type, and AP-return role for PDF-style simulated results

The simulated return should exercise the same UI contract that real reconciled dcm4chee results use whenever practical. If the simulated path is stored separately, the UI must still label it clearly as an AP-returned/simulated result and expose the same proof identifiers.

## API / UI Direction

Backend options:

- Add a dedicated E2E verification endpoint or scripted command that orchestrates the local fixture steps and returns an evidence object.
- Add a fixture endpoint or helper for simulated AP-return records tied to an existing DICOM order.
- Reuse existing MWL sync, MWL verify, result refresh, and patient/order payload endpoints instead of duplicating core logic.

Frontend direction:

- The DICOM patient/order workspace should show the simulated or live AP-returned result without requiring raw JSON inspection.
- PDF artifacts should expose an operator-visible open/copy link when available.
- DICOM-style results should show Study, Series, and Instance identifiers in the existing PACS-style browser.
- The selected DICOM order detail should make MWL Sync, MWL Queryable, AP C-STORE/AP Returned Result, and Reconciliation statuses visible.

## Documentation Direction

The SOP should cover:

- service startup commands and health/smoke checks
- required ports: Healthcare Lab UI, dcm4chee UI, dcm4chee DIMSE, dcm4chee HL7 Patient sync, and DICOMweb/MWL REST
- AE titles: archive called AE, Healthcare Lab calling AE, MWL AE, AP station/calling AE
- endpoint distinction between `WORKLIST` MWL REST and `DCM4CHEE` archive QIDO/WADO/STOW
- expected identifiers and where to find them in Healthcare Lab, dcm4chee, and AP logs/tools
- live AP steps for MWL query and C-STORE
- simulated AP-return steps for PDF/DICOM UI verification
- troubleshooting for missing patient, empty MWL, wrong AE, C-STORE rejection, missing identifiers, no-result refresh, ambiguous/wrong-patient reconciliation, and inaccessible PDF/viewer links

## Risks / Trade-offs

- [Risk] Live AP behavior may not be available in automated tests. -> Mitigation: separate automated fixture coverage from manual production-like AP steps in the SOP.
- [Risk] Simulated AP-return records may diverge from real dcm4chee QIDO metadata. -> Mitigation: keep fixtures close to normalized dcm4chee result records and require live AP acceptance before closing the production-like path.
- [Risk] PDF artifacts and DICOM objects have different storage/viewer behavior. -> Mitigation: test both as separate fixture modes or explicitly document which mode is required for acceptance.
- [Risk] Identifier drift can make reconciliation appear flaky. -> Mitigation: capture and display the canonical identifiers at each step and fail with actionable diagnostics instead of guessing.

## Open Questions

- Should simulated PDF artifacts be stored as local fixture files, uploaded records, or URL-only artifact references?
- Should the E2E evidence output be persisted in the database, generated as a Markdown/JSON report, or both?
- Is the first implementation expected to C-STORE a real DICOM object from a test tool when AP is unavailable, or should that stay manual/live-AP-only?
