# Healthcare Lab User Handbook (English)

> Document status: v1.0.0 Release Candidate draft<br>
> Documentation baseline: `fd0e38f`<br>
> Last updated: 2026-07-22<br>
> This edition has not passed final publication, clean-install, or full end-to-end verification for all four protocols. Content marked “Pending RC verification” is not a final operational guarantee.

## Part I: Understand and Start Healthcare Lab

<a id="chapter-1"></a>
## Chapter 1 — About This Handbook

This handbook helps Healthcare Lab operators install, configure, start, stop, verify, and troubleshoot the system and complete ECG order/result workflows using HL7 v2, FHIR R4, GDT 2.1, and DICOM/dcm4chee.

It is intended for healthcare integration testers, application specialists, healthcare IT engineers, system operators, and demonstration operators. Source-code knowledge is not required.

This handbook applies to the v1.0.0 RC Docker distribution model. It excludes source builds and development setup. First-time installers should read Chapters 3–6; UI operators may begin with Chapters 7–9; protocol users may go directly to Chapters 10–13; troubleshooting begins in Chapter 14.

<a id="chapter-2"></a>
## Chapter 2 — Healthcare Lab Overview

Healthcare Lab is an operations platform for a trusted local or internal healthcare integration lab. Its typical workflow is:

```text
Create Patient
  -> Create ECG Order
  -> Send, sync, or export Order
  -> AP (QHAP) processes Order
  -> Return, import, or reconcile Result
  -> Inspect status, result, and operation history
```

The Healthcare Lab UI and backend manage the local workflow. OIE routes HL7 v2; Medplum stores and queries FHIR R4 resources; GDT Bridge exchanges files through a shared folder; dcm4chee provides MWL, a DICOM archive, and DICOMweb; AP (QHAP) obtains orders and returns results.

The main sidebar pages are Dashboard, Patient, Order, OIE, GDT, Medplum, and dcm4chee. These names match the recorded 2026-07-22 RC browser pass; unverified actions and limitations are called out in the relevant chapters.

### System Architecture

```text
Browser -> Healthcare Lab (lab-app:5000)
              |-> OIE (HL7 v2 / MLLP)
              |-> Medplum (FHIR R4 / OAuth)
              |-> GDT Bridge shared folder
              `-> dcm4chee (HL7 ADT, MWL, QIDO/WADO)

AP (QHAP) <-> OIE / GDT shared folder / dcm4chee
```

> Pending RC verification: replace this text diagram with the final deployment diagram and verify every connection, direction, protocol, and port.

<a id="chapter-3"></a>
## Chapter 3 — Prerequisites

The v1.0.0 RC support boundary is a trusted local machine or internal lab running `linux/amd64` containers. Windows uses Docker Desktop in Linux container mode. An equivalent Linux Docker host remains pending formal release verification.

### Verified RC host environment

On 2026-07-22, the RC `lab-app` started, passed its Docker health check, and returned HTTP 200 in the environment below. This is a tested environment, not a minimum requirement.

| Item | Verified value |
| --- | --- |
| Host OS | Windows 11 64-bit |
| Host hardware | 16 logical CPUs, approximately 16 GB RAM |
| PowerShell | Windows PowerShell 5.1 |
| Docker Desktop | 4.75.0 |
| Docker Engine | 29.5.2, Linux/amd64 |
| Docker Compose | v5.1.3 |
| Docker VM resources | 16 CPUs, approximately 8 GB RAM |
| RC image | `healthcare-lab:verify-fd0e38f` |

### Pre-installation checks

Run:

```powershell
docker version
docker compose version
docker info --format 'Server={{.ServerVersion}} OSType={{.OSType}} Arch={{.Architecture}} CPUs={{.NCPU}} Memory={{.MemTotal}}'
```

Confirm that Docker Server information is present, `OSType=linux`, and the architecture is `x86_64`/`amd64`. If only Docker Client information appears, start Docker Desktop or correct the current Docker context and daemon permissions.

Also confirm that:

- The host can access GHCR and third-party image registries.
- Default host ports 5000, 6600, 6661, 8080, 8443, 8103, 3000, 8082, 11112, and 2575 are not used by another process.
- A Medplum OAuth client ID and secret are available when FHIR sync is required.
- A GDT host folder is prepared; the Docker host IP, firewall rules, and required external AP (QHAP) endpoints are known when applicable.
- Only virtual test data will be used.

> Pending RC verification: minimum CPU, memory, and storage requirements; supported browser versions; and a clean installation on an equivalent Linux host.

<a id="chapter-4"></a>
## Chapter 4 — Installing the Released Docker Image

The release model combines a fixed Healthcare Lab image, a versioned deployment bundle, and compatible OIE, Medplum, and dcm4chee images. `.env` belongs to the deployment bundle and contains deployment-specific image tags, ports, service addresses, credentials, and volume paths. It is not part of the immutable image.

### RC installation procedure

1. Download and extract the v1.0.0 deployment bundle.
2. Open PowerShell in the bundle root.
3. Create the local configuration and GDT folders:

   ```powershell
   Copy-Item .env.example .env
   New-Item -ItemType Directory -Force instance\gdt-bridge\inbox
   New-Item -ItemType Directory -Force instance\gdt-bridge\outbox
   ```

4. Validate Compose syntax and the resolved image matrix:

   ```powershell
   docker compose --env-file .env -f deploy\docker-compose.yml config --quiet
   docker compose --env-file .env -f deploy\docker-compose.yml config --images
   ```

   `config --quiet` should exit with code 0. `config --images` should show the fixed Healthcare Lab `1.0.0` image and the third-party digests listed in the release documentation.

5. Review `.env` and enter the credentials, ports, and paths required by the deployment. Before starting Compose, replace the host-facing dcm4chee connection values copied from `.env.example` with Docker-network addresses for `lab-app`:

   ```dotenv
   DCM4CHEE_DIMSE_HOST=dcm4chee
   DCM4CHEE_HL7_HOST=dcm4chee
   DCM4CHEE_DICOMWEB_BASE_URL=http://dcm4chee:8080/dcm4chee-arc/aets/WORKLIST/rs
   DCM4CHEE_QIDO_RS_URL=http://dcm4chee:8080/dcm4chee-arc/aets/DCM4CHEE/rs
   DCM4CHEE_WADO_RS_URL=http://dcm4chee:8080/dcm4chee-arc/aets/DCM4CHEE/rs
   DCM4CHEE_STOW_RS_URL=http://dcm4chee:8080/dcm4chee-arc/aets/DCM4CHEE/rs
   ```

   Keep `DCM4CHEE_WEB_UI_URL` host-facing because a browser opens it. In contrast, `127.0.0.1` in the six backend values above points back to `lab-app` when Compose injects `.env` into that container. The deployment template must be corrected and clean-install verification repeated before this workaround can be removed from the installation procedure.
6. After the formal image is published, pull the fixed version:

   ```powershell
   docker pull ghcr.io/tzu-huang/healthcare-lab:1.0.0
   ```

7. Start the services and inspect their state:

   ```powershell
   docker compose --env-file .env -f deploy\docker-compose.yml up -d
   docker compose --env-file .env -f deploy\docker-compose.yml ps
   Invoke-WebRequest http://127.0.0.1:5000/ -UseBasicParsing
   ```

   `dcm4chee-storage-init` is a one-shot initialization service. It creates the configured archive storage directory, sets the directory to `wildfly:wildfly` with mode `0775`, and must succeed before `dcm4chee` starts. `Exited (0)` in `docker compose ps -a` is its expected state; a nonzero exit code means archive storage initialization failed.

The root page should return HTTP 200 and required containers should be running/healthy. Confirm the actual image rather than relying on the container name:

```powershell
.\deploy\lab.ps1 inspect lab-app
docker compose --env-file .env -f deploy\docker-compose.yml config --images
```

The `Image` value reported by `inspect` must be the immutable Healthcare Lab tag selected for this installation. Container health does not prove that a protocol workflow is complete.

### Completed RC image verification

An isolated Compose project verified `healthcare-lab:verify-fd0e38f` during this documentation round. The container became `healthy`, the root page returned HTTP 200, Gunicorn listened on container port 5000, and a marker in `/app/instance` survived force recreation. All seven container release contract tests passed.

This validates RC image behavior. It does not validate the public pull of `ghcr.io/tzu-huang/healthcare-lab:1.0.0` or a clean full-stack installation.

> Pending RC verification: the `v1.0.0` tag, unauthenticated public pull, image digest, clean installation, and first-time initialization.

<a id="chapter-5"></a>
## Chapter 5 — Configuration

Configuration may come from `.env`, Compose, persisted server inventory in Dashboard, and external systems. When values conflict, a workflow may use persisted server inventory. For example, Medplum sync uses the saved Medplum `baseUrl`; the browser URL or public URL in `.env` must not be assumed to be the backend address.

Important address contexts:

| Context | Example | Purpose |
| --- | --- | --- |
| Browser/host | `http://127.0.0.1:5000` | Operate Healthcare Lab |
| Docker service | `http://medplum:8103/fhir/R4` | `lab-app` accesses Medplum |
| External device | `<Docker-host-IP>:6661` | AP (QHAP) sends results to OIE |

After changing `.env`, recreate the affected service, normally with `.\deploy\lab.ps1 restart <service>`. The wrapper's `restart` action runs `up -d --force-recreate`; it is not a process-only restart. After changing a managed Channel destination, queue, retry, or ACK setting, Preview, Apply, and redeploy the Channel.

Before applying configuration, run:

```powershell
docker compose --env-file .env -f deploy\docker-compose.yml config --quiet
```

This verifies that Compose can resolve the configuration. It does not validate credentials, network connectivity, or a protocol workflow.

Keep credentials only in the local `.env` or an approved secret store. Do not place them in documentation, screenshots, or version control.

<a id="chapter-6"></a>
## Chapter 6 — Starting, Stopping, and Verifying Healthcare Lab

Run these commands from the deployment bundle root:

```powershell
.\deploy\lab.ps1 inspect lab-app
.\deploy\lab.ps1 status
.\deploy\lab.ps1 start all
.\deploy\lab.ps1 smoke all
.\deploy\lab.ps1 logs oie -Lines 200
.\deploy\lab.ps1 restart lab-app
.\deploy\lab.ps1 stop all
```

| Action | Actual purpose |
| --- | --- |
| `inspect` | Emits JSON containing container, image, state, port, and Compose metadata |
| `status` | Runs `docker compose ps` to list running services |
| `start` | Runs `docker compose up -d`, optionally for one service |
| `smoke` | Currently lists Compose `ps` state; it does not run HTTP or protocol tests |
| `logs` | Displays the last N log lines for the selected service |
| `restart` | Force recreates a service; a selected service uses `--no-deps` |
| `stop` | Stops a selected service or the full stack without removing named volumes |

`gdt-bridge`, `hl7tester`, and `gdt-hospital` are logical wrapper names mapped to the `lab-app` container. `medplum` maps to both the Medplum API and Web UI.

Default interfaces are Healthcare Lab at `http://127.0.0.1:5000`, OIE HTTP at `http://127.0.0.1:8080`, Medplum UI at `http://127.0.0.1:3000`, and dcm4chee UI at `http://127.0.0.1:8082/dcm4chee-arc/ui2`.

### Ready-for-use verification

1. Run `.\deploy\lab.ps1 inspect lab-app` and verify the image tag, state, ports, and restart count.
2. Run `.\deploy\lab.ps1 status` and verify that the expected services are listed.
3. Run `Invoke-WebRequest http://127.0.0.1:5000/ -UseBasicParsing` and confirm HTTP 200.
4. Open the required OIE, Medplum, and dcm4chee interfaces.
5. Run the relevant service connectivity check.
6. Run the required protocol workflow from Chapters 10–13.

Verification has four levels: container running, service health, service-to-service connectivity, and complete workflow. Only the last proves that the Patient, Order, and Result workflow completed. The current `.\deploy\lab.ps1 smoke all` performs only first-level state listing.

### Startup troubleshooting

- Docker shows Client but no Server: start Docker Desktop and verify the context.
- A port is already in use: stop the conflicting service or select a free host port in `.env`, then recreate the affected service.
- `lab-app` does not become healthy: inspect `.\deploy\lab.ps1 logs lab-app -Lines 200` and verify the image, volumes, and `.env`.
- The container uses the wrong image: compare `inspect lab-app` with `config --images`; correct `LAB_APP_IMAGE` and recreate `lab-app`.
- The container is healthy but the workflow fails: continue through network, authentication, protocol response, and identifier-matching checks instead of reinstalling repeatedly.

## Part II: Use the Core Pages

<a id="chapter-7"></a>
## Chapter 7 — Dashboard

Dashboard is the default page after startup and is titled `Server Health Dashboard`. It presents the container runtime summary, three primary service groups, resource usage, and recent events.

![Dashboard after Run Checks, showing all three service groups as Healthy together with containers, ports, actions, resource usage, and recent events.](images/dashboard-checked.png)

### Page areas

- Top summary: `TOTAL`, `RUNNING`, `ATTENTION`, `CPU`, and `MEMORY`.
- `Lab Services`: HL7 v2/OIE, HL7 FHIR/Medplum, and dcm4chee/DICOM.
- Each group shows protocol status, its primary host port, and `Check`, `Start`, `Stop`, and `Restart`.
- Expandable groups show child services such as the Medplum database and cache.
- `Resource Usage` shows CPU and memory for primary containers.
- `Recent Events` shows the latest health-check results.

### Run health checks

1. Open `Dashboard`.
2. Select `Run Checks` for all groups, or select `Check` for one group.
3. Wait for `Dashboard updated`.
4. Inspect each group status and `Recent Events`.

In the isolated RC test, the initial protocol statuses were `Unknown`. After `Run Checks`, OIE, Medplum, and dcm4chee passed application, process, and protocol checks and changed to `Healthy`. A value of `7 RUNNING` does not by itself change protocol status from `Unknown` to `Healthy`.

### Service operations

`Start`, `Stop`, and `Restart` operate real Compose services; they do not only change the Dashboard display. In a shared environment, expand the group, confirm affected services, and notify other users before executing an action. `Restart` can interrupt listeners, in-flight requests, or queued messages.

This round verified `Run Checks` but did not select `Stop` or `Restart` against the shared runtime. `Degraded`, `Down`, disabled-action reasons, Enable/Disable, and complete operation-history behavior remain pending isolated full-stack verification.

<a id="chapter-8"></a>
## Chapter 8 — Patient

The Patient page uses one `Register Patient` form for HL7 v2, FHIR, GDT, and DICOM Patients. Selecting a mode changes the title, visible fields, and payload preview.

![FHIR Patient form showing mode, MRN, name, DOB, FHIR-specific fields, Valid preview, FHIR JSON, and the Local Patients table.](images/patient-fhir-preview.png)

### Common creation procedure

1. Select `Patient` in the sidebar.
2. Select `HL7 v2`, `FHIR`, `GDT`, or `DICOM` under `MODE`.
3. Enter `FIRST NAME`, `LAST NAME`, and `DATE OF BIRTH`; DOB uses `YYYYMMDD`.
4. Select `SEX`. Current values are `F`, `M`, `O`, and `U`.
5. Optionally enter an MRN. If blank, the application generates the global sequence. A manual value must be `MRN-` followed by at least six digits, for example `MRN-910001`.
6. Enter any additional mode-specific fields.
7. Select `Refresh Preview`.
8. Confirm that `Preview Status` is `Valid preview`, then inspect MRN, name, DOB, Sex, and the payload.
9. Select `Create Local Patient`.
10. Record `PAT-xxxxxx`, MRN, `VISIT-xxxxxx`, mode, state, and external reference.

`Refresh Preview` only updates the preview. It neither creates a local record nor transmits external data. Missing first name, last name, or DOB produces `Needs input`.

### Mode-specific behavior

| Mode | Additional visible fields/payload | Verified behavior on Create |
| --- | --- | --- |
| HL7 v2 | Patient class, assigned location, attending provider, account number; MSH/EVN/PID/PV1 for ADT A04 | Creates a local Patient and visit; Preview does not transmit ADT |
| FHIR | Email, active, structured address, managing organization; FHIR R4 Patient JSON | Creates the local Patient, then attempts Medplum sync; success produces `Patient/<id>`, while failure preserves the local record with `Error`/`Sync failed` |
| GDT | Phone and address; GDT 6301 fields | Creates a local GDT Patient; the Order is created separately in the Order/GDT workflow |
| DICOM | Patient class, phone, and address; DICOM Patient Module attributes | Creates a local Patient and immediately performs HL7 ADT sync to dcm4chee; this round received ACK `AA` and displayed `Synced` |

### FHIR sync recovery

