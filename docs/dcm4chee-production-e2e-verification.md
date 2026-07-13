# dcm4chee Production-Like E2E Verification

This SOP verifies the Healthcare Lab DICOM path:

```text
Healthcare Lab patient/order
-> dcm4chee Patient precondition
-> dcm4chee MWL item
-> AP MWL query
-> AP C-STORE result to dcm4chee
-> Healthcare Lab result refresh/reconciliation
-> Healthcare Lab UI result display
```

Use only virtual lab data. Do not use production patient data or production ECG
artifacts.

## Required Services

Start from the repo root:

```powershell
.\deploy\lab.ps1 restart all
.\deploy\lab.ps1 smoke dcm4chee
.\deploy\lab.ps1 smoke lab-app
```

Open Healthcare Lab at:

```text
http://127.0.0.1:5000
```

Confirm the dcm4chee profile diagnostics:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/dcm4chee/profile/diagnostics
```

## Required Ports And AE Titles

| Value | Default |
| --- | --- |
| Healthcare Lab UI | `http://127.0.0.1:5000` |
| dcm4chee UI | `http://127.0.0.1:8082/dcm4chee-arc/ui2` |
| dcm4chee DIMSE MWL/C-STORE | `127.0.0.1:11112` |
| dcm4chee HL7 Patient sync | `127.0.0.1:2575` |
| dcm4chee MWL REST | `http://127.0.0.1:8082/dcm4chee-arc/aets/WORKLIST/rs/mwlitems` |
| dcm4chee archive QIDO/WADO/STOW | `http://127.0.0.1:8082/dcm4chee-arc/aets/DCM4CHEE/rs` |
| Archive called AE title | `DCM4CHEE` |
| Healthcare Lab calling AE title | `HEALTHCARE_LAB` |
| MWL AE title | `WORKLIST` |
| AP scheduled station / calling AE title | `ECG_AP` |

The local dcm4chee runtime exposes MWL REST through `WORKLIST`, while archive
QIDO/WADO/STOW uses `DCM4CHEE`. A common failure is querying the archive AE for
MWL items.

## Create The Demo Fixture

Healthcare Lab exposes a deterministic fixture endpoint:

```powershell
$fixture = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:5000/api/dcm4chee/e2e-fixture `
  -ContentType application/json `
  -Body '{}'
```

Record these values from `$fixture.evidence.identifiers`:

- Patient ID
- Issuer of Patient ID
- Accession Number
- Requested Procedure ID
- Scheduled Procedure Step ID
- Study Instance UID

The fixture creates local virtual patient/order data and a local PACS/MWL
mapping. For a live AP run, create a DICOM patient and order from the UI or API
so Healthcare Lab performs the real patient sync and MWL create operations.

## Live AP Verification Path

1. In Healthcare Lab, create or select a DICOM patient and DICOM order.
2. Confirm Patient precondition status is `Synced`.
3. Confirm MWL Sync status is `Created`.
4. Click **Verify MWL Query** and confirm MWL Queryable status is `verified`.
5. Give the AP operator:
   - host `127.0.0.1` or the reachable lab IP
   - port `11112`
   - called AE title `DCM4CHEE`
   - calling/station AE title `ECG_AP`
   - Patient ID, issuer, accession number, requested procedure ID, SPS ID, and
     Study Instance UID from Healthcare Lab evidence
6. AP queries MWL and selects the matching order.
7. AP C-STOREs the ECG DICOM result to dcm4chee.
8. In Healthcare Lab, click **Refresh PACS Results** for the patient/order.
9. Confirm the UI shows:
   - AP C-STORE Result is not `No result`
   - Reconciliation is `matched`
   - Study/Series/Instance rows are visible
   - identifiers match the evidence values
   - viewer or retrieve links are available when dcm4chee returns enough UIDs

Fetch the evidence after the run:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/orders/<order-id>/dcm4chee-e2e-evidence
```

## Simulated AP Return Path

Use this path when the UI and reconciliation display need verification without a
live AP.

Create a simulated PDF return:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:5000/api/orders/<order-id>/dcm4chee-simulated-ap-return `
  -ContentType application/json `
  -Body '{"type":"pdf","artifactUrl":"http://localhost/reports/dcm4chee-simulated-ecg-report.pdf"}'
```

Create a simulated DICOM metadata return:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:5000/api/orders/<order-id>/dcm4chee-simulated-ap-return `
  -ContentType application/json `
  -Body '{"type":"dicom"}'
```

The DICOM order workspace also exposes **Simulate AP PDF** and **Simulate AP
DICOM** actions. Simulated rows are labeled with source `simulated_ap_return` so
operators can distinguish fixture evidence from live dcm4chee evidence.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Patient precondition fails | dcm4chee HL7 port `2575`, assigning authority `local-dcm4chee`, and Patient ID are correct. |
| MWL create fails with missing patient | Create/sync the DICOM patient before MWL order creation. |
| MWL verification returns empty | Confirm the endpoint uses `/aets/WORKLIST/rs/mwlitems`, not `/aets/DCM4CHEE/rs`. |
| AP cannot find the order | Confirm AP station/calling AE `ECG_AP`, Patient ID/issuer, accession number, requested procedure ID, and SPS ID. |
| C-STORE accepted but Healthcare Lab shows no result | Confirm the result preserves Study Instance UID or accession number and refresh the patient DICOM results. |
| Reconciliation is wrong-patient or ambiguous | Compare returned Patient ID/issuer and order identifiers with Healthcare Lab evidence. |
| PDF artifact cannot open | Confirm the artifact URL/path is reachable from the browser running Healthcare Lab. |
