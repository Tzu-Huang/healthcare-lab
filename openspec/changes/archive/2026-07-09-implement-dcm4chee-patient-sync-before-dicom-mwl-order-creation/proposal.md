## Why

Healthcare Lab can create local DICOM Patient records and dcm4chee MWL orders, but dcm4chee rejects MWL creation when the referenced Patient does not already exist in the archive. Operators then see `patient_missing` and follow-up MWL verification failures even though the local Patient and order remain valid.

ZAC-44 adds a dcm4chee Patient sync lifecycle before MWL creation. The local dcm4chee runtime is `dcm4che/dcm4chee-arc-psql:5.35.0` from `dcm4chee-arc-light`; its MWL REST endpoint checks Patient existence before accepting `mwlitems`, while its HL7 receiver supports ADT patient update messages. Healthcare Lab should therefore sync local DICOM Patients to dcm4chee through HL7 ADT and treat Patient sync as a visible MWL precondition.

## What Changes

- Add dcm4chee HL7 connection settings to the local connection profile, including host, port, sending application/facility, receiving application/facility, and default Patient ID issuer behavior.
- Expose dcm4chee HL7 port `2575` in the Docker lab and use `dcm4chee:2575` from the lab-app container by default.
- Add a dcm4chee Patient sync/upsert path that sends HL7 ADT for local DICOM Patient creation.
- Persist dcm4chee Patient sync attempts separately from MWL attempts, with request payload, endpoint, ACK/error details, sync status, and timestamps.
- Surface Patient sync status on Patient and DICOM order views so operators can distinguish Patient precondition failures from MWL endpoint/query failures.
- Before creating a dcm4chee MWL item, verify that the referenced Patient has synced successfully or attempt a Patient sync preflight if needed.
- Preserve local DICOM orders when Patient sync fails, recording an actionable `patient_missing` or Patient sync precondition failure instead of hiding the root cause behind empty MWL query diagnostics.
- Keep existing MWL REST creation/read-back/verify behavior, but guard it with the Patient sync precondition.

## Capabilities

### New Capabilities

- `healthcare-lab-dcm4chee-patient-sync`: Sync local DICOM Patient records into dcm4chee using the local archive HL7 ADT receiver and record the sync lifecycle.

### Modified Capabilities

- `healthcare-lab-dcm4chee-connection-profile`: Include dcm4chee HL7 receiver settings needed for Patient sync.
- `healthcare-lab-dcm4chee-mwl-order-model`: Require dcm4chee Patient existence before MWL creation and keep Patient precondition diagnostics visible during MWL sync and verification.

## Impact

- Affected code: likely `app.py`, `backend/lab_store.py`, `frontend/static/app.js`, `frontend/templates/index.html`, `deploy/docker-compose.yml`, `.env.example`, `README.md`, and tests under `tests/`.
- Affected systems: local SQLite Patient sync ledger, dcm4chee HL7 receiver, dcm4chee MWL REST endpoint, Patient page, DICOM order workspace, Docker lab networking.
- Non-goal for this change: replacing MWL REST order creation with HL7 ORM. HL7 ORM-to-MWL can be evaluated after Patient ADT sync is stable.
- Non-goal for this change: using STOW-RS to create Patient master data. STOW-RS remains appropriate for real DICOM object upload, not for Patient master upsert.