If a FHIR Patient shows `Sync failed`:

1. Confirm that persisted Medplum server inventory uses `host=medplum` and `baseUrl=http://medplum:8103/fhir/R4` inside Docker.
2. Open `Medplum`.
3. Select the failed Patient and inspect the error.
4. Correct connectivity or credentials, then select `Retry`.
5. Confirm `Synced` and record the `Patient/<id>` reference.

### Duplicate prevention and limitations

- A noncanonical MRN produces a preview validation error and a failed Create request.
- An existing MRN does not create a second Patient; the UI reports `Patient MRN ... already exists.`.
- This RC UI did not expose Patient edit or delete actions. Do not assume an existing record can be edited or deleted from the Patient page.

<a id="chapter-9"></a>
## Chapter 9 — Order

The Order page creates ECG Orders. Available `MODE` values are `HL7 v2`, `FHIR`, `GDT ECG`, and `DICOM MWL`. The Patient selector lists only mode-compatible local Patients. A FHIR Order requires a synced Patient with a Medplum Patient reference.

![FHIR R4 ServiceRequest Order form showing a synced Patient, Valid preview, ServiceRequest fields, payload JSON, and Local Orders for all four modes.](images/order-fhir-created.png)

### Common creation procedure

1. Select `Order` in the sidebar.
2. Select a `MODE`.
3. Select a compatible `PATIENT`. If none is available, return to Patient and create or sync one first.
4. Enter requested time, ordering provider, and clinical indication as needed. Generated fields are assigned during Create when left blank.
5. Review mode-specific fields.
6. Select `Refresh Preview`.
7. Confirm `Valid preview` and compare Patient, MRN, code, priority/time, and payload.
8. Select the mode-specific Create button.
9. In `Local Orders`, record Order ID, mode, MRN, visit, code, status, and timestamp.

### Mode-specific creation results

| Mode | Create button | ECG definition/key identifiers | Verified result |
| --- | --- | --- | --- |
| HL7 v2 | `Create Order` | `ECG12`, alternate `93000`; `ORD-xxxxxx`, placer Order Number, visit, account number | Creates local ORM O01; backend status is `Ready to send`, which does not mean OIE/AP (QHAP) received it |
| FHIR | `Create FHIR Order` | FHIR `ServiceRequest`, `ECG12 / 12 Lead ECG`; local Order ID, identifier, `ServiceRequest/<id>` | Requires a synced Patient; creates the local Order and immediately syncs it to Medplum; this round obtained a live ServiceRequest reference |
| GDT ECG | `Create GDT Order` | `8402=EKG01`; `GDT-ORD-xxxxxx`, GDT Patient Number, field `6330` correlation | Creates a local `6302` message with backend status `Created`; this does not mean AP (QHAP) picked up the file |
| DICOM MWL | `Create DICOM MWL Order` | `ECG12`; `LAB-ORD-*`, `ACC-*`, Study UID, `RP-*`, `SPS-*` | Creates the local Order and performs MWL REST create/read-back; this round returned HTTP 200 and `Synced`, while verification remained `not_verified` |

During this round, `Local Orders` displayed all four new Orders with the green summary label `Accepted`. This is a list summary, not a shared completion state for all protocols. Use the table above and Chapters 10–13 to inspect protocol-specific status.

### Ready-for-transmission checklist

- Patient mode and Order mode are compatible.
- MRN and Patient/visit references are correct.
- Preview is `Valid preview`.
- ECG code and display match the selected mode.
- Local Order ID and mode-specific identifiers are recorded.
- A FHIR Patient is `Synced`; a DICOM Patient ADT is `Synced`.
- After creation, complete the protocol-specific send, export, query, result, or reconciliation steps.

This round did not verify Order edit/delete, every retry action, or complete external result return. Those remain for the end-to-end work in Chapters 10–13.

## Part III: Complete the Integration Workflows

<a id="chapter-10"></a>
## Chapter 10 — HL7 v2 / OIE Order Workflow

This workflow sends a local ECG Order as HL7 `ORM^O01` through Open Integration Engine (OIE) to the AP application (QHeart-AP, also referred to as QHAP), then receives the AP result as HL7 ORU through OIE. Healthcare Lab preserves the raw result and either associates it with the Patient and Order or retains it in `Unmatched Results` for investigation.

```text
ORM: Healthcare Lab -> OIE:6600 -> AP:6671
ORU: AP -> OIE:6661 -> Healthcare Lab:6665
```

![OIE Patient-Centered Console showing the selected ECG Order, OIE endpoint, ACK AA, running result listener, and an unmatched ORU](images/oie-order-workflow.png)

### Preconditions

1. On `Dashboard`, run health checks and confirm `HL7 v2 / OIE` is `Healthy`.
2. In `Settings > OIE Connection`, confirm the saved Management API connection passes its connection test.
3. In `Settings`, refresh the managed Channels and confirm both `HLAB_ORM_TO_AP` and `HLAB_ORU_TO_HLAB` are deployed. If either is missing or out of date, use its guarded `Operation preview`, review the exact route and diff, then execute the operation before the preview expires.
4. Confirm `HLAB Result Listener` is running at `0.0.0.0:6665` with MLLP enabled. Saving settings does not rebind an already running listener; use the displayed restart or `Retry` guidance when required.
5. Confirm QHeart-AP is listening on port `6671` at the destination address reachable from the OIE container.
6. In the managed ORU Channel preview/read-back, verify the deployed queue, retry interval, timeout, and ACK-validation values. Do not infer live values from the template alone.

The managed routes are fixed by purpose:

| Managed Channel | Source | Destination | Purpose |
| --- | --- | --- | --- |
| `HLAB_ORM_TO_AP` | OIE TCP Listener `:6600` | AP MLLP `:6671` | Deliver ECG Orders to AP |
| `HLAB_ORU_TO_HLAB` | OIE TCP Listener `:6661` | `lab-app:6665` | Deliver AP results to Healthcare Lab |

Do not substitute `127.0.0.1` for a destination in another container. Inside OIE, loopback means the OIE container itself.

### Send the ECG Order

1. Create an `HL7 v2` Patient as described in Chapter 8. Its ADT preview includes `MSH`, `EVN`, `PID`, and `PV1`.
2. Create an `HL7 v2` ECG Order as described in Chapter 9. Record the local Order ID, Patient MRN, visit/account identifiers, and placer Order number.
3. Open `OIE`, select the Patient, and select the Order. Confirm the `HOST / IP` and `PORT` fields point to `oie` and `6600`, the timeout is appropriate, and `MLLP` is selected.
4. Inspect `HL7 Preview`. The `MSH-10` message control ID must be unique for this transmission. The Patient/Order correlation identifiers must agree with the selected records; use fresh synthetic identifiers when executing a formal verification run.
5. Select `Send Order` once. Preserve the displayed send details and ACK.
6. In OIE, verify the corresponding `MSH-10` has one successful source receipt and one successful destination send with no error or queued message.
7. At AP, verify exactly one Order was received with the same Patient, placer Order number, and `MSH-10`.

An ACK code describes message acceptance at that hop:

| Evidence | Meaning | Required follow-up |
| --- | --- | --- |
| `AA` | The receiving hop accepted the HL7 message | Still verify OIE destination delivery and AP receipt |
| `AE` | Application error | Inspect the ACK error detail and OIE message state, correct the data/configuration, then retry with controlled correlation |
| `AR` | Application rejection | Treat as not delivered; inspect routing, message structure, and receiver policy |
| Local Orders `Accepted` | Healthcare Lab accepted or sent the local Order workflow step | Not proof that AP completed the examination or that an ORU returned |

### Receive and match the ORU result

1. AP sends a new ORU message to the Docker host's published OIE port `6661`.
2. OIE accepts the source message and `HLAB_ORU_TO_HLAB` forwards it to `lab-app:6665`.
3. Healthcare Lab returns an HL7 ACK. Confirm OIE marks the destination send successful rather than queued or errored.
4. In `OIE`, refresh and select the Patient/result. Inspect the preserved raw HL7 and the matched Patient and Order.
5. Confirm the result appears exactly once and retains its own `MSH-10`.

If Patient or Order correlation fails, Healthcare Lab must preserve the message under `Unmatched Results`; it must not attach it to an unrelated Order. Select `Preview` to inspect the message type, MRN, status, received time, and raw identifiers. Correct the source identifiers or workflow configuration rather than editing the preserved evidence.

### Outage and recovery

When live Channel read-back confirms the verified RC contract, the managed ORU destination queues connection failures and ACK timeouts and retries every 10 seconds. A verified recovery sequence is:

1. Confirm the target is the intended isolated/disposable lab Compose project. During an announced maintenance window, stop only `lab-app`; leave OIE and AP running.
2. Send one uniquely identified ORU from AP to OIE `6661`.
3. Confirm OIE accepts the source message and shows the HLAB destination as queued/retryable. Do not purge or manually resend it.
4. Start `lab-app`; confirm the `6665` listener auto-starts.
5. Poll until a recorded deadline for the OIE queue to drain, then confirm Healthcare Lab persists exactly one result for that `MSH-10`. If the deadline expires, preserve the queue state, destination error, listener state, and timestamps; mark the run failed or blocked and investigate without purging or resending.

Do not run this test against a shared runtime merely for handbook coverage. After restoring the listener or dependency, use the `HLAB Result Listener` `Retry` control only if listener status is degraded; allow the OIE destination queue to retry automatically. Do not manually resend or purge the ORU. Preserve queue state for diagnosis.

### RC verification record

The v1.0.0 RC live gate passed on 2026-07-21 with OIE `4.5.2`. The witnessed run verified managed Channel create/deploy/read-back, an ORM with ACK `AA` and exactly one AP receipt, matched and unmatched ORU handling, managed lifecycle isolation, and queued ORU recovery with exactly one persisted result. The detailed correlation ledger is maintained in `docs/oie-live-verification-evidence-z52-20260721-a.md`.

On 2026-07-22, the browser view captured above reconfirmed the actual labels and read-only state: Order endpoint `oie:6600`, MLLP enabled, `Status: Accepted`, `Last ACK: AA`, listener `Running 0.0.0.0:6665`, and an ORU retained in `Unmatched Results`. No shared-runtime Stop/Restart or duplicate send was performed during this handbook pass.

<a id="chapter-11"></a>
## Chapter 11 — FHIR R4 / Medplum Order Workflow

Healthcare Lab uses a local-first write path and a Medplum-backed read path. Creating a FHIR Patient or ECG Order first preserves local workflow intent, then immediately attempts OAuth-authenticated synchronization to Medplum. After synchronization, Medplum is the canonical source for the clinical resource JSON; the local SQLite ledger remains the source for sync state, sync/retry attempt history, errors, `OperationOutcome`, deterministic identifiers, and Medplum references.

```text
Patient page -> local Patient + FHIR ledger -> Medplum Patient
Order page   -> local Order + FHIR ledger   -> Medplum ServiceRequest
Medplum page -> live Patient / ServiceRequest / DiagnosticReport reads
                                      `-> related Observation / DocumentReference / Binary
