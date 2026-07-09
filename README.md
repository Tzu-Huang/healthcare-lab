# Healthcare Lab

Local healthcare interoperability lab dashboard and control plane for monitoring
OIE, Medplum, OpenEMR/GDT, and dcm4chee services.

This project is split out from the former combined `intern/repo` workspace. It
owns the Server Health Dashboard, local Docker Compose runtime, service health
checks, and service operation controls.

See [PROJECT_BOUNDARY.md](PROJECT_BOUNDARY.md) for the split rules.

## Current Progress

The lab now has three working local workflow tracks:

- **HL7 v2 / OIE:** local Patient and Order workflows can create HL7 ADT and
  ORM payloads, send selected ORM messages to the configured OIE MLLP endpoint,
  and record ACK or transport results.
- **FHIR R4 / Medplum:** Patient creation is local-first with Medplum sync,
  retry, and idempotent identifier matching. FHIR Orders create a local order
  anchor, sync a `ServiceRequest`, then generate and sync a dependent ECG
  worklist `Task`.
- **GDT 2.1 / OpenEMR-style bridge:** Patient/order context can be exported as
  GDT `6302`, result files can be imported from the bridge folders, and parsed
  `6310` result context is retained locally.

Healthcare Lab treats Medplum as the canonical source of truth for synced FHIR
clinical resources. Local SQLite storage is a workflow ledger for unsynced
intent, sync status, deterministic identifiers, retry/idempotency metadata,
request/response audit, OperationOutcome details, and Medplum references.

## Test UI

![ECG AP Simulator SOP workflow](docs/images/ap-simulator-sop.png)

The browser UI opens with square test-category options:

- **HL7 v2.5** for the OIE/Mirth MLLP workflow.
- **HL7 FHIR** for Medplum FHIR API return testing.
- **GDT** for the OpenEMR-style ECG order / bridge proof of concept.

The HL7 v2.5 category presents the AP workflow: listen for hospital HL7, review
the queue, upload ECG JSON and/or PDF, return the ECG result, and inspect the
selected record.

## Architecture

```text
Mirth Connect Hospital Simulator
        |
        | ADT^A04 / ADT^A08 / ORM^O01
        | MLLP over TCP :6671
        v
ECG AP Integration Simulator
        |
        +-- SQLite demo queue
        +-- ECG JSON upload and/or PDF upload
        +-- MRN == HL7 PID-3 matching
        |
        | ORU^W01 waveform OBX or ORU^R01 aECG XML / PDF OBX attachment
        | MLLP over TCP :6661
        v
Mirth Connect Hospital Listener
        |
        v
ACK: AA / AE / AR
```

The browser UI also retains a collapsed Advanced Tools section for local
loopback MLLP tests, raw message inspection, ACK failure simulation, and the
optional mock Patient Pull extension.

## Paired Open Source