```

![Medplum Patient-Centered Console showing a synced Patient, active ServiceRequest, live DiagnosticReport query result, and Medplum live ServiceRequest JSON](images/medplum-workflow.png)

### Preconditions and endpoint selection

1. Run the Dashboard check and confirm `HL7 FHIR / Medplum` is `Healthy`.
2. Confirm the saved Medplum server inventory record is enabled and has valid OAuth credentials.
3. As documented in Chapter 5 and `deploy/README.md`, when `lab-app` runs in Docker, the persisted values must use the Compose service address:

   ```text
   host    = medplum
   baseUrl = http://medplum:8103/fhir/R4
   ```

4. Do not substitute the browser URL or `MEDPLUM_PUBLIC_BASE_URL` for this sync address. A smoke check can pass while Patient/Order sync fails if the persisted server `baseUrl` is wrong.

### Create and sync the Patient and Order

1. Create a FHIR Patient as described in Chapter 8. A successful write displays `Synced` and a `Patient/<id>` Medplum reference.
2. Create a FHIR Order as described in Chapter 9. The Patient must already have a valid synced `Patient/<id>` reference.
3. Healthcare Lab creates one local Order anchor and one FHIR ledger record, builds a FHIR R4 `ServiceRequest`, and immediately attempts Medplum sync.
4. On success, confirm `Synced`, `ServiceRequest/<id>`, and the following relationship in the live JSON:

   ```text
   ServiceRequest.subject.reference = Patient/<id>
   ```

5. Confirm the ECG definition, including `ECG12 / 12 Lead ECG`, status, intent, priority, requested time, requester, and deterministic identifier.

The current workflow does not create or require a FHIR `Task`. `ServiceRequest` is the Order representation.

### Use the Medplum Patient-Centered Console

1. Open `Medplum` and select `Refresh`. Use the status filter to show `All statuses`, `Synced`, `Pending sync`, `Sync failed`, or `Syncing` records.
2. Select a Patient row. The `Selected Patient` panel shows MRN, sync state, Medplum reference, and update time.
3. Select the Patient disclosure arrow independently when inline Order/Result rows are needed. Selecting a Patient and expanding a row are separate actions.
4. Under `Orders & Results`, select the `ServiceRequest` for the ECG Order.
5. Inspect `Console JSON`. For a reachable synced resource, `Preview Source` must say `Medplum live JSON`; this is the canonical resource returned by Medplum, not merely the locally submitted payload.
6. Use `Copy JSON` only with synthetic data. Do not place real PHI, OAuth tokens, or credentials in troubleshooting evidence.

If live preview of a known synced ledger record fails, the console may show the preserved local submitted JSON and label it as a local fallback. That fallback proves the original workflow intent was retained; it does not prove the Medplum resource is currently available or authoritative.

### Discover DiagnosticReport results

DiagnosticReport discovery is selection-triggered and live. Selecting or refreshing a synced Patient causes Healthcare Lab to query Medplum; there is no background scheduler in this console workflow.

1. Select a synced Patient. Healthcare Lab queries `DiagnosticReport` by the Patient reference.
2. When a `ServiceRequest` is selected, Healthcare Lab prefers a `based-on=ServiceRequest/<id>` search.
3. If Medplum rejects or does not support the `based-on` search with an expected query error, Healthcare Lab safely falls back to a Patient search and filters `DiagnosticReport.basedOn[]` server-side.
4. The UI separates `Order-linked results` from `Patient-level results`. A report without a ServiceRequest reference remains visible as Patient-level; it is not silently discarded.
5. Each report summary shows its code/display, status, effective or issued date, linked Order when available, result count, and attachment/reference count.
6. Select `Preview` on the report or a related row to fetch live JSON for `Observation`, `DocumentReference`, or referenced `Binary` resources. Related resources are loaded lazily and are not copied into a complete local FHIR shadow store.

An empty Bundle is a valid result. `No reports` means Medplum was reachable and returned no matching DiagnosticReports; it must not be reported as a service outage.

### Sync states, errors, and Retry

| State or display | Meaning | Operator action |
| --- | --- | --- |
| `Pending sync` | Local workflow intent exists but has not completed Medplum sync | Confirm configuration/connectivity, then use `Retry` |
| `Syncing` | A sync attempt is in progress | Wait for the bounded request to finish; do not submit a duplicate create |
| `Synced` | A Medplum id/reference and successful sync time are recorded | Inspect `Medplum live JSON`; no Retry action is shown |
| `Sync failed` | The local record remains, with a human-readable error and available response evidence | Inspect the error and `OperationOutcome`, correct the cause, then retry the same record |
| `Live fetch failed; showing local JSON` | A previously synced reference could not be read live | Treat the JSON as submitted fallback, not canonical current data |
| `Fetch failed` | Live DiagnosticReport/resource query failed | Check authorization, endpoint, HTTP response, and returned `OperationOutcome` |

Retrying the same ledger record with its deterministic FHIR identifier is idempotent. Healthcare Lab searches Medplum using that identifier: if the resource already exists, it records that existing id/reference; otherwise it creates it once. Do not create a replacement local Patient or Order merely because a sync attempt failed.

FHIR errors may include a human-readable summary, HTTP status, raw response, and a FHIR `OperationOutcome`. Preserve a bounded, redacted projection of the issue severity, code, diagnostics, expression/location, request URL, and attempt timestamp when escalating. Remove PHI, tokens, authorization data, credentials, and sensitive query-string values; do not include unrelated resource bodies.

### RC verification record

The 2026-07-22 browser pass verified successful Patient and ServiceRequest synchronization, the required persisted Docker `baseUrl`, failure followed by corrected inventory and `Retry -> Synced`, and live Medplum references. The RC view captured above shows a selected Patient with one active `12 Lead ECG` ServiceRequest, `Preview Source: Medplum live JSON`, and `No reports`; the empty live result was displayed without marking Medplum unhealthy. No destructive Medplum action was exposed or performed.

<a id="chapter-12"></a>
## Chapter 12 — GDT 2.1 Order Workflow

Healthcare Lab exchanges GDT 2.1 files with AP (QHeart-AP/QHAP) through one shared bridge root. It writes an outgoing `6302` New Test Request, then imports the returned `6310` Test Data Transfer and its artifact references. The UI names `GDT-OUT` and `GDT-IN` from Healthcare Lab's point of view.

```text
Healthcare Lab -- GDT-OUT 6302 --> /data/gdt-bridge/inbox --> AP
Healthcare Lab <-- GDT-IN  6310 -- /data/gdt-bridge/outbox <-- AP
```

![GDT Patient-Centered Console showing bridge paths, watcher state, an expanded Patient, a GDT-OUT Order, and the raw 6302 payload](images/gdt-workflow.png)

### Bridge folder contract

Set `GDT_BRIDGE_HOST_PATH` to the host folder shared with AP. Docker mounts that root at `/data/gdt-bridge`; Healthcare Lab does not create an absent host bridge root for the operator. Create and permission the required folders before exchange:

| Folder | Producer → consumer | Purpose |
| --- | --- | --- |
| `inbox/` | Healthcare Lab → AP | Generated `6302` requests waiting for AP |
| `outbox/` | AP → Healthcare Lab | Returned `6310` results waiting for import |
| `processing/` | Healthcare Lab internal | Same-volume claim while an inbound result is being imported |
| `archive/` | Healthcare Lab internal | Successfully imported `6310` files in PoC/debug archive mode |
| `error/` | Healthcare Lab internal | Files that could not be parsed or persisted |
| `reports/` | AP/shared | Referenced PDF, DICOM, XML, or other result artifacts |

Do not interpret the `Bridge Inbox` table heading as the filesystem `inbox/`. That table lists inbound results discovered from AP's `outbox/`, plus archived/error history.

### Configure the GDT Console

1. Open `GDT`. Confirm `GDT-IN > Folder Path` is `/data/gdt-bridge/inbox` and `GDT-OUT > Folder Path` is `/data/gdt-bridge/outbox` in the current UI. Despite those field labels, the operational direction is the folder contract above.
2. Set the polling intervals. The default RC values are 2 seconds; values below 0.25 seconds are not accepted.
3. Select `Save`, then `Refresh`, and confirm `Bridge Folder` shows `Ready`.
4. The backend supports the following inbound filename profiles, but the current RC Console does not expose a profile selector. Configure the profile, sender, and receiver through the approved deployment/API configuration before starting the watcher; do not assume `Save` changes them:

   - `permissive`: accept otherwise eligible `.gdt` files for lab use.
   - `gdt21`: accept configured legacy sender/receiver filenames and allowed numeric sequence extensions.
   - `gdt35`: accept `<receiver>_<sender>_<sequence>.GDT` using configured abbreviations.

5. Stop automatic import before changing watcher configuration. Use `Start` to begin automatic `outbox/` polling and confirm the badge changes from `Off` to `On (<seconds>s)`; use `Stop` to leave manual import available.

### Create and export a 6302 Order

1. Create a GDT Patient and GDT ECG Order as described in Chapters 8 and 9. The RC test type is `8402=EKG01` (12-lead resting ECG).
2. Open `GDT`, select the Patient, and use the disclosure arrow. The expanded Patient shows `GDT-OUT > Orders` and `GDT-IN > Results` separately.
3. Select `Preview GDT-OUT`. Verify the byte-counted payload contains at least:

   | Field | Expected purpose |
   | --- | --- |
   | `8000=6302` | New Test Request set type |
   | `8100` | Five-digit complete message byte length |
   | `9218=02.10` | GDT 2.1 version |
   | `3000` | Canonical Patient MRN |
   | `6330` | Local GDT Order correlation, such as `GDT-ORD-000001` |
   | `8402=EKG01` | ECG test code |
   | `8315` / `8316` | Receiver and sender identifiers |

4. Confirm each record's three-digit length includes the length digits, four-digit field code, content, and trailing CRLF. Do not edit the rendered file manually; an incorrect record or total byte length is rejected.
5. Select `Write GDT-OUT` once. Healthcare Lab writes a temp file and atomically renames it into `/data/gdt-bridge/inbox` using a name such as:

   ```text
   gdtin_GDT-ORD-000001_<timestamp>.gdt
   ```

6. Confirm the Order retains its local identity, export path/status, and event even if the filesystem write fails. AP should consume the completed file rather than a partial/temp file.

`Created` means the local Order and raw 6302 exist. It does not prove the file was written, AP consumed it, or a result returned.

### Import and match a 6310 result

AP writes the completed result file into `/data/gdt-bridge/outbox`. Import it either manually from `Bridge Inbox` with `Import GDT-IN` or automatically with the watcher.

The importer:

1. Skips hidden, `.tmp`, `.temp`, and internally managed processing files.
2. Waits for file size/timestamp stability during watcher scans.
3. Processes eligible files FIFO by creation time when reliable, otherwise by deterministic timestamp/filename order.
4. Claims one file with a same-volume rename into `processing/` before parsing.
5. Parses only a valid byte-counted `6310`, preserves raw GDT and parsed fields, and continues to later files if one file fails.

Order matching gives precedence to an unambiguous Order identifier carried in fields such as `6330` or `6200`. A known `3000` Patient number without a supported Order identifier may preserve Patient context, but the result remains unmatched/review-needed; Healthcare Lab must not attach it to the latest Order merely because the Patient matches.

For a matched result, expand the Patient and select `Preview GDT-IN`. The current detail panel shows `Match`, result `Status`, a measurement summary, artifact references, and raw `6310`. Use the raw payload and persisted API/repository evidence to verify:

- result status and interpretation from `8418`, `6220`, `6227`, and `6228`;
- canonical measurements such as HR, PR, QRS, QT, and QTC from repeated `8410`/`8420`/`8421` groups;
- the matched Patient and local GDT Order;
- preserved raw `6310` text and import/match events.

### Artifact references

A `6310` may describe artifacts through repeated `6302`–`6305` groups. The current result coordinator normalizes format, description, reference/path/URL, role, and availability status. Missing or unverifiable targets are retained with warning status and do not invalidate an otherwise parseable result. The current RC Console offers `Open` for safe HTTP(S) URLs and `Copy` for references; it does not provide a general local-file download action. DICOM remains reference-only and is not rendered.

Use artifact open/download actions only when the reference is safe and expected. Copyable paths, URLs, and raw payload evidence may contain patient identifiers; use synthetic data and redact host/user paths before sharing.

### Archive, delete, error, and duplicate behavior

| Outcome | File disposition | Durable evidence |
| --- | --- | --- |
| Success with `archive` | Move from `processing/` to collision-safe `archive/` path | Raw GDT, canonical result, match, attachments, and events remain in SQLite |
| Success with `delete` | Delete exchange file after persistence succeeds | The same persisted result evidence remains; this is closer to GDT read-and-delete behavior |
| Parse/persist failure | Move to `error/` when possible | The current import/watcher result exposes diagnostics; other files continue |
| Claim/stability/binding skip | Leave for a later scan or operator correction | Skip reason appears in watcher/import result |

Archive mode is the PoC/debug default. Changing to delete mode removes the successfully processed exchange file, so confirm evidence and backup expectations before enabling it.

Do not copy an already processed `6310` back into `outbox/`. Archive/delete disposition prevents the original exchange file from being scanned again, but the current RC has not demonstrated durable idempotency when an operator or device reintroduces the same filename/content.

### Troubleshooting checklist

- `Bridge Folder` not ready: verify the host path exists, is mounted, contains sibling `inbox/` and `outbox/`, and is writable by the container.
- Order remains `Created`: use `Write GDT-OUT`, then inspect export status/path; do not infer AP receipt.
- File does not appear for import: verify it is in AP's `outbox/`, has a supported stable filename, and matches the configured binding profile/sender/receiver.
- Import error: validate `8000=6310`, `8100`, `9218=02.10`, required `3000` and `8402`, and byte lengths.
- Result is unmatched: compare `6330`/`6200` with the local `GDT-ORD-*`; do not force a Patient-only match.
- Watcher cannot be reconfigured: select `Stop`, update the approved deployment/API configuration, refresh the Console, then start it again.

### RC verification record

The 2026-07-22 browser pass confirmed the actual Patient-Centered Console labels, `/data/gdt-bridge/inbox` and `/data/gdt-bridge/outbox`, 2-second poll fields, watcher `Off`, expanded `GDT-OUT` and `GDT-IN` sections, the local identifiers `MRN-000005`, `GDT-PAT-000005`, and `GDT-ORD-000001`, and a valid raw `6302` containing `8000=6302`, `9218=02.10`, `6330=GDT-ORD-000001`, and `8402=EKG01`. This handbook pass did not write another shared-folder file, start the watcher, manufacture a 6310, or alter archived shared evidence; 6310 import/recovery behavior is covered by the repository's GDT integration/runtime tests and the persisted imported-file history shown in the console.

Two RC defects remain release blockers for this chapter: canonical measurement objects currently render as `[object Object]` in the GDT-IN summary, and durable duplicate prevention has not been demonstrated for a previously processed 6310 that is reintroduced into `outbox/`. The result detail also does not yet surface interpretation/comments or import/match events outside the raw payload. Fix and browser-reverify these items before treating the GDT SOP as final v1.0.0 behavior.

<a id="chapter-13"></a>
## Chapter 13 — DICOM / dcm4chee Order Workflow

This workflow first synchronizes a DICOM Patient to dcm4chee through HL7 ADT and then creates a Modality Worklist (MWL) item. AP (QHAP) queries MWL, performs the examination, and C-STOREs the images. Healthcare Lab then discovers the result through QIDO/WADO and reconciles it. Healthcare Lab owns Patient and Order intent plus the mapping ledger; dcm4chee is authoritative for MWL, Studies, and DICOM artifacts.

```
Patient -> ADT :2575 -> dcm4chee
Order   -> MWL REST (WORKLIST) -> automated read-back
AP      -> DIMSE :11112 (DCM4CHEE) query / C-STORE
Archive -> QIDO/WADO (DCM4CHEE) -> reconciliation
```

![The dcm4chee Patient-Centered Console showing ADT ACK AA, MWL query, AP C-STORE results, Matched reconciliation, and the Study/Series/Instance hierarchy](images/dcm4chee-workflow.png)

### Prerequisites and AE/endpoints

1. Run the Dashboard health checks and confirm `dcm4chee / DICOM` is `Healthy`.
2. Open the `dcm4chee` Console and confirm profile diagnostics are `Healthy`/`Valid`.
3. Confirm the AE Titles: archive/AP DIMSE called AE `DCM4CHEE`, Healthcare Lab calling AE `HEALTHCARE_LAB`, MWL REST surface `WORKLIST`, and scheduled station/AP calling AE `ECG_AP`.
4. Select the address for the caller:

   | Caller | Endpoint/AE | Purpose |
   | --- | --- | --- |
   | Healthcare Lab container | `dcm4chee:2575` | Patient ADT |
   | Healthcare Lab automated verification | `/aets/WORKLIST/rs/mwlitems` | MWL REST create/read-back |
   | Healthcare Lab archive discovery | `/aets/DCM4CHEE/rs` | QIDO/WADO |
   | Physical AP | `<Docker-host-IP>:11112`, called AE `DCM4CHEE`, calling AE `ECG_AP` | DIMSE MWL query and C-STORE |
   | Browser | `http://127.0.0.1:8082/dcm4chee-arc/ui2` | dcm4chee UI |

   Do not configure the REST surface `WORKLIST` as the AP's DIMSE called AE or substitute a browser URL for a container-internal address. If AP runs away from the Docker host, use a lab-host IP reachable from AP, not `127.0.0.1`.

A local profile without authentication can be valid for a trusted lab. A Valid diagnostic does not make that profile production-ready.

### Create and synchronize a DICOM Patient

1. Create a DICOM Patient as described in Chapter 8.
2. The system normally synchronizes Patient master data to dcm4chee through ADT after local creation. If it is still unsynchronized when an Order is created, MWL preflight first attempts Patient synchronization and must not POST MWL if that attempt fails.
3. On the Patient row, confirm `ADT Sync: Synced`, `ACK: AA`, and the endpoint. `AA` means the receiver accepted this ADT; `AE`, `AR`, or a timeout is not a successful synchronization.
4. The Patient must be `Synced` before a subsequent MWL Order can be treated as available to AP.

### Create a DICOM MWL Order

1. As described in Chapter 9, select a synchronized DICOM Patient and create a `DICOM MWL` Order.
2. Record the local Order ID, Accession Number, Study Instance UID, Requested Procedure ID, Scheduled Procedure Step ID, DICOM Patient ID (normally mapped from MRN in this lab), and the issuer separately.
3. Confirm MWL create/read-back completes. Green `Accepted` in Local Orders is only a local summary; `MWL Sync: Created` means the worklist item was created; `MWL Queryable: Verified` only proves that the configured `WORKLIST` REST surface returned a strong-identifier match. It does not prove a physical AP completed a DIMSE query.
4. Query/read back before retrying. If an item already exists with the same deterministic identifiers, retain its mapping and do not POST a duplicate MWL item.

### AP query, C-STORE, and result reconciliation

1. From AP, connect to reachable `<Docker-host-IP>:11112` and run a DIMSE MWL query with calling AE `ECG_AP` and called AE `DCM4CHEE`. Verify Patient ID/issuer, Accession Number, Requested Procedure ID, SPS ID, scheduled time, and station AE. This step is the live AP pickup proof.
2. After the examination, C-STORE DICOM instances to archive called AE `DCM4CHEE`; do not send them to `WORKLIST`.
3. In the Healthcare Lab dcm4chee Console, select the Patient/Order and refresh. Confirm `AP C-STORE Result` reports the discovered result-row count.
4. Confirm `Reconciliation: Matched`. The system prefers a strong Study Instance UID match, then Accession Number in the same server/profile namespace, and then RP ID plus SPS ID. Weak identifiers, cross-Patient conflicts, or multiple candidates must remain unresolved/ambiguous and must not be attached to an arbitrary Order.
5. Expand the Study, Series, and Instance hierarchy. Verify Study/Series/SOP Instance UIDs, modality, instance count, and times. `Open Viewer` inspects archive content; `Copy Retrieve` copies the retrieval reference. Neither action changes reconciliation.

If AP reports `C-STORE returned unknown status: 0x110`, `0x110` is DICOM `0x0110 Processing Failure`. It only establishes that archive processing failed and does not by itself mean that the AE was unauthorized. Inspect `errorComment`/`Caused by` in the dcm4chee server log at the same timestamp. `java.nio.file.AccessDeniedException: /storage/fs1` means dcm4chee accepted the Association and C-STORE request, but WildFly could not write the archive storage. In contrast, an AE policy/authorization failure normally rejects the Association before C-STORE or explicitly returns `0x0124 Refused: Not Authorized`; use the actual AP and server-log response as evidence. Compose now runs `dcm4chee-storage-init` at startup to correct the configured storage directory. After correction, resend the instance; a successful response is `status=0H`.

### State interpretation and recovery

| Display | Meaning | Action |
| --- | --- | --- |
| ADT `Synced` / ACK `AA` | dcm4chee accepted the Patient ADT | Continue with Order creation |
| MWL `Created`, query unverified | Automated REST create/read-back verification is incomplete | Inspect the configured `WORKLIST` REST target |
| MWL Query `Verified` | `WORKLIST` REST returned the expected strong-identifier match | AP must still DIMSE-query `DCM4CHEE:11112` |
| No result / query failed | No matching QIDO result exists, or the archive query failed | Distinguish an empty result from connectivity/authentication failure; do not recreate the Order |
| Unresolved / ambiguous | Strong identifiers are missing or multiple candidates exist | Compare Patient, Study UID, Accession, and RP/SPS; preserve evidence for review |
| Matched | One result is linked uniquely to the Order | Verify the hierarchy and viewer/retrieve actions |
| Duplicate | The SOP/Study was already processed | Do not resend or create another mapping; inspect AP retry or archive ingest history |

Never guess a match for a wrong-Patient, missing-accession, or unlinked Study by choosing the newest Order. Correct source identifiers or mapping configuration and query/reconcile again. Do not delete the original Study or recreate a Patient/Order merely to turn the UI green.

For the repeatable simulated-AP path, PDF/DICOM evidence artifact, `simulated_ap_return` source label, or evidence API, follow `docs/dcm4chee-production-e2e-verification.md` in an isolated environment. Simulated evidence can verify mapping and UI behavior, but it cannot replace physical-AP DIMSE pickup/C-STORE proof. Label captured evidence as live or simulated and use synthetic Patients only.

### RC verification record

The 2026-07-22 browser pass read existing synthetic `MRN-000003`/`ORD-000003` evidence without mutating the shared workflow: Patient ADT was `Synced`, ACK was `AA`, and the endpoint was `dcm4chee:2575`; MWL creation was complete and REST query verification was `Verified`; preserved AP C-STORE evidence showed `3 result row(s)`; reconciliation was `Matched`. The UI also read back the Study/Series/Instance hierarchy, viewer/retrieve actions, raw MWL JSON, and valid profile diagnostics. This pass did not re-witness physical-AP DIMSE pickup/C-STORE, create another Patient or Order, or stop/restart the shared runtime.

## Part IV: Operate and Recover the System

<a id="chapter-14"></a>
## Chapter 14 — Operations and Troubleshooting

This chapter covers routine checks, layered diagnosis, controlled recovery, and pre-upgrade backup. Preserve evidence first, then diagnose in this order: container → service health → network/port → authentication → protocol response → workflow state → identifier matching → UI presentation. Do not jump from a UI symptom to data deletion or reinstallation.

### Routine checks

1. Open Dashboard and confirm `TOTAL`, `RUNNING`, `ATTENTION`, CPU, and memory have no unexpected changes.
2. `Refresh` only reloads current state. Use `Run Checks` for real protocol probes, or `Check` only the target group.
3. Confirm the states of `HL7 v2 / OIE`, `HL7 FHIR / Medplum`, and `dcm4chee / DICOM`; expand groups to inspect child services.
4. Inspect `Recent Events`, protocol-console diagnostics, listener/watcher state, and incomplete workflows.
5. Use a synthetic smoke Patient/Order for the required path. All containers running does not prove an end-to-end workflow.

The 2026-07-22 read-only browser pass showed seven services running, zero attention, and all three protocol groups `Healthy`. It also confirmed the `Refresh`, `Run Checks`, group-level `Check/Start/Stop/Restart`, and `Recent Events` labels. No runtime control action was executed.

### Preserve safe incident evidence first

Before correction, record the timestamp and timezone, synthetic Patient/MRN, local Order ID, protocol, external reference, current state, last successful step, error summary, HTTP/HL7 ACK status, container image/tag, and relevant bounded logs. For an OIE queue incident, also preserve Channel ID/revision, destination state, retry timeline, and `MSH-10`; never purge or manually resend merely to clear the evidence.

Before sharing, remove PHI, OAuth tokens, passwords, Authorization/Cookie headers, complete credentials, sensitive query strings, unbounded upstream bodies, and private host/user paths. Raw HL7, FHIR JSON, GDT, DICOM metadata, and screenshots may all contain Patient identifiers; use synthetic data only.

Common read-only checks:

```powershell
.\deploy\lab.ps1 status
.\deploy\lab.ps1 inspect lab-app
.\deploy\lab.ps1 logs lab-app -Lines 200
.\deploy\lab.ps1 logs oie -Lines 200
Invoke-WebRequest http://127.0.0.1:5000/ -UseBasicParsing
```

### Layered diagnosis

| Layer | Question | Next action |
| --- | --- | --- |
| Container | Is a service not running/healthy, is restart count increasing, or is the image wrong? | Inspect `status`, `inspect`, and bounded logs; verify Docker daemon, volume, and image tag |
| Service health | Is the container normal while Dashboard is `Unknown`, `Degraded`, or `Down`? | Run the target `Check`, read each probe and `Recent Events`; do not rely only on container health |
| Network/port | Is there a timeout, refused connection, wrong host, or wrong published port? | Distinguish browser/host, Docker service name, and external-AP endpoints; inspect firewall and port collisions |
| Authentication | Is there HTTP 401/403 or an OAuth/OIE-management failure? | Verify credential presence, scope/expiry, and TLS mode; never paste secrets into logs |
| Protocol response | Is there HL7 `AE/AR`, FHIR `OperationOutcome`, GDT parse failure, or DICOM query/C-STORE failure? | Preserve bounded protocol diagnostics and correct payload, routing, or receiver policy |
| Workflow state | Does a local record exist while sync/export/query/result is incomplete? | Use that protocol's state and Retry; do not create a replacement Patient/Order |
| Identifier matching | Is the result unmatched, ambiguous, or duplicate? | Compare MRN/issuer, Order ID, MSH-10, ServiceRequest, GDT `6330`, and Study UID/Accession/RP/SPS |
| UI presentation | Is backend evidence correct while the page is blank, stale, or malformed? | Refresh, inspect browser console/API response, and preserve a screenshot; do not alter authoritative data to fit the UI |

### Protocol quick triage

| Symptom | Inspect first | Safe recovery |
| --- | --- | --- |
| OIE Order has no ACK / ORU is queued | `oie:6600`, AP `6671`, OIE ingress `6661`, HLAB listener `lab-app:6665`, Channel deployed state, and queue | Restore the dependency and allow destination auto-retry. Use listener `Retry` only when the listener is degraded; never purge/manually resend |
| FHIR `Sync failed` | Persisted Medplum `baseUrl`, OAuth, and `OperationOutcome`; Docker requires `http://medplum:8103/fhir/R4` | Correct inventory/credential and Retry the same ledger record; do not create a duplicate resource |
| GDT file is not imported | Bridge mount, `inbox/`/`outbox/` direction, filename profile, watcher, byte lengths, and `processing/archive/error` disposition | Wait for file stability, then manual-import or start watcher; preserve raw 6310 and never replay a processed file |
| DICOM Patient/MWL fails | ADT ACK, `dcm4chee:2575`, `WORKLIST` REST read-back, and stable identifiers | Repair Patient sync first; query/read back before MWL retry to avoid a duplicate POST |
| AP C-STORE returns `0x0110`/`110H` | dcm4chee `server.log`, `errorComment`/`Caused by` at the same timestamp; inspect the configured storage directory when `AccessDeniedException` appears | `0x0110` is a general processing failure, not proof of AE denial. For `/storage/fs1` permission failure, confirm `dcm4chee-storage-init` is `Exited (0)` and the directory is `wildfly:wildfly`, `0775`; resend after correction and never delete the archive volume |
| DICOM result is unmatched | Patient ID/issuer, Study UID, Accession, RP/SPS, and server/profile namespace | Correct mapping, then refresh/reconcile; never guess the newest Order |

### Select the smallest recovery action

| Action | Actual effect | Use when |
| --- | --- | --- |
| Refresh/Check | Does not change workflow data; reloads state or runs probes | First action |
| Protocol Retry | Retries the same persisted record/listener | The cause is corrected and the state is explicitly retryable |
| Start/Stop | Starts or stops the selected Compose service/group | In a maintenance window after checking affected services, queues, and other users |
| `restart` wrapper | Runs `up -d --force-recreate`, replacing the container and applying Compose/env | After image, environment, published-port, or runtime-configuration changes |
| Reinstall | Redeploys the full bundle | Only when installation content is unrecoverable and a backup/rollback plan exists |
| Reset/delete/purge | May permanently remove workflows, queues, or data | Not a routine handbook action; requires an explicit maintenance procedure and verified backup |

Dashboard `Stop`/`Restart` controls the real runtime. Before using it, expand the target group and confirm affected services, listeners, in-flight requests, OIE queues, and the GDT watcher. If only a managed OIE Channel destination, queue, timeout, or ACK validation changed, Preview, Apply, and redeploy the Channel; Channel redeploy cannot change a Compose-published port.

### Backup, upgrade, and rollback

Before upgrade, schedule a maintenance window: stop new operations, allow in-flight workflows to finish, and pause AP reads/writes against the GDT shared folder. Stopping `lab-app` makes SQLite quiescent; it does not prevent an external AP from changing GDT files while they are copied.

First preserve a release manifest: record `inspect lab-app`, `config --images`, the current immutable `LAB_APP_IMAGE`, Compose bundle version, and backup timestamp. Preserve the effective `.env` separately in access-controlled secret storage so rollback can reconstruct configuration; never put it in screenshots, tickets, ordinary logs, or a publishable backup artifact.

Then create an operator-controlled backup and stop only `lab-app`. The following `Copy-Item` applies only to the default `GDT_BRIDGE_HOST_PATH=instance\gdt-bridge`:

```powershell
New-Item -ItemType Directory -Force backup\v1.0.0
.\deploy\lab.ps1 stop lab-app
docker compose --env-file .env -f deploy\docker-compose.yml cp lab-app:/app/instance backup\v1.0.0\instance
Copy-Item -Recurse instance\gdt-bridge backup\v1.0.0\gdt-bridge
```

If `GDT_BRIDGE_HOST_PATH` is a custom AP share, resolve and verify its actual absolute host path, then copy that exact folder to the backup. Do not copy the default path and claim completion. Confirm AP remains quiesced, the backup contains the instance database and evidence from the actual GDT bridge, and both can be read back from controlled storage. Do not include `.env`, secrets, or real Patient data in a backup artifact intended for publication.

Set `LAB_APP_IMAGE` in `.env` to the target immutable tag, then:

```powershell
docker compose --env-file .env -f deploy\docker-compose.yml pull lab-app
.\deploy\lab.ps1 restart lab-app
Invoke-WebRequest http://127.0.0.1:5000/ -UseBasicParsing
```

After upgrade, rerun Dashboard checks and the required protocol smoke workflow. Resume AP exchange only after they pass.

This release does not yet provide a fully verified named-volume restore command, so this section is not an executable destructive-rollback SOP. If rollback is required, keep AP exchange quiesced, stop `lab-app`, preserve the failed-upgrade instance separately, and retain the release manifest and logs. Restore the complete matching instance backup and configuration only under a controlled restore runbook or release-maintainer direction; verify the restore target, schema compatibility, and recoverability before selecting the previous immutable `LAB_APP_IMAGE` and recreating. Never merge a backup into an unknown or non-empty instance, and never switch only the image: image rollback may not reverse a database migration.

### Upgrade or incident completion criteria

- Dashboard and target-protocol diagnostics have returned to the expected state.
- The same failed workflow succeeds without a duplicate Patient, Order, message, resource, or Study mapping.
- OIE queues drain through normal retry; GDT processing/error disposition is explainable; FHIR/DICOM external references read back.
- The before/after timeline, smallest action taken, verification result, and remaining limitations are recorded.
- If completion is impossible, mark the run failed/blocked and preserve evidence; never close it by deleting data, purging a queue, or fabricating a green state.

## Appendix A — Command Quick Reference

Run these PowerShell commands from the deployment-bundle root, where `.env` and `deploy\docker-compose.yml` are present. Use the wrapper for routine operations so service aliases and Compose arguments remain consistent. A successful command proves only the stated layer; complete the ready-for-use or protocol verification in Chapters 6 and 10–13 before declaring the system operational.

### Host and Compose checks

| Purpose | Command | Expected evidence / boundary |
| --- | --- | --- |
| Check Docker client and server | `docker version` | Both Client and Server sections are available. |
| Check Compose | `docker compose version` | A Compose v2-compatible command is available. |
| Check the Docker host | `docker info --format 'Server={{.ServerVersion}} OSType={{.OSType}} Arch={{.Architecture}} CPUs={{.NCPU}} Memory={{.MemTotal}}'` | `OSType=linux`; v1.0.0 RC was verified on `amd64`. |
| Validate effective Compose configuration | `docker compose --env-file .env -f deploy\docker-compose.yml config --quiet` | Exit code 0 validates interpolation and Compose structure, not credentials or connectivity. |
| List effective images | `docker compose --env-file .env -f deploy\docker-compose.yml config --images` | Compare every image with the release matrix; use an immutable application tag. |

### Routine lifecycle and inspection

| Purpose | Command | Actual effect / caution |
| --- | --- | --- |
| Inspect `lab-app` | `.\deploy\lab.ps1 inspect lab-app` | Returns Compose container metadata in JSON, including image, state, ports, and restart count. |
| Show the whole stack | `.\deploy\lab.ps1 status` | Runs Compose `ps`; it does not test application or protocol behavior. |
| Show one logical service | `.\deploy\lab.ps1 status <service>` | Accepts `oie`, `medplum`, `medplum-postgres`, `medplum-redis`, `medplum-app`, `dcm4chee`, `dcm4chee-db`, `ldap`, `lab-app`, `gdt-bridge`, `hl7tester`, or `gdt-hospital`. The last three map to `lab-app`. |
| Start the whole stack | `.\deploy\lab.ps1 start all` | Runs Compose `up -d`. Use a service name instead of `all` to limit scope. |
| Stop the whole stack | `.\deploy\lab.ps1 stop all` | Stops containers without deleting named volumes. Pause AP exchange and drain or record in-flight work first. |
| Recreate one service | `.\deploy\lab.ps1 restart <service>` | Runs `up -d --force-recreate --no-deps`; this replaces the selected container and applies image, environment, and Compose changes. It is not an in-process restart. |
| Run the wrapper smoke check | `.\deploy\lab.ps1 smoke all` | Runs Compose `ps` only. Follow with HTTP, Dashboard, connectivity, and workflow checks. |
| Read recent logs | `.\deploy\lab.ps1 logs <service> -Lines 200` | Reads the last 200 lines. Treat output as sensitive: redact PHI, credentials, tokens, payloads, paths, and identifiers before sharing. |

Use the smallest service scope that solves the problem. `restart all` recreates the entire stack; confirm dependencies, queues, listeners, other users, and the maintenance window before doing so. `stop`, `restart`, and Dashboard lifecycle actions affect the real runtime.

### Installation and HTTP verification

```powershell
Copy-Item .env.example .env
New-Item -ItemType Directory -Force instance\gdt-bridge\inbox
New-Item -ItemType Directory -Force instance\gdt-bridge\outbox
docker compose --env-file .env -f deploy\docker-compose.yml config --quiet
docker compose --env-file .env -f deploy\docker-compose.yml config --images
docker pull ghcr.io/tzu-huang/healthcare-lab:1.0.0
docker compose --env-file .env -f deploy\docker-compose.yml up -d
docker compose --env-file .env -f deploy\docker-compose.yml ps
Invoke-WebRequest http://127.0.0.1:5000/ -UseBasicParsing
```

HTTP 200 verifies only the Healthcare Lab web endpoint. Run Dashboard checks and the required end-to-end protocol workflow before use.

### Backup and application-image upgrade

Before these commands, stop new operations, finish or record in-flight workflows, and pause all AP reads and writes against the GDT exchange folder. Preserve `inspect lab-app`, `config --images`, the immutable `LAB_APP_IMAGE`, the bundle version, and the backup timestamp. Store the effective `.env` separately in controlled secret storage.

For the default `GDT_BRIDGE_HOST_PATH=instance\gdt-bridge` only:

```powershell
New-Item -ItemType Directory -Force backup\v1.0.0
.\deploy\lab.ps1 stop lab-app
docker compose --env-file .env -f deploy\docker-compose.yml cp lab-app:/app/instance backup\v1.0.0\instance
Copy-Item -Recurse instance\gdt-bridge backup\v1.0.0\gdt-bridge
```

If `GDT_BRIDGE_HOST_PATH` is custom, resolve and verify its absolute host path and copy that exact folder instead. Read back and verify both backup trees before upgrading. Then set `LAB_APP_IMAGE` to the target immutable tag and run:

```powershell
docker compose --env-file .env -f deploy\docker-compose.yml pull lab-app
.\deploy\lab.ps1 restart lab-app
Invoke-WebRequest http://127.0.0.1:5000/ -UseBasicParsing
```

Resume AP exchange only after Dashboard and the required protocol smoke workflow pass. This release has no fully verified named-volume restore command; Appendix A therefore does not provide a direct rollback command. Follow the controlled rollback boundary in Chapter 14.

## Appendix B — URLs and Port Matrix

Use Docker service names and container ports for traffic between Compose services. Use the Docker-host address and published port for a browser or physical AP outside the Compose network. Values below are release defaults; `.env` may override published ports. Confirm the effective configuration instead of assuming the defaults:

```powershell
docker compose --env-file .env -f deploy\docker-compose.yml config --quiet
docker compose --env-file .env -f deploy\docker-compose.yml ps
docker compose --env-file .env -f deploy\docker-compose.yml port <service> <container-port>
```

### Operator, browser, and protocol endpoints