The recommended hospital-side simulator is
[OpenIntegrationEngine](https://github.com/OpenIntegrationEngine/engine?utm_source=chatgpt.com).

| Item | Value |
| --- | --- |
| Role | Simulates hospital HL7 Push and result-receive endpoints |
| Version | `4.5.2` |
| License | MPL-2.0 |
| Container image | `nextgenhealthcare/connect:4.5.2` |

`4.5.2 IOE` is used because IOE is the later update from Mirth Connect and is continuing updating. This repository does not vendor or redistribute its code or binaries.

## Features

- Healthcare Interoperability Lab Console first screen for managed service
  health visibility, editable server registry, server detail, Run Check, and a
  Servers / Settings Port Matrix.
- Patient page with HL7 v2.3.1, FHIR R4, GDT 2.1, and DICOM preview modes.
- FHIR Patient creation through a local-first Medplum sync flow, including
  common demographics, contact/address fields, sync status display, and retry.
- Local FHIR workflow ledger for `Patient`, `ServiceRequest`, `Task`,
  `DiagnosticReport`, `Observation`, `DocumentReference`, `Binary`, and
  `Provenance` mapping metadata.
- Medplum page for supported FHIR resource inventory, Patient-centered
  filtering, live Medplum JSON preview, local fallback preview, copy action,
  and non-destructive retry for pending or failed local workflow records.
- FHIR Order mode that builds and syncs `ServiceRequest` resources, then
  creates ECG worklist `Task` resources linked to the synced patient and order.
- Raw TCP reachability and MLLP ACK testing.
- AP-side MLLP listener with start, stop, status, and configurable demo ACK.
- Inbound support for `ADT^A04`, `ADT^A08`, and `ORM^O01`.
- SQLite-backed demo queue for multiple records.
- ECG JSON upload, validation, preview, and MRN matching.
- PDF upload, validation, metadata preview, and HL7 result attachment return.
- Selectable HL7 v2.5.1 `ORU^W01` or `ORU^R01` result generation.
- ECG JSON waveform return as `ORU^W01` MA or NA waveform OBX segments.
- ECG JSON aECG XML return as `ORU^R01` inline `OBX|ED`.
- Base64-encoded PDF inline `OBX|ED` generation, with `OBX|RP` when a public
  URL is supplied.
- URL-based artifact return for hospital-facing HL7 demos, including multiple
  public URLs carried through `OBX`.
- Outbound ORU send, ACK inspection, error recording, and retry.
- Mock FHIR-style Patient lookup extension.
- Medplum FHIR API submission for selected-order ECG/PDF return testing with
  `Binary + Observation + DocumentReference + DiagnosticReport` packaging.
- GDT ECG order creation, GDT 2.1 `6302` export, `6310` result return, and
  PDF/DICOM artifact import through a shared-folder bridge contract.

## Healthcare Lab Console

The app opens on a server-health dashboard for the local interoperability lab.
The managed service registry is stored in the local SQLite demo database and is
seeded with:

| Service | Type |
| --- | --- |
| OIE | HL7 Engine |
| Medplum | FHIR Server |
| OpenEMR | EMR |
| GDT Bridge | GDT Bridge |
| dcm4chee | DICOM Archive |
| HL7Tester | Test Tool |
| GDT Hospital | Test Tool |

Health status values are:

- `Healthy`: configured checks are passing.
- `Degraded`: some health information is still unavailable or partially
  available.
- `Down`: a required reachable endpoint failed.
- `Unknown`: no check has run or no Phase 1 check is configured.

Phase 1 health checks include real HTTP or TCP reachability when a server record
has a base URL or host/port. Protocol checks use the same health response model
but remain shallow smoke checks; deep HL7, FHIR, GDT, and DICOM validation is
reserved for later work. Server detail pages show operation buttons such as
Start, Stop, and Restart as disabled controls because real command execution is
not implemented in this phase.

The local dcm4chee profile is available through:

```text
GET /api/dcm4chee/profile
GET /api/dcm4chee/profile/diagnostics
```

The default profile is named `local-dcm4chee` and matches the Docker lab
defaults:

| Field | Value |
| --- | --- |
| Display name | `dcm4chee Local Archive` |
| Environment | `local-docker` |
| Web UI URL | `http://127.0.0.1:8082/dcm4chee-arc/ui2` |
| DIMSE host / port | `127.0.0.1:11112` |
| Called AE title | `DCM4CHEE` |
| Healthcare Lab calling AE title | `HEALTHCARE_LAB` |
| MWL AE title | `WORKLIST` |
| Default Scheduled Station AE Title | `ECG_AP` |
| DICOMweb / MWL REST base URL | `http://127.0.0.1:8082/dcm4chee-arc/aets/WORKLIST/rs` |
| Study Instance UID root | `1.2.826.0.1.3680043.10.543` |

The profile also includes QIDO-RS, WADO-RS, STOW-RS, viewer-link, auth, and TLS
fields for future MWL, verification, C-STORE reconciliation, and viewer-link
workflows. The local default uses `DCM4CHEE_AUTH_MODE=none` and
`DCM4CHEE_TLS_ENABLED=false`; that is only for the local lab and is not a
production security profile.

DICOM MWL order creation and verification use the dcm4chee MWL REST path:

```text
POST /dcm4chee-arc/aets/WORKLIST/rs/mwlitems
GET /dcm4chee-arc/aets/WORKLIST/rs/mwlitems?...query...
Content-Type: application/dicom+json
```

The archive QIDO/WADO/STOW application is exposed by the `DCM4CHEE` web app,
but modality worklist REST is exposed by the `WORKLIST` web app in the local
dcm4chee defaults. Healthcare Lab records the configured MWL AE and request URL
in the PACS/MWL ledger so operators can distinguish wrong-AE failures from empty
worklist results.

Healthcare Lab stores the local order first, then maintains a local PACS/MWL
ledger that maps the Healthcare Lab order to dcm4chee identifiers. The canonical
mapping stores Patient ID, Issuer of Patient ID, Accession Number, Requested
Procedure ID, Scheduled Procedure Step ID, Study Instance UID, Worklist Label,
profile/server namespace, sync status, retry count, and latest error details.
Every create/read-back operation also keeps request/response audit history for
debugging.

After a successful MWL create, Healthcare Lab attempts a best-effort dcm4chee
read-back query and stores any identifiers dcm4chee returned, generated, or
normalized. Re-running sync for an order with a successful canonical mapping
does not POST a duplicate MWL item. Failed or ambiguous retries reuse the stable
local identifiers from the mapping so later dcm4chee studies can be matched back
to the original local order by Study Instance UID, then Accession Number, then
Requested Procedure ID plus Scheduled Procedure Step ID. If dcm4chee rejects the
request because the patient does not exist, the local order remains available
and the dcm4chee MWL sync state is recorded as `Patient missing`. Full AP
C-STORE result ingestion/display and viewer-link consumption remain future work.

The DICOM order workspace can verify MWL queryability for a local order. The
verification action queries dcm4chee MWL using the ledger identifiers and records
the query criteria, endpoint, response status, matched identifiers, and
diagnostics. Successful verification proves which MWL item was found; failed
verification distinguishes connectivity/profile problems, missing patient
preconditions, empty worklist responses, identifier mismatches, and ambiguous
matches.

The first Docker Desktop runtime scaffold for the Lab Console lives in
[deploy/](deploy/README.md). It includes `docker-compose.yml` and the
`deploy/lab.ps1` wrapper for local `status`, `start`, `stop`, `restart`,
`smoke`, and `logs` operations.

## Patient Page

Use **Patient** to create local virtual patient records for the supported
workflow modes:

- **HL7 v2.3.1:** previews an `ADT^A04` payload for the local OIE workflow.
- **FHIR R4:** previews a FHIR `Patient`, stores the local Patient first, then
  creates or updates the paired FHIR workflow ledger record and attempts Medplum
  sync.
- **GDT 2.1:** stores patient context used by the GDT order/export workflow.
- **DICOM:** previews patient module attributes for future DICOM-oriented
  workflow work.

FHIR Patient rows show sync status, Medplum `Patient/<id>` reference, last sync
metadata, and sync errors when available. `Pending sync` and `Sync failed` rows
remain visible locally and can be retried without creating duplicate Medplum
Patients because sync uses deterministic identifiers.

## Order Page

The app uses a left sidebar for primary navigation. The Dashboard remains
focused on managed server health and operations, while **Patient**, **Order**,
**OIE**, **Medplum**, and **GDT** provide the local interoperability workflows.

Use **Order** to create a local 12-lead ECG order from an existing local Patient
record.

For **HL7 v2.3.1** orders:

- HL7 v2.3.1 is enabled for the MVP.
- The generated `ORM^O01` preview includes `MSH`, `PID`, `PV1`, `ORC`, and
  `OBR`.
- Orders are stored in the local SQLite demo database with status, raw ORM
  payload, and later ACK/send details.

Use **OIE** to inspect local Patient ADT inventory and local Order ORM
inventory. The Order inventory can send one selected ORM message to the
configured OIE MLLP endpoint, defaulting to `localhost:6663` for direct local
Flask runs and `oie:6663` in the Docker Compose lab, and stores the returned ACK
code (`AA`, `AE`, or `AR`) or transport error.

OIE-to-AP routing is intentionally outside this app scope. Configure downstream
channels inside OIE when an integration demo needs received ORM messages routed
to another application endpoint.

For **FHIR R4** orders:

- The selected Patient must already be a synced FHIR Patient with a Medplum
  `Patient/<id>` reference.
- The Order page exposes the scoped ServiceRequest form fields needed for the
  ECG order workflow and renders a FHIR R4 `ServiceRequest` preview.
- Creating the order stores a local order anchor, syncs the `ServiceRequest` to
  Medplum, then generates an ECG worklist `Task` with
  `Task.for = Patient/<id>` and `Task.focus = ServiceRequest/<id>`.
- Local Orders shows independent sync status and Medplum references or errors
  for both the `ServiceRequest` and generated `Task`.

GDT order creation is handled through the GDT workflow and bridge contract.
HL7 v2.5.1 and DICOM order modes remain future work.

## Medplum Console

Select **Medplum** from the sidebar to inspect supported FHIR workflow
resources. The page reads synced resource previews from live Medplum APIs when
possible and joins local ledger metadata such as sync status, local identifiers,
Medplum references, and last error.

The Medplum page currently supports:

- Inventory rows for `Patient`, `ServiceRequest`, `Task`, `DiagnosticReport`,
  `Observation`, and `DocumentReference`.
- Patient-centered filtering through direct FHIR references such as `subject`,
  `patient`, and `for`.
- A selected Patient workspace with related ServiceRequest, Task,
  DiagnosticReport, Observation, and DocumentReference context when available.
- A bottom JSON console that labels whether the preview came from Medplum live
  data, local submitted JSON, or local fallback after a live fetch failure.
- Non-destructive retry for local `Pending sync` and `Sync failed` records.

The page does not expose destructive Medplum actions such as delete or arbitrary
resource update.

## Requirements

- Python 3.10 or newer
- Flask dependencies from `requirements.txt`
- Mirth Connect `4.5.2` or another compatible MLLP endpoint
- Virtual test data only

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

Then edit `.env` and set the Medplum credentials you need for the FHIR demo.

Open:

```text
http://127.0.0.1:5000
```

The Flask server binds to loopback only. Set `LAB_APP_PORT` before startup to
use another local UI port, for example:

```powershell
$env:LAB_APP_PORT = "5100"
python app.py
```

Then open `http://127.0.0.1:5100`. Lab registry and operation history data is
created locally in `instance/healthcare-lab.db` and is excluded from Git. Set
`HEALTHCARE_LAB_DB` to override the path; `HL7_SIMULATOR_DB` is still accepted
as a migration fallback.

When running inside Docker, the Compose runtime sets `LAB_APP_HOST=0.0.0.0` so
the host port mapping can reach the Flask server. Local direct startup keeps the
safer loopback default unless you explicitly override `LAB_APP_HOST`.

## Quick Demo

Select **HL7 v2.5** from the landing view, then follow the AP workflow in order:

1. **Listen for Hospital HL7:** start `Hospital -> AP Listener :6671`.
2. **Review Incoming Queue:** use Mirth Connect to push `ADT^A04`, then confirm
   the matching queue row is `WAITING_FOR_ECG`.
3. **Upload ECG JSON or PDF:** upload
   [examples/ecg-sample.json](examples/ecg-sample.json), a PDF report, or both.
   The row becomes `READY_TO_SEND` after inbound HL7 context and at least one
   result artifact are present.
4. **Return ECG Result to Hospital:** configure
   `AP -> Hospital Result Endpoint :6661`, choose `ORU^W01` or `ORU^R01`,
   generate the HL7 result, and send it.
5. **Inspect Selected Record:** confirm the row becomes `ACCEPTED` and review
   the recorded `AA` ACK and attempt history.

All generated HL7 v2 result messages use `MSH-12 = 2.5.1`. When ECG JSON is
present, `ORU^W01` emits waveform observations using the selected MA
timepoint-major or NA channel-major layout. `ORU^R01` emits a standard aECG XML
payload in an inline `OBX|ED`. When PDF is present, generated result messages
include an inline `OBX|ED` attachment with Base64 `application/pdf` content.
PDF-only records return a minimal result with patient context and the PDF
attachment.

When a hospital-facing workflow uses public URLs for artifact delivery, the
result uses `OBX|RP` instead of embedding that same payload inline.

The **Review Incoming Queue** card also provides demo cleanup controls:

- **Remove All** clears all queued demo records after confirmation, without
  stopping `Hospital -> AP Listener :6671`.
- **Delete** appears on an individual row only after the result has been
  accepted with an `AA` ACK.

## Medplum FHIR Demo

Select **HL7 FHIR** from the landing view to test against a Medplum FHIR server.
Enter the Medplum FHIR base URL, such as:

```text
http://localhost:8103/fhir/R4
```

The connection card now shows server-side Medplum auth status. Configure the
Flask server with `MEDPLUM_CLIENT_ID` and `MEDPLUM_CLIENT_SECRET` so it can
obtain access tokens using OAuth client credentials and refresh them
automatically when needed. The local dev server now loads these values from
`.env` in the repo root before Flask starts.

Optional auth-related environment variables:

- `MEDPLUM_SCOPE`
- `MEDPLUM_TOKEN_URL`
- `MEDPLUM_AUTH_GRACE_SECONDS`

When submitting ECG JSON as an external file link, set **File Base URL** to a
server-reachable HTTPS origin such as an ngrok tunnel or your reverse-proxy
domain. Do not leave this as `localhost` unless the FHIR server is running on
the same host and can resolve that loopback address.

For a stable deployment, do not expose the Flask dev server directly on
`:8103`. Put Nginx or another reverse proxy in front of it so external clients
use standard `80/443`, then set `ECG_FILE_BASE_URL` to that public HTTPS
origin. The app now trusts forwarded host and scheme headers from one proxy
layer, so generated URLs can stay on `https://your-domain/...` instead of
falling back to the internal Flask host/port.

Example:

```text
External users / FHIR server -> https://ecg.example.com/storage/...
Nginx :443 -> http://127.0.0.1:5000
Flask app -> stores files locally and publishes URLs with ECG_FILE_BASE_URL
```

Use **GET ServiceRequest** to fetch recent order data with included patient and
order context:

```text
ServiceRequest?_count=20&_sort=-_lastUpdated&_include=ServiceRequest:subject&_include=ServiceRequest:encounter&_include=ServiceRequest:requester&_include=ServiceRequest:performer
```

The UI displays the raw `ServiceRequest` bundle directly so the test user can
inspect the returned FHIR content as-is. Then choose one returned
`ServiceRequest` from the summary list and upload ECG JSON, a PDF report, or
both:

- The fetched `ServiceRequest` bundle is still kept in raw form for debugging,
  but the UI shows a simplified selectable list with patient and order details.
- **Remove** in this view only removes an item from the current UI list. It does
  not delete any FHIR resources on the server.
- ECG JSON uploads are converted into structured ECG `Observation` resources and
  are also preserved byte-for-byte as a FHIR `Binary` resource with
  `contentType = application/json`.
- Raw ECG JSON and optional PDF uploads are indexed through a
  patient/order-linked `DocumentReference` so they remain easy to inspect from
  the FHIR side.
- The final selected-order clinical result is submitted as a
  `DiagnosticReport` linked to both the selected `Patient` and the selected
  `ServiceRequest`.

The UI displays the created `DiagnosticReport`, related structured resources,
and raw Medplum response details for the submission.

For newer Patient-centered FHIR work, use the **Patient**, **Order**, and
**Medplum** sidebar pages:

1. Create a Patient in FHIR mode and confirm the row reaches `Synced`.
2. Create an Order in FHIR mode from that synced Patient.
3. Open **Medplum** to inspect the Patient, ServiceRequest, generated Task, and
   raw live FHIR JSON.

## Mirth Connect Channel Setup

Create these two channels in Mirth Connect Administrator before running the
end-to-end demo.

### Channel 1: Push Hospital HL7 to the AP

1. Open **Channels**, then select **New Channel**.
2. Set the channel name to `HOSPITAL_PUSH_TO_AP`.
3. Set the **Source** connector type to `Channel Reader`.
4. Open **Destinations**, then set the connector type to `TCP Sender`.
5. Set **Remote Address** to the Windows AP simulator IP, such as
   `192.168.30.52`.
6. Set **Remote Port** to `6671`.
7. Select `MLLP` transmission mode and use a `5000` ms timeout.
8. Save and deploy the channel.

The AP UI must already show:

```text
Hospital -> AP Listener :6671
Listening 0.0.0.0:6671
```

To send a hospital-side test message:

1. In Mirth Connect Administrator, open **Channels**.
2. Select `HOSPITAL_PUSH_TO_AP`.
3. Select **Send Message**.
4. Paste the following virtual patient message and send it:

```hl7
MSH|^~\&|HOSPITAL||ECG_AP||20260602150000||ADT^A04|ADT002|P|2.5.1
PID|1||QT_Athlete_003_Borderline2||Brooks^Caleb||20100228|M
```

The AP queue should show `WAITING_FOR_ECG`. Upload
[examples/ecg-sample.json](examples/ecg-sample.json) to change the record to
`READY_TO_SEND`.

### Channel 2: Receive AP ECG Results

1. Create another channel named `HOSPITAL_RECEIVE_ORU`.
2. Set the **Source** connector type to `TCP Listener`.
3. Set **Listener Port** to `6661`.
4. Select server mode, `MLLP` transmission mode, and `UTF-8` encoding.
5. Keep the default response behavior so Mirth returns an HL7 ACK on the same
   connection.
6. Save and deploy the channel.

In the AP UI, configure:

```text
AP -> Hospital Result Endpoint :6661
Hospital Host: <Ubuntu-IP>
Hospital Port: 6661
```

Choose a result profile, select **Generate HL7 Result**, then select **Send ORU
to Hospital** and confirm the selected record reports an `AA` ACK. For the full
Ubuntu Docker setup and connectivity checks, see
[Mirth Connect setup](docs/mirth-connect-setup.md).

## Advanced Tools

Expand **Advanced Tools** only when troubleshooting or demonstrating optional
behavior. The local loopback sender uses:

```text
AP Simulator Raw Sender -> 127.0.0.1:6671 -> AP Simulator Listener
```

This sends the simulator's test `ADT^A04` message back to itself. It does not
represent the hospital production flow. Advanced Tools also contains the
`AA` / `AE` / `AR` ACK simulation, raw ORU editor, session log, and mock
Patient Pull lookup.

## Documentation

- [Architecture and boundaries](docs/architecture.md)
- [Mirth Connect setup](docs/mirth-connect-setup.md)
- [End-to-end demo walkthrough](docs/demo-walkthrough.md)
- [ECG hospital integration research](docs/ecg-hl7-integration-research.md)
- [GDT bridge MVP](docs/gdt-bridge-mvp.md)
- [HL7 ORU PDF validation tool](docs/hl7-oru-pdf-validation.md)
- [Reverse proxy notes](docs/reverse-proxy-nginx.md)

## Tests

```powershell
python -m unittest discover -s tests -v
python -m py_compile app.py backend\lab_store.py backend\dashboard_services.py backend\lab_operations.py backend\gdt_adapter.py tests\test_app.py tests\test_lab_store.py tests\test_b64_pdf.py tests\test_gdt_adapter.py
node --check frontend\static\app.js
```

## Demo Limitations

- SQLite is demo persistence, not a production message queue.
- MRN matching uses ECG `patient.mrn == HL7 PID-3` without assigning authority
  or order-ID matching.
- Current patient-name reconciliation is incomplete. Returned names may not yet
  match the hospital-sent demographics in every flow.
- ECG observation identifiers are placeholders that must be agreed with each
  hospital.
- The mock Patient endpoint is not a complete FHIR server.
- HL7 v2 waveform and aECG returns are lab interoperability profiles.
  Production ECG waveform exchange should prefer DICOM ECG Waveform Storage
  when PACS is available.
- TLS, authentication, authorization, audit logging, and production patient
  data handling are out of scope.