| Service / flow | Docker-network endpoint | Default host / external endpoint | Setting / boundary |
| --- | --- | --- | --- |
| Healthcare Lab UI/API | `http://lab-app:5000` | `http://127.0.0.1:5000` | Host port: `LAB_APP_PORT`; HTTP only in this release. |
| Healthcare Lab Order → OIE | `oie:6600` | `<Docker-host-IP>:6600` when an external sender needs the same ingress | Host port: `OIE_ORDER_INGRESS_HOST_PORT`. The in-container sender continues to use `oie:6600`. |
| AP Result → OIE | `oie:6661` | `<Docker-host-IP>:6661` | Host port: `OIE_AP_RESULT_INGRESS_HOST_PORT`; Compose explicitly publishes the default on `0.0.0.0`. |
| OIE Result → Healthcare Lab | `lab-app:6665` | Not published by default | Listener: `HLAB_RESULT_LISTENER_HOST` / `HLAB_RESULT_LISTENER_PORT`; OIE reaches it through the Docker network. The deprecated `OIE_MLLP_RESULT_*` aliases affect this listener only. |
| OIE Order → AP | `<AP-address>:6671` | AP-owned listener, normally `<AP-IP>:6671` | The release bundle does not provide or host-publish an AP service. OIE `expose: 6671` does not create the external listener. |
| OIE HTTP | `http://oie:8080` | `http://127.0.0.1:8080` | Host port: `OIE_HTTP_PORT`. |
| OIE HTTPS | `https://oie:8443` | `https://127.0.0.1:8443` | Host port: `OIE_HTTPS_PORT`; trust behavior depends on the deployed certificate. |
| Medplum FHIR R4 API | `http://medplum:8103/fhir/R4` | `http://127.0.0.1:8103/fhir/R4` | Host port: `MEDPLUM_PORT`. Healthcare Lab sync must use the Docker URL in its persisted server inventory, not the browser/public URL. |
| Medplum web app | `http://medplum-app:3000` | `http://127.0.0.1:3000` | Host port: `MEDPLUM_APP_PORT`; the browser-side API base is `MEDPLUM_PUBLIC_BASE_URL`. |
| dcm4chee web UI | `http://dcm4chee:8080/dcm4chee-arc/ui2` | `http://127.0.0.1:8082/dcm4chee-arc/ui2` | Host port: `DCM4CHEE_HTTP_PORT`; operator link: `DCM4CHEE_WEB_UI_URL`. |
| dcm4chee MWL / DICOMweb | `http://dcm4chee:8080/dcm4chee-arc/aets/WORKLIST/rs` | `http://127.0.0.1:8082/dcm4chee-arc/aets/WORKLIST/rs` | Healthcare Lab uses the Docker address in the release stack; QIDO/WADO/STOW use the configured archive AE path. |
| dcm4chee DIMSE / C-STORE | `dcm4chee:11112` | `<Docker-host-IP>:11112` | Host port: `DCM4CHEE_DICOM_PORT`. MWL called AE is `WORKLIST`; AP result C-STORE uses archive called AE `DCM4CHEE`. |
| dcm4chee HL7 ADT | `dcm4chee:2575` | `<Docker-host-IP>:2575` | Host port: `DCM4CHEE_HL7_PORT`; Healthcare Lab Patient sync inside Compose uses `dcm4chee:2575`. |
| GDT Bridge | `/data/gdt-bridge` in `lab-app` | Folder selected by `GDT_BRIDGE_HOST_PATH` | File exchange only; there is no GDT TCP port. AP and Healthcare Lab must use the same host folder contract. |

### Internal dependency endpoints

These endpoints are for Compose services, not operator or AP access. They are not host-published by the release bundle.

| Dependency | Docker-network endpoint | Consumer |
| --- | --- | --- |
| Medplum PostgreSQL | `medplum-postgres:5432` | Medplum server |
| Medplum Redis | `medplum-redis:6379` | Medplum server |
| dcm4chee PostgreSQL | `dcm4chee-db:5432` | dcm4chee archive |
| dcm4chee LDAP | `ldap:389` | dcm4chee archive |

> **RC release blocker:** the current `.env.example` contains host-facing `127.0.0.1` values for dcm4chee DIMSE, HL7, MWL/DICOMweb, and QIDO/WADO/STOW. If copied unchanged into a Compose deployment, `127.0.0.1` inside `lab-app` identifies the `lab-app` container, not dcm4chee. Until the deployment template is corrected and clean-install verification is repeated, set the runtime targets to `dcm4chee`, `dcm4chee:2575`, `dcm4chee:11112`, `http://dcm4chee:8080/dcm4chee-arc/aets/WORKLIST/rs`, and `http://dcm4chee:8080/dcm4chee-arc/aets/DCM4CHEE/rs` as applicable. Keep only the operator-facing `DCM4CHEE_WEB_UI_URL` on the host URL. Confirm the effective profile in the dcm4chee Console before creating a Patient or Order.

`127.0.0.1` in the table is the local operator URL, not proof that the published socket is loopback-only. Compose publications without an explicit host IP normally listen on all host interfaces, and AP result ingress explicitly binds `0.0.0.0`. Treat every published port as reachable according to the Docker host firewall and network policy. This release provides no application authentication, TLS termination, or public-Internet ingress boundary; keep it on a trusted local machine or isolated internal lab.

## Appendix C — Configuration Reference

Configuration has three different owners:

- `.env` and Compose define images, host publications, mounts, credentials, and process-start environment. Validate them with `docker compose ... config --quiet`, then recreate the affected service.
- Persisted Healthcare Lab settings define runtime profiles such as OIE management/listener intent and the Medplum server inventory. Saving them does not necessarily restart a listener or deploy an OIE Channel.
- External systems own AP endpoints, OAuth clients, OIE users/certificates, and dcm4chee AE configuration. A locally valid value is not proof that the external system accepts it.

`Required` below means required for the named workflow, not for opening Healthcare Lab. `<empty>` means the release template intentionally leaves the value blank. Never place real credentials in documentation, screenshots, tickets, or Git.

### Core, Medplum, OpenEMR, and OIE environment

| Variable(s) | Required | Release default / example | Purpose | Apply action |
| --- | --- | --- | --- | --- |
| `LAB_APP_IMAGE` | Yes; default supplied | `ghcr.io/tzu-huang/healthcare-lab:1.0.0` | Selects the immutable application image. | `pull lab-app`, then recreate `lab-app`; verify image and health. |
| `MEDPLUM_CLIENT_ID`, `MEDPLUM_CLIENT_SECRET` | For authenticated FHIR sync | `<empty>` | OAuth client credentials used by `lab-app`; the secret is sensitive. | Recreate `lab-app`, test OAuth, then Retry the same failed ledger item. |
| `MEDPLUM_SCOPE`, `MEDPLUM_TOKEN_URL` | Only when the OAuth server requires overrides | `<empty>`; blank token URL is derived from FHIR base URL | OAuth scope and token endpoint. | Recreate `lab-app`; test token acquisition. |
| `MEDPLUM_AUTH_GRACE_SECONDS` | No | `300` | Refreshes a cached token before expiry. | Recreate `lab-app`. |
| `MEDPLUM_APP_PORT` | No | `3000` | Host publication for the Medplum web app. | Recreate `medplum-app`; update browser/public URLs if changed. |
| `MEDPLUM_APP_BASE_URL` | No | `http://127.0.0.1:3000/` | Medplum server's configured web-app URL. | Recreate `medplum`; verify redirects. |
| `MEDPLUM_ALLOWED_ORIGINS` | No | `http://127.0.0.1:3000,http://localhost:3000` | Browser origins accepted by Medplum. | Recreate `medplum`; verify CORS from the intended browser origin. |
| `MEDPLUM_PUBLIC_BASE_URL` | No | `http://127.0.0.1:8103/` | Browser-side Medplum API base passed to `medplum-app`; not the `lab-app` sync URL. | Recreate `medplum-app`; verify browser requests. |
| `MEDPLUM_RECAPTCHA_SITE_KEY`, `MEDPLUM_RECAPTCHA_SECRET_KEY` | Environment-dependent | Template site key; secret `<empty>` | Medplum reCAPTCHA settings. The secret is sensitive. | Recreate both `medplum` and `medplum-app`; verify the login flow. |
| `ECG_FILE_BASE_URL` | Only for external artifact links | `https://ecg.example.com` | Base URL used when ECG artifacts are external. | Recreate `lab-app`; verify generated links without exposing PHI. |
| `OPENEMR_DB_HOST`, `OPENEMR_DB_PORT` | Only for the optional OpenEMR source | `<empty>`, `3306` | OpenEMR/MariaDB endpoint; OpenEMR is not included in the release stack. | Recreate `lab-app`; run a bounded connectivity check. |
| `OPENEMR_DB_USER`, `OPENEMR_DB_PASSWORD`, `OPENEMR_DB_NAME` | Only for the optional OpenEMR source | `openemr`, placeholder password, `openemr` | Database credentials and schema; password is sensitive and the template value is not a usable secret. | Recreate `lab-app`; verify least-privilege access. |
| `OPENEMR_GDT_PROCEDURE_CODES` | Only for OpenEMR-filtered GDT workflows | `1001` | Procedure-code allowlist/source filter. | Recreate `lab-app`; verify a synthetic matching and non-matching case. |
| `HLAB_RESULT_LISTENER_HOST`, `HLAB_RESULT_LISTENER_PORT` | For OIE result return | `0.0.0.0`, `6665` | Bind address and container port of the Healthcare Lab MLLP result listener. | Recreate `lab-app`; then confirm or restart listener runtime and OIE destination. Changing this does not publish a host port. |
| `OIE_AP_RESULT_INGRESS_HOST_PORT` | For physical AP result ingress | `6661` | Host-published port mapped to `oie:6661`. | Recreate `oie`; update AP target/firewall and test ACK. |
| `OIE_ORDER_INGRESS_HOST_PORT` | Only for an external Order sender | `6600` | Host-published port mapped to `oie:6600`; internal Healthcare Lab still uses `oie:6600`. | Recreate `oie`; update external sender/firewall. |
| `OIE_MLLP_RESULT_HOST`, `OIE_MLLP_RESULT_PORT` | No; deprecated migration aliases | Commented `0.0.0.0`, `6665` | One-release aliases used only when the corresponding `HLAB_RESULT_LISTENER_*` value is unset. They never control OIE host publication. | Migrate to `HLAB_RESULT_LISTENER_*` and recreate `lab-app`. |

### dcm4chee environment

| Variable(s) | Required | Release default / example | Purpose | Apply action |
| --- | --- | --- | --- | --- |
| `DCM4CHEE_STORAGE_DIR` | Required for archive storage | `/storage/fs1` | LDAP archive storage path and the target initialized by `dcm4chee-storage-init`; it must be inside the archive volume mounted at `/storage`. | Decide before first deployment and do not directly change it after data exists. Persisted LDAP may not rewrite its storage configuration from an environment change, and changing the path does not move old DICOM objects. Any change requires pausing AP, taking a consistent archive-volume/database/LDAP backup, following a supported dcm4chee migration, and verifying it before resuming. |
| `DCM4CHEE_PROFILE_NAME`, `DCM4CHEE_DISPLAY_NAME`, `DCM4CHEE_ENVIRONMENT_NAME` | For DICOM workflow | `local-dcm4chee`, `dcm4chee Local Archive`, `local-docker` | Stable profile identity and operator labels. | Recreate `lab-app`; do not rename a profile casually because mappings use its namespace. |
| `DCM4CHEE_WEB_UI_URL` | For operator link | `http://127.0.0.1:8082/dcm4chee-arc/ui2` | Host/browser URL only. | Recreate `lab-app`; verify the link from the operator host. |
| `DCM4CHEE_DIMSE_HOST`, `DCM4CHEE_DIMSE_PORT` | For DIMSE diagnostics/workflow | Compose default: `dcm4chee`, `11112`; direct-host override: `127.0.0.1`, `11112` | DIMSE destination from `lab-app`. | Correct to the caller-reachable address, recreate `lab-app`, and test AE connectivity. |
| `DCM4CHEE_CALLED_AE_TITLE`, `DCM4CHEE_CALLING_AE_TITLE` | For DIMSE | `DCM4CHEE`, `HEALTHCARE_LAB` | Archive called AE and Healthcare Lab calling AE. | Recreate `lab-app`; coordinate with dcm4chee AE policy. |
| `DCM4CHEE_MWL_AE_TITLE`, `DCM4CHEE_DEFAULT_SCHEDULED_STATION_AE_TITLE` | For MWL | `WORKLIST`, `ECG_AP` | MWL REST AE path and scheduled station/AP identity. | Recreate `lab-app`; verify MWL create/read-back and physical AP query. |
| `DCM4CHEE_HL7_HOST`, `DCM4CHEE_HL7_PORT` | For Patient ADT sync | Compose default: `dcm4chee:2575`; direct-host override: `127.0.0.1:2575` | dcm4chee HL7 listener reached from `lab-app`. | Recreate `lab-app`; verify ADT ACK. See the port-overload blocker below. |
| `DCM4CHEE_HL7_SENDING_APPLICATION`, `DCM4CHEE_HL7_SENDING_FACILITY` | For Patient ADT sync | `HEALTHCARE_LAB`, `LAB_APP` | MSH sender identity. | Recreate `lab-app`; coordinate with receiver routing. |
| `DCM4CHEE_HL7_RECEIVING_APPLICATION`, `DCM4CHEE_HL7_RECEIVING_FACILITY` | For Patient ADT sync | `DCM4CHEE`, `DCM4CHEE` | MSH receiver identity. | Recreate `lab-app`; coordinate with receiver routing. |
| `DCM4CHEE_PATIENT_ASSIGNING_AUTHORITY` | For stable Patient identity | `local-dcm4chee` | Issuer/assigning authority paired with Patient ID. | Recreate `lab-app`; do not change after data exists without a migration plan. |
| `DCM4CHEE_DICOMWEB_BASE_URL` | For MWL REST | Template host URL; Compose-safe value `http://dcm4chee:8080/dcm4chee-arc/aets/WORKLIST/rs` | MWL create/read-back base. | Recreate `lab-app`; verify `/mwlitems` create and query. |
| `DCM4CHEE_QIDO_RS_URL`, `DCM4CHEE_WADO_RS_URL`, `DCM4CHEE_STOW_RS_URL` | For archive query/retrieve/store as used | Template host URLs; Compose-safe archive base `http://dcm4chee:8080/dcm4chee-arc/aets/DCM4CHEE/rs` | Archive AE DICOMweb services. | Recreate `lab-app`; test only the operations required by the workflow. |
| `DCM4CHEE_VIEWER_STUDY_URL_TEMPLATE` | No | `<empty>` | Optional operator viewer link template. | Recreate `lab-app`; verify escaping and a synthetic Study UID. |
| `DCM4CHEE_UID_ROOT` | For generated UIDs | `1.2.826.0.1.3680043.10.543` | UID root used for generated DICOM identifiers. | Recreate `lab-app`; never change for existing mappings without a migration plan. |
| `DCM4CHEE_AUTH_MODE` | No for trusted local profile | `none` | Selects the supported authentication behavior. | Recreate `lab-app`; verify diagnostics and access policy. |
| `DCM4CHEE_TLS_ENABLED`, `DCM4CHEE_TLS_VERIFY` | Environment-dependent | `false`, `true` | Enables TLS behavior and certificate verification. | Recreate `lab-app`; never disable verification merely to hide a certificate error. |
| `DCM4CHEE_USERNAME`, `DCM4CHEE_TOKEN_URL` | When the selected auth mode requires them | `<empty>` | Authentication identity/token endpoint. | Recreate `lab-app`; test authentication without logging tokens. |
| `DCM4CHEE_CERTIFICATE_PATH`, `DCM4CHEE_PRIVATE_KEY_PATH` | When mutual TLS/profile requires them | `<empty>` | Container-readable certificate/key paths; private key is sensitive. | Mount files explicitly, recreate `lab-app`, and verify permissions and TLS. |

> **RC release blockers:** `.env.example` claims its dcm4chee defaults match Compose, but its host-facing `127.0.0.1` values are not valid destinations from `lab-app`; see Appendix B. In addition, `DCM4CHEE_HL7_PORT` currently controls both the `lab-app` internal target port and the dcm4chee host publication. Overriding it for a host-port conflict would also direct `lab-app` to the wrong container port. Do not override it in the current bundle; resolve a conflict through a corrected, separately named host-publication setting and repeat clean-install verification.

### GDT environment

| Variable(s) | Required | Release default / example | Purpose | Apply action |
| --- | --- | --- | --- | --- |
| `GDT_BRIDGE_HOST_PATH` | Only when not using the default folder | `<empty>` → `instance\gdt-bridge` | Host folder mounted to `/data/gdt-bridge`. | Pause AP exchange, verify the absolute host path and folder contract, then recreate `lab-app`. |
| `GDT_BRIDGE_IMPORT_SUCCESS_MODE` | No | `archive` | Successful-file disposition. | Recreate `lab-app`; verify with a synthetic `6310`. |
| `GDT_BRIDGE_FILENAME_PROFILE` | No | `permissive` | Filename validation policy. | Recreate `lab-app`; verify accepted and rejected filenames before tightening. |
| `GDT_BRIDGE_RECEIVER_ID`, `GDT_BRIDGE_SENDER_ID` | Profile-dependent | `<empty>` | Optional GDT party-ID validation/generation values. | Recreate `lab-app`; coordinate exact IDs with AP. |
| `GDT_BRIDGE_WATCH_POLL_SECONDS`, `GDT_BRIDGE_STABLE_SECONDS` | No | `2`, `1` | Watch interval and minimum file-stability window. | Recreate `lab-app`; verify complete files are not read while still being written. |

### Persisted UI settings

| UI area | Fields / default source | Save effect | Additional action required |
| --- | --- | --- | --- |
| OIE Management connection | Base URL, username, replacement password, timeout (UI fallback `10` seconds), TLS verification mode | `Save Connection Settings` persists the profile; an empty password field preserves the configured password. | `Test Connection` uses saved settings only. A certificate or credential failure must be corrected, not bypassed. |
| Healthcare Lab result listener | Host, port, MLLP framing, auto-start | `Save Listener Settings` saves intent only and explicitly does not restart runtime. | Use Start/Stop/Retry as appropriate. If the Compose container port/publication changed, update `.env` and recreate first. |
| Managed OIE Channels | Desired Healthcare Lab-owned source/destination fields for each managed Channel | `Save desired fields` updates desired state only. | Refresh inventory, Preview the single target, review owned-field differences, then Apply. Save/Preview alone does not change OIE. |
| Medplum server inventory | `host=medplum`, `port=8103`, `baseUrl=http://medplum:8103/fhir/R4`, protocol `FHIR`, enabled | Persists the sync target used by Patient/Order workflows. | Test connectivity/OAuth, then Retry the same ledger item. Do not replace it with `MEDPLUM_PUBLIC_BASE_URL`. |
| GDT Console runtime profile | Bridge path/mount visibility, disposition, filename profile, party IDs, watch timing | Displays or updates application runtime intent where the UI permits. | In Docker, changing the host folder still requires `.env` mount correction and `lab-app` recreation; pause AP exchange first. |
| dcm4chee Console profile | Config-derived profile, AEs, HL7/DIMSE/DICOMweb endpoints, auth/TLS diagnostics | Primarily reports the effective profile and workflow state. | Correct `.env`/external AE configuration, recreate `lab-app`, rerun diagnostics, then Retry the same Patient/Order mapping. |

After any change, record the previous value without secrets, the owner, reason, affected services, apply action, verification result, and rollback boundary. A green syntax check is not a connectivity or workflow test.

## Appendix D — Data, Folders, and Backup

Container images are replaceable software; volumes, bind mounts, external systems, and controlled configuration storage hold state. Container recreation must preserve mounted state, but it is not a backup and does not prove that the state can be restored.

### Data ownership and persistence matrix

| Data / Compose storage | Mounted location / authority | Contains | Backup classification and boundary |
| --- | --- | --- | --- |
| `lab-app-instance` | `lab-app:/app/instance` | Healthcare Lab SQLite database (`healthcare-lab.db` by default), local Patients/Orders, protocol ledgers, mappings, attempts, results, OIE settings, and runtime history | Critical for Healthcare Lab recovery. Stop `lab-app` before copying so SQLite is quiescent. |
| GDT host bind mount | `${GDT_BRIDGE_HOST_PATH:-instance\gdt-bridge}` → `lab-app:/data/gdt-bridge` | `6302`/`6310` exchange files, processing/error/archive history, and referenced reports | Critical when GDT is used. AP and Healthcare Lab jointly mutate it; pause both sides before copying. Copy the actual configured absolute host path. |
| `oie-appdata` | `oie:/opt/connect/appdata` | OIE application data, Derby-backed state in the default profile, Channels/configuration, and message/queue evidence as retained by OIE | Critical for OIE recovery. The application-only backup command does not include it; use an OIE-aware, quiesced backup procedure. |
| `medplum-postgres` | `medplum-postgres:/var/lib/postgresql/data` | Canonical Medplum FHIR resources and server database state | Critical for FHIR recovery. Requires a PostgreSQL-consistent backup/restore procedure; filesystem copy while running is not an approved database backup. |
| `medplum-redis` | `medplum-redis:/data` | Medplum Redis runtime/cache state | Operational dependency. Treat according to the pinned Medplum recovery procedure; never infer that deleting it is harmless merely because Redis is often used as a cache. |
| `dcm4chee-archive` | `dcm4chee:/storage` | DICOM object storage | Critical and sensitive. Must be protected together with matching archive database and LDAP configuration. |
| `dcm4chee-db-data` | `dcm4chee-db:/var/lib/postgresql/data` | dcm4chee archive database, metadata, and indexes | Critical. Requires a PostgreSQL-consistent procedure and must remain aligned with DICOM object storage. |
| `dcm4chee-ldap`, `dcm4chee-ldap-config` | LDAP data and `/etc/openldap/slapd.d` | dcm4chee device, AE, connection, and LDAP configuration | Critical for reconstructing the verified archive/AE topology; back up as a coordinated dcm4chee set. |
| `.env` and external secret material | Operator-controlled storage outside images and publishable artifacts | Image selection, ports, endpoints, OAuth/database credentials, certificates, and private-key paths | Required to reconstruct configuration, but highly sensitive. Preserve separately in access-controlled secret storage; do not add it to a normal data backup or Git. |
| Medplum / dcm4chee / AP external state | External authoritative systems | FHIR resources, Studies/instances, AP workflow state, and device-held artifacts | Not owned by the Healthcare Lab SQLite backup. Use each system's supported backup and reconciliation procedure. |

`lab-gdt-bridge` and `dcm4chee-db` are declared named volumes in the current Compose file but are not mounted by any service. They are not the active GDT bridge or dcm4chee database backup source. Do not select a volume by a similar name; confirm effective mounts with `docker inspect` or rendered Compose configuration.

### GDT folder contract

| Folder | Writer / direction | Recovery meaning |
| --- | --- | --- |
| `inbox/` | Healthcare Lab → AP | Generated `6302` Orders waiting for or visible to AP. |
| `outbox/` | AP → Healthcare Lab | Returned `6310` results waiting for import. |
| `processing/` | Healthcare Lab internal | Same-volume claim for an inbound file being processed; investigate before moving anything manually. |
| `archive/` | Healthcare Lab internal | Successfully imported raw files when success mode is `archive`. |
| `error/` | Healthcare Lab internal | Files that failed parsing or persistence and require bounded investigation. |
| `reports/` | AP/shared | Referenced result artifacts such as PDF, XML, or DICOM. A reference in SQLite is not a copy of the artifact. |

Preserve the complete sibling-folder tree rather than only `inbox/` and `outbox/`. Do not replay an archived or processed `6310` to test a restore: durable duplicate prevention for reintroduced content is not yet proven.

### Application-image upgrade backup

This procedure protects Healthcare Lab local state and the GDT bridge for a `lab-app` image upgrade. It is not a full-stack OIE/Medplum/dcm4chee backup.

1. Schedule a maintenance window. Stop new Healthcare Lab operations, let in-flight work finish or record it as incomplete, stop the GDT watcher, and pause all AP reads/writes to the shared folder.
2. Record the timestamp/timezone, release/bundle version, immutable `LAB_APP_IMAGE`, `inspect lab-app`, `config --images`, effective mount source for `/data/gdt-bridge`, and affected workflow states. Store `.env` separately as a secret.
3. For the default `GDT_BRIDGE_HOST_PATH=instance\gdt-bridge` only, run:

   ```powershell
   New-Item -ItemType Directory -Force backup\v1.0.0
   .\deploy\lab.ps1 stop lab-app
   docker compose --env-file .env -f deploy\docker-compose.yml cp lab-app:/app/instance backup\v1.0.0\instance
   Copy-Item -Recurse instance\gdt-bridge backup\v1.0.0\gdt-bridge
   ```

4. If `GDT_BRIDGE_HOST_PATH` is custom, resolve and verify its actual absolute host path, then copy that exact tree instead. Never copy the default folder and report success.
5. Verify the backup while `lab-app` remains stopped: confirm the instance tree contains the expected database, confirm all required GDT sibling folders and artifacts were copied, record file counts/sizes and a controlled integrity manifest, and read representative synthetic files from the backup location.
6. Protect the backup using access control and encryption appropriate to its contents. It may contain PHI, raw protocol payloads, credentials embedded in evidence, private paths, and DICOM metadata. Apply a documented retention and secure-disposal policy.

Do not publish this backup, attach it to a ticket, or use real Patient data as release evidence. A release-evidence bundle should contain only bounded, redacted metadata and synthetic artifacts.

### Full-stack backup and restore boundary

A full-stack recovery point must coordinate at least Healthcare Lab, GDT exchange, OIE, Medplum PostgreSQL, and the dcm4chee database/object-store/LDAP set. Independent copies taken at unrelated times may restore successfully at the filesystem level yet leave missing FHIR references, mismatched DICOM metadata, duplicated messages, or irreconcilable Patient/Order mappings.

The v1.0.0 RC does not provide verified commands for backing up or restoring every named volume, nor a verified named-volume restore command for `lab-app-instance`. Therefore:

- the commands above are not a direct rollback or disaster-recovery SOP;
- do not use `docker compose down -v`, delete/recreate volumes, copy into a live database volume, or merge a backup into a non-empty target;
- do not restore only SQLite when external canonical data changed after the backup, and do not restore only an old image when schema migration may have occurred;
- preserve the failed-upgrade state separately, keep AP exchange quiesced, and use a version-matched controlled restore runbook or release-maintainer direction;
- verify target identity, emptiness, schema/application compatibility, secret/configuration match, ownership/permissions, and recoverability before any destructive restore;
- after restore, verify database integrity, Dashboard health, OIE queues/listeners, GDT disposition, Medplum references, dcm4chee Studies, and one synthetic end-to-end workflow before resuming AP exchange.

Until a restore has been executed in an isolated environment and the recovered workflows have passed reconciliation, the backup is only a backup candidate—not proven recoverability.

## Appendix E — Status and Error Reference

A status belongs to one layer. Do not treat `Created`, HTTP 200, ACK `AA`, `Synced`, and `matched` as interchangeable: they may respectively prove a local write, an HTTP exchange, HL7 application acceptance, external persistence, and result reconciliation. Read the latest attempt, timestamp, identifier/reference, and error evidence with the status.

### Dashboard and runtime states

| Status | Meaning | Operator action |
| --- | --- | --- |
| `Healthy` | The checks executed for that process/application/protocol layer met their current criteria. | Continue to the required workflow check; health is not end-to-end proof. |
| `Degraded` | The service is reachable or partially usable, but an optional/secondary check or expected data condition needs attention. | Expand child checks and read the specific message; do not restart blindly. |
| `Down` | A required check failed, a process is stopped, or the endpoint is unreachable/invalid. | Identify whether the failure is runtime, network, application, or protocol before using the smallest recovery action. |
| `Unknown` | No usable endpoint/result exists, a check has not run, or a dependent check was skipped. | Run checks and correct missing configuration; do not report Unknown as Healthy or Down without evidence. |
| `Running` / `Stopped` | Container or listener runtime state, not workflow health. | A Running process can still be unhealthy; a saved listener configuration can remain Stopped until Start/Retry. |

Dashboard summaries aggregate child states. Always expand the group: one green container count does not prove OIE routing, Medplum OAuth, GDT folder direction, or dcm4chee reconciliation.

### Local Patient, Order, and HL7 v2 states

| Status / ACK | Meaning | Operator action |
| --- | --- | --- |
| `Created` / local record present | Healthcare Lab persisted local intent. It does not prove transmission or external acceptance. | Continue the protocol-specific send/sync/export step and record the local ID. |
| `Ready to send` | An HL7 Order exists locally and is eligible for the send action. | Verify Patient/Order identifiers, OIE destination, and listener readiness; send once. |
| `Accepted` | The latest HL7 Order send received an accepting application ACK and was recorded as accepted. | Preserve ACK/control ID and verify OIE destination/queue evidence; acceptance is not proof that AP completed the examination. |
| `Error` | The send or application processing failed without a more specific projected state. | Inspect bounded error/ACK details, correct the cause, and retry the same Order only when safe. |
| `Rejected` | The receiver rejected the application message, normally corresponding to ACK `AR`. | Correct routing, structure, identifiers, or receiver policy; do not create a replacement Order. |
| `Transport error` | No valid application acceptance was obtained because connection, timeout, framing, or transport failed. | Check endpoint/listener/network and OIE queue state; preserve correlation before retry. |
| ACK `AA` | HL7 application accepted the message. | Correlate `MSH-10`/ACK control ID and verify the intended destination, not merely source receipt. |
| ACK `AE` | Application error: the receiver handled the message but reported an application failure. | Inspect ACK error detail and receiver logs; correct data/configuration before controlled retry. |
| ACK `AR` | Application rejection: the receiver did not accept the message for processing. | Treat as not delivered; correct routing/message/policy before retry. |
| Result `order-matched` | The inbound result correlated to a known local Order. | Verify Patient and identifiers, then inspect the persisted result. |
| Result `patient-only` | The result correlated to a Patient but not a specific Order. | Use stable Order identifiers; do not attach it to the newest Order by guess. |
| Result `unmatched-patient` / unmatched | No safe Patient/Order correlation was found. | Preserve in unmatched results and repair identifiers/mapping; never fabricate a match. |
| Duplicate result ignored | The listener recognized a duplicate result and did not create a second result row. | Keep the ACK/evidence and investigate upstream resend behavior; do not purge the original. |

### FHIR synchronization states

| Raw/UI status | Meaning | Operator action |
| --- | --- | --- |
| `Pending sync` | Local Patient/ServiceRequest intent exists but external synchronization has not completed. | Confirm persisted `http://medplum:8103/fhir/R4`, OAuth, and connectivity, then Retry the same record. |
| `Syncing` | A synchronization attempt is in progress or recorded as active. | Wait for the bounded operation deadline; if stale, inspect the latest attempt before retrying. |
| `Synced` | Medplum accepted/persisted the resource and Healthcare Lab holds a valid `Patient/<id>` or `ServiceRequest/<id>` reference. | Read back the live resource and continue; keep local ledger/reference correlation. |
| `Sync failed` | Local intent remains, but the latest Medplum attempt failed. | Inspect HTTP status, safe error summary, and `OperationOutcome`; fix configuration/data and Retry the same ledger item. |
| `Local only` | UI has local context without a usable live Medplum reference/result. | Do not represent it as Medplum-backed; synchronize or select a valid synced Patient. |
| `No reports` | Medplum query succeeded and returned no matching DiagnosticReports. | This is a valid empty result, not an outage. Confirm search identifiers and wait/requery as appropriate. |

Never create a second Patient or Order to clear `Pending sync` or `Sync failed`. A failed retry must preserve deterministic identifiers and attempt history.

### GDT states and file disposition

| State | Meaning | Operator action |
| --- | --- | --- |
| Order `Created` | Local `6302` intent exists; the exchange file may not yet have been written or consumed. | Use `Write GDT-OUT` once and verify the atomic file in `inbox/`. |
| Order `Result received` | A `6310` was imported and correlated to the Order. | Inspect raw/canonical result, artifacts, and match evidence. |
| Bridge file `pending` | A stable candidate is visible in AP's `outbox/` and can be imported. | Validate filename/profile and import once, manually or through the watcher. |
| Parse `accepted` | The GDT message passed parsing/validation sufficiently to be persisted. | Continue to match/artifact review; accepted does not itself mean Order matched. |
| Match `order-matched` | `6330`/other supported identifiers correlated to a local GDT Order. | Verify MRN/Patient context and result content. |
| Match `unmatched` | No unique local GDT Order correlation was found. | Preserve the result and identifiers; correct the mapping, not the raw evidence. |
| Success mode `archive` | The processed source file moved to collision-safe `archive/`. | Retain according to policy; do not copy it back to `outbox/`. |
| Success mode `delete` | The processed exchange file was deleted after successful persistence. | Confirm SQLite result/evidence before relying on this mode; raw source is no longer in the bridge. |
| `processing/` | Healthcare Lab claimed the inbound file with a same-volume rename. | If stale, preserve state and investigate watcher/import failure before manual movement. |
| `error/` | Parse or persistence failed and the file was moved aside when possible. | Inspect bounded diagnostics and raw synthetic data; correct the cause before a controlled re-import procedure. |
| Artifact `available` | A referenced local path was found. | Verify it is the intended artifact; availability is not content validation. |
| Artifact `reference-only` | A non-local or HTTP(S) reference is retained without proving target content. | Use `Open` only for safe URLs or `Copy` the reference; apply access controls. |
| Artifact `warning` / `missing-reference` | Target cannot be found/verified or the reference is empty. | Preserve the warning and correct artifact delivery; other parseable result content may remain valid. |

The current RC has not proved durable idempotency when an already processed `6310` is reintroduced. File disposition prevents the original file from being rescanned; it is not a guarantee against operator/device replay.

### dcm4chee Patient and MWL states

| Raw status | UI display | Meaning and action |
| --- | --- | --- |
| Patient `Pending sync` | `Pending sync` | Local Patient exists but ADT acceptance is incomplete; verify `dcm4chee:2575` and Retry the same Patient. |
| Patient `Synced` | `Synced` | ADT received ACK `AA`; continue to MWL while retaining Patient ID/issuer. |
| Patient `Sync failed` | `Sync failed` | ADT did not complete successfully; inspect ACK/transport and fix before MWL creation. |
| MWL `Pending sync` | `Retry needed` when retryable, otherwise `Pending` | Create/read-back is incomplete; query first, then retry only if no existing MWL item is found. |
| MWL `Created` | `Synced` | MWL create/read-back mapping succeeded. This does not prove physical AP query or examination completion. |
| MWL `Sync failed` | `Retry needed` when retryable, otherwise `Failed` | Latest create/read-back failed; inspect error type/HTTP response and query before retrying to avoid duplicate POST. |
| MWL `Patient missing` | `Failed` | dcm4chee could not resolve the Patient required by MWL. | Repair and verify Patient ADT first; do not bypass the precondition. |

MWL verification is separate from mapping status:

| Verification status | Meaning | Operator action |
| --- | --- | --- |
| `not_verified` | No completed query/read-back proof exists. | Query using stable identifiers. |
| `verified` | Exactly the expected MWL item was read back. | Record identifiers and continue to physical AP verification. |
| `verification_failed` | Read-back did not prove the expected item or the query failed. | Inspect response/error and mapping; do not issue an unconditional create. |
| `verification_ambiguous` | More than one candidate or insufficiently unique evidence exists. | Resolve identifiers/duplicates; never choose the newest candidate by guess. |

### dcm4chee result reconciliation states

| Status | Meaning | Operator action |
| --- | --- | --- |
| `matched` | Study/result identifiers safely correlate to the selected Patient and Order. | Verify Study/Series/SOP hierarchy and preserve evidence. |
| `no_result` | QIDO completed successfully but returned no matching result. | Valid empty state; wait/requery and confirm identifiers. |
| `ambiguous` | Multiple candidates prevent a safe unique match. | Compare Patient ID/issuer, Accession, Study UID, RP/SPS; do not guess. |
| `duplicate` | The same Study/SOP/result was already processed or duplicated in discovery. | Inspect AP/archive resend history; do not create another mapping. |
| `wrong_patient` | Candidate identifiers conflict with the selected Patient. | Quarantine from automatic matching and correct upstream identity/mapping. |
| `missing_accession` | Required Accession correlation is absent. | Repair AP/MWL/DICOM identifiers; do not match only by time. |
| `unlinked` | Result exists but is not linked to a local Order. | Preserve it and reconcile using stable identifiers. |
| `query_failed` | Archive query failed; this is not an empty result. | Correct endpoint/auth/TLS/network and repeat the query without recreating the Order. |

### OIE management error categories

| Category | Meaning / first action |
| --- | --- |
| `authentication`, `unauthenticated` | Credentials/session missing or rejected; correct the saved account/session without exposing secrets. |
| `permission` | Account authenticated but lacks required authority; grant only the necessary OIE permission. |
| `tls` | Certificate verification or TLS negotiation failed; correct trust/certificate/hostname, never silently disable verification. |
| `connection`, `timeout` | Endpoint unreachable or deadline expired; check address, port, firewall, runtime, and bounded timeout. |
| `revision-conflict` | Channel changed after Preview or expected revision. Refresh inventory and request a fresh Preview; do not force stale mutation. |
| `validation` | Local request/settings/owned fields are invalid. Correct the input before contacting OIE again. |
| `unsupported-version` | OIE version is outside the verified `4.5.2` contract. Stop mutation and verify compatibility. |
| `server` | OIE returned a server-side failure. Preserve safe status/timing and inspect OIE logs. |
| `unexpected-response` | Response was empty, malformed, oversized, or structurally unexpected. Preserve a bounded redacted summary; do not log the entire body. |

For every failure, preserve the same local record, correlation identifiers, latest-attempt time, safe error category, and external reference. Retry only after correcting the cause and confirming the state is retryable; never delete, purge, or fabricate a green status to close an incident.

## Appendix F — Test Data and Workflow Checklists

Use only synthetic Patients created for the isolated lab. Never copy a real person's name, MRN, date of birth, address, phone, email, ECG, FHIR resource, HL7/GDT payload, or DICOM metadata into a verification run. A successful simulated workflow proves the simulator/mapping path only; label it `simulated` and do not present it as physical-AP proof.

### Reusable synthetic dataset

Reserve a fresh six-digit run range before testing. The examples below are syntactically valid but must be changed if they already exist. Create a separate local Patient for each mode because the Patient selector and external identifiers are mode-specific.

| Workflow | Example MRN | Synthetic name | DOB / sex | ECG definition | Additional values |
| --- | --- | --- | --- | --- | --- |
| HL7 v2 / OIE | `MRN-910101` | `Avery Testhl7` | `19850101` / `F` | `ECG12`, alternate `93000`, priority `R` | Patient class `O`; synthetic location/provider/account values |
| FHIR / Medplum | `MRN-910102` | `Blake Testfhir` | `19850202` / `M` | `ECG12 / 12 Lead ECG`; FHIR status `active`, intent `order` | Synthetic email/address if those fields are exercised |
| GDT 2.1 | `MRN-910103` | `Casey Testgdt` | `19850303` / `O` | `8402=EKG01` | Allow generated GDT Patient/Order numbers; record field `6330` |
| DICOM / dcm4chee | `MRN-910104` | `Devon Testdicom` | `19850404` / `U` | `ECG12`, priority `R` | Patient class `O`; issuer/profile `local-dcm4chee`; station AE `ECG_AP` |

Use a requested/scheduled time generated during the run in `YYYYMMDDHHMMSS` form. Do not reuse an `MSH-10`, local Order number, GDT filename/correlation identifier, Accession Number, Study Instance UID, Requested Procedure ID, or Scheduled Procedure Step ID from a previous run. Keep MRNs stable within one run; do not repair a failure by creating another Patient.

### Verification record template

Create one record per workflow and one row per attempt. Use Taipei time with an explicit `+08:00` offset and include UTC when evidence comes from systems using UTC.

| Field | Required content |
| --- | --- |
| Run identity | Unique run ID, test type (`live-physical-AP`, `live-service`, or `simulated`), release/tag/digest, bundle revision, date, tester |
| Environment | Host OS/architecture, Docker/Compose versions, effective image list, relevant profile/server/Channel revision; no secrets |
| Patient | Synthetic name, MRN, local Patient ID, mode, external Patient reference/ID and issuer |
| Order | Local Order ID, protocol, requested time, code, and protocol identifiers: placer/filler, ServiceRequest, `6330`, Accession/Study/RP/SPS as applicable |
| Result | Result/message ID, DiagnosticReport/Observation reference, GDT source filename/artifact reference, or Study/Series/SOP UIDs as applicable |
| Attempts | Start/end timestamps, action, pre-state, post-state, HTTP/ACK/status, safe error category, and whether Retry was used |
| Evidence | Bounded screenshots/log excerpts, query/read-back proof, file disposition, queue/listener state, and evidence location/checksum; redact secrets/private paths |
| Outcome | `PASS`, `FAIL`, or `BLOCKED`; last successful step, unmet criterion, remaining limitation, cleanup/retention decision |

`PASS` requires every mandatory criterion for that test type. `FAIL` means an executed criterion produced the wrong result. `BLOCKED` means a required external dependency or authorized action was unavailable; it is not a pass. Never change a status, delete a record, purge a queue, replay a processed file, or manufacture evidence to obtain PASS.

### Common preflight and completion checklist

| Check | Pass criterion |
| --- | --- |
| Scope and authority | Test type, systems/AP in scope, allowed mutations, maintenance window, and stop condition are recorded. |
| Synthetic data | All Patient/result content is demonstrably synthetic and the MRNs are unused in this environment. |
| Release identity | `inspect lab-app` and `config --images` match the intended immutable release matrix. |
| Runtime | Required containers/listeners are Running and Dashboard child checks have been inspected. |
| Configuration | Effective internal/external endpoints, credentials-present state, profile/AE/Channel identifiers, and GDT mount are verified without recording secrets. |
| Evidence safety | Capture location is access-controlled; PHI, tokens, passwords, cookies, Authorization headers, query strings, and private host paths will be redacted. |
| Correlation | Fresh Patient/Order/message/file/Study identifiers are recorded before transmission. |
| Completion | Final state is read back from the authoritative system and reconciled to exactly one local Patient/Order; no unexplained queue/file/result remains. |

After each run, rerun the relevant Dashboard check and record whether AP exchange/listeners/watchers were returned to their intended state. Preserve failed evidence according to policy; cleanup must not destroy the information required to diagnose the failure.

### HL7 v2 / OIE checklist

| Step | Pass criterion / evidence |
| --- | --- |
| Create | HL7-mode Patient and Order are created once; Order is `Ready to send`; preview contains the selected MRN, visit/account, `ECG12`/`93000`, and a fresh `MSH-10`. |
| Route readiness | OIE management connection and result listener are healthy; managed Channel destination is `oie:6600` for the in-container sender path and the AP target is the intended reachable listener. |
| Send ORM | One Send action returns ACK `AA`; local Order becomes `Accepted`; OIE shows one source receipt and one successful destination send for the same `MSH-10`, with no unexplained error/queued duplicate. |
| AP proof | For `live-physical-AP`, AP records receipt of the same Patient/Order identifiers. A simulator ACK alone cannot satisfy this criterion. |
| Return ORU | AP sends one valid synthetic ORU through `<Docker-host-IP>:6661`; OIE forwards it to `lab-app:6665`; Healthcare Lab returns ACK and persists one result. |
| Reconcile | Result is `order-matched` to the intended MRN/Order; raw result and control identifiers agree; unmatched and duplicate lists contain no unexplained new item. |
| Recovery check | If testing outage recovery, preserve queued/error state, correct the cause, wait to a recorded deadline, and prove normal retry drains the queue without manual resend or duplicate result. |

### FHIR / Medplum checklist

| Step | Pass criterion / evidence |
| --- | --- |
| Preconditions | Persisted server inventory is `host=medplum`, `port=8103`, `baseUrl=http://medplum:8103/fhir/R4`; OAuth is configured without exposing credentials. |
| Create Patient | FHIR-mode Patient is created once, reaches `Synced`, and has one live `Patient/<id>` reference that reads back with the expected synthetic identifier. |
| Create Order | The synced Patient is selected; one ServiceRequest is created with `ECG12`, `active`, `order`, priority/time/requester, and a deterministic identifier. |
| Verify Order | Local status is `Synced`; one live `ServiceRequest/<id>` reads back from Medplum and references the intended Patient. |
| Discover result | Patient-Centered Console queries live resources. A matching DiagnosticReport is correctly linked, or a successful empty Bundle is recorded as `No reports`, not an outage. |
| Recovery check | Induce only an approved safe failure, preserve `Sync failed`/`OperationOutcome`, correct the cause, and Retry the same ledger item to `Synced` without a duplicate Patient/ServiceRequest. |

### GDT 2.1 checklist

| Step | Pass criterion / evidence |
| --- | --- |
| Folder readiness | Effective `/data/gdt-bridge` mount is writable and contains sibling `inbox/`, `outbox/`, `processing/`, `archive/`, `error/`, and `reports/`; AP uses the same host folder and agreed direction. |
| Create | GDT-mode Patient and one Order are created; raw `6302` includes `8000=6302`, `9218=02.10`, the expected `3000`, fresh `6330`, and `8402=EKG01`. |
| Export | `Write GDT-OUT` is selected once; a complete collision-safe file appears atomically in `inbox/`; record filename, size, timestamp, and checksum without replaying it. |
| AP proof | For a physical-AP run, AP reads that exact file and returns a stable valid `6310` to `outbox/`. A hand-created file is acceptable only for a separately labelled simulated test using a validated fixture. |
| Import | Manual import or watcher claims the file through `processing/`, parse status is `accepted`, match is `order-matched`, and Order becomes `Result received`. |
| Result/artifacts | Raw/canonical result, measurements, `6330`, and artifacts agree; each artifact is `available`, expected `reference-only`, or has an explained warning. |
| Disposition | Source moves to `archive/` or is deleted according to configured success mode; parse/persist failure moves to `error/` when possible and is recorded as FAIL. |
| Replay boundary | No processed `6310` is copied back to `outbox/`. Durable replay protection remains unverified and cannot be marked PASS. |

### DICOM / dcm4chee checklist

| Step | Pass criterion / evidence |
| --- | --- |
| Profile | Diagnostics confirm intended profile, `dcm4chee:2575`, MWL REST `WORKLIST`, archive AE `DCM4CHEE`, calling AE `HEALTHCARE_LAB`, station/AP AE `ECG_AP`, and caller-appropriate host/internal URLs. |
| Create Patient | DICOM-mode Patient is created once; ADT receives ACK `AA`; status is `Synced`; Patient ID and issuer read back consistently. |
| Create MWL | One DICOM MWL Order is created with recorded Accession, Study UID, Requested Procedure ID, SPS ID, Patient ID/issuer, code, and scheduled time. |
| Verify MWL | REST create succeeds and a query/read-back returns exactly the expected item; mapping displays `Synced` and verification is `verified`, not ambiguous. |
| Physical AP proof | AP queries MWL using its real network path/AE, selects the intended item, performs the synthetic examination, and C-STOREs instances to called AE `DCM4CHEE`. Simulated return must be labelled and cannot satisfy this row. |
| Discover | QIDO finds the expected Study; Study/Series/SOP UIDs, Patient ID/issuer, Accession, modality, instance count, and times agree. WADO/viewer actions reference the same Study. |
| Reconcile | Result is `matched` to exactly one intended local Order; there is no unexplained `wrong_patient`, `missing_accession`, `ambiguous`, `duplicate`, or `unlinked` row. |
| Empty/failure distinction | An empty successful query records `no_result`; connectivity/auth/TLS failure records `query_failed`. Neither condition causes a replacement Order. |

### Negative and recovery coverage

Run negative tests only in an isolated environment and only when the failure is reversible without destructive cleanup.

| Case | Required observation |
| --- | --- |
| Duplicate MRN | Create is rejected and no second Patient row appears. |
| Invalid Patient/Order input | Preview/Create reports validation failure and sends no external message/resource/file. |
| HL7 `AE`/`AR` or transport failure | Exact layer and correlation are preserved; retry occurs only after correction. |
| FHIR OAuth/configuration failure | Local ledger remains with safe error/OperationOutcome; corrected Retry creates no duplicate resource. |
| GDT invalid/unstable file | Watcher does not read a changing/temp file; invalid stable input is isolated with diagnostics and does not block other files. |
| DICOM Patient missing/ambiguous query | MWL/result is not guessed or blindly recreated; identifiers and retryability are reported correctly. |

A release claim must list omitted or blocked cases. Automated repository tests, simulated AP tests, browser checks, and physical-AP verification are separate evidence classes; none silently substitutes for another.

## Appendix G — Version Compatibility

Compatibility is defined by the complete release matrix, not by one component version. Replacing any pinned image, changing platform/architecture, or connecting an unverified AP/device creates a deployment outside the verified v1.0.0 RC matrix until the relevant checks in Appendix F pass.

### Current release gate

The handbook is structurally complete, but the v1.0.0 operational release gate remains **BLOCKED**. A release owner must close the items below or explicitly narrow and approve the release claim; documentation must not silently turn an unverified item into supported behavior.

| Gate area | Open release evidence / defect |
| --- | --- |
| Publication and clean installation | Create and verify the `v1.0.0` tag, public unauthenticated pull, immutable digest, first-time initialization, and clean full-stack installation on an equivalent `linux/amd64` host. |
| Deployment configuration | Correct the host-facing dcm4chee values in `.env.example`; separate the dcm4chee host-published HL7 port from the `lab-app` internal target; repeat clean-install and ADT/MWL/DICOMweb verification. |
| GDT operator workflow | Fix `[object Object]` measurement rendering, demonstrate durable duplicate prevention for reintroduced 6310 content, expose the documented result details, and browser-reverify the final behavior. |
| Recovery | Provide and successfully exercise a controlled named-volume restore runbook, including `lab-app-instance`; current backup candidates do not prove recoverability. |
| Support declaration and architecture | Publish minimum CPU/memory/storage and supported browser versions; replace the text topology with the final verified deployment diagram. |
| External/control coverage | Complete or explicitly exclude the remaining physical-AP four-protocol E2E cases and isolated Dashboard Stop/Restart/Enable/Disable/degraded/down/history behavior. |

### Evidence levels

| Level | Meaning |
| --- | --- |
| RC-verified | Exercised in the recorded 2026-07-22 RC host/browser/workflow pass or container verification described in this handbook. |
| Contract-tested | Enforced by repository tests or static release/Compose contracts, but not necessarily exercised against every external implementation. |
| Digest-pinned | Exact image content is fixed by repository digest; no additional upstream version claim is made unless a tag is also present. |
| Unverified | Not covered by completed release evidence. It must not be described as supported merely because configuration fields exist. |

### Application and container matrix

| Component | v1.0.0 RC contract | Evidence / compatibility boundary |
| --- | --- | --- |
| Healthcare Lab | `ghcr.io/tzu-huang/healthcare-lab:1.0.0` | Immutable release tag; public pull/digest and final clean-install publication remain part of the release gate. |
| Application runtime | `python:3.11-slim`; Flask `>=3.0,<4.0`; Gunicorn `>=23.0,<24.0`; python-dotenv `>=1.0,<2.0`; PyMySQL `>=1.1,<2.0` | Built into the application image. Operators must not install host Python packages into the released container. One Gunicorn worker is required by current single-process listener ownership. |
| OIE | `nextgenhealthcare/connect:4.5.2@sha256:4afa295cfe7c5ffd596efee69594157fea87202e33d66bb4a98a52db4598f836` | RC/contract target is OIE `4.5.2`. Managed Channel APIs/templates are version-sensitive; another OIE version requires management, Channel preview/apply, queue, ACK, and E2E re-verification. |
| Medplum server | `medplum/medplum-server@sha256:4d2c8e926fe536176a88a7e24555f97f92226e39f171bd0b5f0c7f667d0bf9f0` | Exact content is digest-pinned. The repository does not provide a reliable human-readable Medplum release version; do not invent one. |
| Medplum app | `medplum/medplum-app@sha256:79f162f7124a8932c2a76fc2c7c72df4b080d5fef43496c64bc34ad68e65ca56` | Must stay paired with the pinned server/public-base configuration unless compatibility is reverified. |
| Medplum PostgreSQL | `postgres:16-alpine@sha256:e013e867e712fec275706a6c51c966f0bb0c93cfa8f51000f85a15f9865a28cb` | PostgreSQL major `16`, exact image digest. Database downgrade/restore compatibility is not implied by an image rollback. |
| Medplum Redis | `redis:7-alpine@sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99` | Redis major `7`, exact image digest; use with the pinned Medplum matrix. |
| dcm4chee database | `dcm4che/postgres-dcm4chee:16.13-35@sha256:1fced918fa507a133ec98db6ad2af92be2db0399c4061d5d59a4405ac445cd70` | Version/tag and digest are paired with archive/LDAP images; independent replacement is unverified. |
| dcm4chee LDAP | `dcm4che/slapd-dcm4chee:2.6.13-35.0@sha256:ca45eaf70d92c4008612ab345a566e06c13b553b079ccf6c652ceda4c9a98b98` | Must remain aligned with the archive configuration and AE topology. |
| dcm4chee archive | `dcm4che/dcm4chee-arc-psql:5.35.0@sha256:20a195c0c53336e1d0c7bdc30536d46611a939f0a2e25dec3318c8d99d7fba29` | dcm4chee archive `5.35.0`, exact digest. Reverify ADT, MWL REST, DIMSE C-STORE, QIDO/WADO, and reconciliation after any change. |

Moving tags `1`, `1.0`, `latest`, and `edge` are not acceptable substitutes for the immutable `1.0.0` release tag in a reproducible verification or rollback record. A `sha-<commit>` image is traceable development evidence, not automatically a stable release.

### Protocol compatibility matrix

| Protocol / surface | v1.0.0 contract | Verified scope and limitations |
| --- | --- | --- |
| HL7 v2 | HL7 `2.5.1`; ADT A04, ORM O01, ORU R01/W01 as implemented; MLLP | Contract/live evidence covers current payloads, ACK `AA/AE/AR`, OIE routing, result listener, and correlation. This is not a general claim for every HL7 profile, optional segment, encoding, or receiver policy. |
| FHIR | FHIR R4 REST; Patient, ServiceRequest, DiagnosticReport, Observation, and required supporting references | Verified against the pinned Medplum images and OAuth flow. Vendor-specific R4 behavior, unsupported search parameters, other FHIR versions, subscriptions, bulk data, and arbitrary resources are outside the claim. |
| GDT | GDT `02.10` / GDT 2.1; `6301`, `6302`, `6310`; ECG test `8402=EKG01` | Contract covers the documented byte-counted subset, folder exchange, matching, and artifact references. It is not a claim of full GDT implementation or compatibility with every filename/device profile. Physical-QHAP version and durable replay protection remain unverified. |
| DICOM / DIMSE | Patient identity/ADT integration, MWL workflow, AP C-STORE to archive AE `DCM4CHEE` | Verified contract covers the documented AEs/identifiers and current dcm4chee matrix. No general DICOM device conformance statement, TLS profile, transfer-syntax matrix, or modality-vendor certification is provided. |
| DICOMweb | MWL REST under `WORKLIST`; QIDO-RS/WADO-RS/STOW-RS archive surface under `DCM4CHEE` | Current paths and reconciliation are version/profile-specific. Browser viewer availability does not prove QIDO/WADO/STOW or physical DIMSE behavior. |
| OpenEMR source | Optional MariaDB procedure-order source | Not provisioned by default Compose and not part of the final v1.0.0 integrated compatibility claim unless separately verified. |
| AP / QHAP | HL7, GDT, or DICOM peer depending on workflow | Product/version, supported profiles, network behavior, and physical-device E2E remain unverified unless a release evidence record explicitly identifies and proves them. |

### Host and client matrix

| Area | Verified / supported boundary | Not yet verified or supported |
| --- | --- | --- |
| Container platform | Release images and integrated stack target `linux/amd64`. | ARM/`arm64`, Windows containers, non-Linux container mode. |
| Recorded RC host | Windows 11 64-bit; Windows PowerShell 5.1; Docker Desktop 4.75.0; Docker Engine 29.5.2; Docker Compose v5.1.3; Docker VM 16 CPUs/8 GB RAM. | These are the recorded environment, not declared minimum hardware/software versions. |
| Equivalent Linux host | Docker Compose on a trusted local/internal `linux/amd64` host is the intended support boundary. | Final clean-install verification on an equivalent standalone Linux host remains pending. |
| Browser | The 2026-07-22 RC browser pass confirms the captured UI behavior in its test environment. | Minimum/supported Chrome, Edge, Firefox, Safari, and mobile browser versions have not been published. |
| Deployment topology | Trusted local machine or isolated internal lab; single `lab-app` replica/worker ownership model. | Public Internet, regulated production healthcare, multi-replica/multi-worker listener ownership, HA, public ingress, built-in authentication, or TLS termination. |

Recorded CPU/memory values prove one successful environment only. Minimum CPU, memory, storage, retention capacity, and performance/concurrency limits remain unverified and must not be inferred from that host.

### Compatibility-change rule

Before changing any component or protocol peer:

1. Record the current complete image/digest matrix, schema/data backup boundary, AP/device version, profile/AE/Channel configuration, and successful baseline workflow.
2. Change one compatibility dimension at a time. A digest change under the same tag is still a component change.
3. Recreate the affected service and run configuration, health, persistence, negative/retry, and required physical/simulated workflow checks from Appendix F.
4. Compare identifiers, payloads, status transitions, error categories, external read-back, and result reconciliation with the baseline.
5. Mark the combination verified only when all required evidence passes. Otherwise restore through a controlled, version-compatible runbook; do not call an image-only switch a rollback.

The matrix is a tested combination, not a semantic-version promise between independently upgraded components.

## Appendix H — Glossary

Terms use the meaning defined here when the same word could refer to several layers. Capitalized Patient and Order normally refer to workflow records/resources; lowercase patient/order may describe the general concept.

| Term | Meaning in this handbook |
| --- | --- |
| ACK | HL7 acknowledgement returned by the receiving application. `AA` means accepted, `AE` application error, and `AR` application rejection. An ACK proves the receiver's response at that hop, not completion of the clinical workflow. |
| Accession Number | DICOM/RIS-style Order identifier used to correlate MWL and Study results. It must remain stable for one Order and must not be replaced by “the newest Study.” |
| ADT | HL7 Admit/Discharge/Transfer message family. Healthcare Lab uses an ADT Patient message for the documented Patient registration/synchronization path. |
| AE Title | Application Entity Title: the configured name of a DICOM application endpoint. In this stack, `DCM4CHEE`, `WORKLIST`, `HEALTHCARE_LAB`, and `ECG_AP` have distinct roles. |
| AP / QHAP | Application partner (QHeart-AP/QHAP) that obtains ECG Orders and returns results through the configured HL7, GDT, or DICOM path. AP product/version compatibility is not implied unless evidence identifies it. |
| AP exchange | All AP reads/writes or network sends/receives for the tested workflow. “Pause AP exchange” includes the GDT shared folder, not only Healthcare Lab UI activity. |
| Assigning authority / issuer | Namespace paired with a Patient identifier. The same Patient ID under a different issuer may identify a different Patient. |
| Backup candidate | A copied data set whose contents were checked but whose restore/reconciliation has not been successfully exercised. It is not proven recoverability. |
| Bind mount | A host file/folder mounted into a container, such as `GDT_BRIDGE_HOST_PATH` at `/data/gdt-bridge`. Its data is owned at the actual host path, not by a similarly named Docker volume. |
| Canonical data | Normalized workflow representation used for consistent processing. It does not replace preserved raw protocol evidence or the external system's authoritative resource/object. |
| C-STORE | DICOM DIMSE service used by AP to send DICOM instances to archive called AE `DCM4CHEE`. It is different from DICOMweb STOW-RS. |
| Container | One runtime instance of an image. Recreating a container replaces that runtime instance while preserving correctly mounted volumes/bind mounts. |
| Correlation | Linking messages/resources/files/Studies to the intended Patient and Order using stable identifiers. Time proximity or “latest record” is not safe correlation. |
| DICOM | Standard and data model used for medical imaging objects and related workflows. This handbook covers a bounded Patient/MWL/Study-result integration, not full DICOM conformance. |
| DICOMweb | HTTP REST services for DICOM workflows, including QIDO-RS, WADO-RS, and STOW-RS. It is separate from DIMSE networking. |
| DiagnosticReport | FHIR resource that represents a diagnostic report and may reference Observations and the originating ServiceRequest. |
| Digest | Content-addressed image identifier such as `sha256:...`. A pinned digest fixes exact image content even when a human-readable version tag is absent. |
| DIMSE | DICOM Message Service Element protocol family, including MWL query and C-STORE operations over DICOM networking. |
| Docker Compose | Tool/model that defines and operates the multi-container stack, networks, publications, and mounts. Compose syntax success is not workflow verification. |
| Endpoint | A reachable address plus protocol context. Browser URL, Docker service endpoint, host-published port, and physical-device target may be different endpoints for the same service. |
| External reference | Identifier or URL/path pointing to data owned outside the local SQLite record, such as a Medplum resource, GDT report, or DICOM Study. A reference is not necessarily a local copy. |
| FHIR | Fast Healthcare Interoperability Resources. This release uses the documented FHIR R4 REST subset with Medplum. |
| GDT | Geräte-Datenträger, a file-based healthcare/device exchange protocol. The release implements the documented GDT 2.1 (`02.10`) subset and folder contract. |
| Health check | A bounded probe of a process, application, or protocol layer. Healthy does not automatically mean end-to-end workflow success. |
| HL7 v2 | Delimited healthcare messaging standard. The current contract uses documented HL7 v2.5.1 ADT/ORM/ORU payloads over MLLP. |
| Immutable tag | Release tag that must not move to different content, such as `1.0.0`. Moving aliases such as `latest` are not immutable rollback evidence. |
| Instance / Series / Study | DICOM hierarchy: a Study contains Series, and a Series contains SOP Instances. All relevant UIDs must agree during reconciliation. |
| Ledger | Persisted local history of workflow intent, identifiers, attempts, states, errors, and external references. It supports retry/reconciliation but is not always the canonical clinical data store. |
| Live | Evidence produced by an actual configured external service or physical AP path during the recorded run. It must identify which external hop was genuinely exercised. |
| Local intent | Patient/Order/workflow record preserved in Healthcare Lab before or independently of successful external synchronization. `Created` or `Pending sync` may represent local intent only. |
| MLLP | Minimal Lower Layer Protocol framing commonly used to transport HL7 v2 over TCP. TCP reachability alone does not prove valid MLLP or application ACK. |
| MRN | Medical Record Number used as the canonical local Patient identifier. Manual test MRNs must use `MRN-` plus at least six digits and must remain synthetic. |
| MWL | DICOM Modality Worklist. Healthcare Lab creates/reads the documented worklist item; physical AP query remains a separate verification step. |
| Named volume | Docker-managed persistent storage referenced by name, such as `lab-app-instance`. A declared but unmounted volume is not an active data source. |
| OAuth 2.0 | Authorization framework used for `lab-app` server-to-server Medplum access. Client secrets and tokens must never appear in shared evidence. |
| Observation | FHIR resource containing a measurement or observation that may be referenced by a DiagnosticReport. |
| OIE | Open Integration Engine (the NextGen Connect-based integration engine in this release) used to receive, route, queue, and forward HL7 messages. |
| OperationOutcome | FHIR resource describing issues returned by a FHIR operation. Preserve only the bounded, redacted diagnostic projection needed for investigation. |
| ORM | HL7 Order message family. The documented ECG Order workflow uses ORM O01. |
| ORU | HL7 Observation Result message family. The documented result paths include ORU R01/W01 profiles as implemented. |
| Patient | Local workflow record or FHIR Patient resource representing the synthetic person under test. Mode-specific local Patients are not interchangeable. |
| PHI | Protected Health Information. Raw messages, FHIR JSON, GDT files, DICOM metadata, screenshots, logs, URLs, and filenames may contain PHI. |
| Preview | Read-only rendering/validation of intended payload or configuration change. Preview does not create/send data or Apply an OIE Channel mutation. |
| QIDO-RS | DICOMweb query service used to discover Studies/Series/Instances. A successful empty query is `no_result`; a failed query is `query_failed`. |
| Quiesced | State in which new writes/exchange are paused and in-flight work is finished or explicitly recorded, allowing a consistent maintenance operation. |
| Reconciliation | Comparing local intent/mappings with authoritative external data and linking a result to exactly the intended Patient/Order. |
| Recreate | Replace a container from current image/Compose/environment using `up -d --force-recreate`. It is not merely restarting a process inside the same container. |
| Requested Procedure / RP | DICOM identifier/concept for the requested procedure associated with an Order. It is one of the stable MWL correlation values. |
| Retry | Reattempt the same persisted workflow record after correcting the cause. Retry must preserve identifiers/history and must not mean creating a replacement Patient or Order. |
| ServiceRequest | FHIR resource representing the requested ECG service/examination. It references the intended Patient and carries stable request identifiers. |
| Simulated | Evidence generated by a controlled fixture/simulator rather than the physical AP hop. It is valid only for the explicitly labelled simulated scope. |
| SOP Instance UID | Globally unique identifier of one DICOM SOP Instance. It participates in duplicate detection and retrieval/reconciliation. |
| Scheduled Procedure Step / SPS | DICOM MWL step describing the scheduled work, including station AE and SPS identifier. |
| STOW-RS | DICOMweb store service. It is an HTTP alternative for storing DICOM objects and is not the AP DIMSE C-STORE proof required by this handbook. |
| Synthetic data | Deliberately fictional Patient, Order, result, and artifact data created for testing and not derived from a real person. |
| WADO-RS | DICOMweb retrieve service used to obtain Study/Series/Instance content or retrieval references. Viewer success alone is not complete WADO verification. |
| Watcher | Healthcare Lab background GDT poller that waits for stable files in AP's `outbox/`, claims them through `processing/`, and applies configured disposition. |
