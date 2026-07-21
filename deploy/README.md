# Lab Deployment Runtime

This folder contains the first local runtime scaffold for the Healthcare
Interoperability Lab Console. It targets Docker Desktop on Windows.

## Services

`docker-compose.yml` defines the managed lab surface used by ZAC-8:

- `oie`: Open Integration Engine / Mirth-style HL7 engine.
- `medplum`: FHIR server backed by Postgres and Redis.
- `medplum-app`: Medplum Web UI for the same local Medplum runtime.
- `lab-app`: this Flask app, representing GDT Bridge, HL7Tester, and GDT
  Hospital logical services.
- `dcm4chee`: DICOM archive backed by Postgres.

The GDT bridge shared folder is mounted at `/data/gdt-bridge` in `lab-app`.
By default Docker Compose binds the repo-local `instance/gdt-bridge`
folder from the developer machine into that container path. Set
`GDT_BRIDGE_HOST_PATH` in the repo-root `.env` file to use another computer
folder, then restart `lab-app`.

Inside Healthcare Lab's GDT page, the **Shared Folder** setting controls the
path the Flask app reads and writes. In Docker this should normally remain
`/data/gdt-bridge`; the actual Windows folder is controlled by the Compose
bind mount through `GDT_BRIDGE_HOST_PATH`. The app does not create bridge
folders: provision them yourself. Orders are written to `inbox/`, and returned
device/AP data is read from `outbox/`.

OpenEMR and MariaDB are not part of the default runtime. An external OpenEMR
procedure-order source can still be configured with the optional `OPENEMR_DB_*`
settings in the repo-root `.env` file.

## Medplum Auth Runtime

`lab-app` reads Medplum OAuth client credentials from `.env` or the shell
environment through `docker-compose.yml`:

```text
MEDPLUM_CLIENT_ID=
MEDPLUM_CLIENT_SECRET=
MEDPLUM_SCOPE=
MEDPLUM_TOKEN_URL=
MEDPLUM_AUTH_GRACE_SECONDS=300
MEDPLUM_APP_BASE_URL=http://127.0.0.1:3000/
MEDPLUM_ALLOWED_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
MEDPLUM_RECAPTCHA_SITE_KEY=6LfHdsYdAAAAAC0uLnnRrDrhcXnziiUwKd8VtLNq
MEDPLUM_RECAPTCHA_SECRET_KEY=
```

Set `MEDPLUM_CLIENT_ID` and `MEDPLUM_CLIENT_SECRET` to a Medplum client that is
allowed to use OAuth client credentials for the target FHIR environment. Leave
`MEDPLUM_TOKEN_URL` blank unless the deployment uses a non-standard token
endpoint; the app derives `/oauth2/token` from the FHIR base URL by default.
Keep the real client secret in `.env` or the operator environment, not in the
tracked Compose file.

The local Medplum Web UI sends a reCAPTCHA site key during account
registration. `docker-compose.yml` sets matching server and app defaults so
the local registration flow is not blocked by a site-key mismatch. The
`MEDPLUM_RECAPTCHA_SECRET_KEY` default is blank for local lab use, so Medplum
does not verify the Google token. Set both reCAPTCHA values explicitly before
using this runtime outside a local developer lab.

The `deploy/lab.ps1` wrapper passes the repo-root `.env` file to Docker Compose
explicitly, even though the Compose file lives under `deploy/`. Its `restart`
action recreates containers so environment-variable changes are loaded into the
new process.

To rotate the client secret:

1. Update `MEDPLUM_CLIENT_SECRET` in `.env`.
2. Restart only the app container:

   ```powershell
   .\deploy\lab.ps1 restart lab-app
   ```

3. Run the Lab Console Medplum smoke check and confirm the `oauth_token` step
   can acquire a token:

   ```powershell
   Invoke-RestMethod -Method Post http://127.0.0.1:5000/api/lab/servers/2/smoke
   ```

4. Confirm any remaining `ServiceRequest` failure is reported separately from
   token acquisition.

## Troubleshooting Medplum Sync

If Patient, Order, or FHIR workflow sync fails with:

```text
Medplum request failed: [Errno 111] Connection refused
```

first check the Lab Console's stored Medplum server URL. The sync path reads
the Medplum `baseUrl` from the Lab Server inventory, not from
`MEDPLUM_PUBLIC_BASE_URL` in `.env`. When `lab-app` runs in Docker, a stored
URL such as `http://127.0.0.1:8103/fhir/R4` points back to the `lab-app`
container itself, not to the Medplum container.

Confirm the stored value:

```powershell
(Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/lab/servers").items | Where-Object {$_.name -eq "Medplum"} | Select-Object name,host,baseUrl
```

For the Docker Compose runtime, update Medplum to use the Docker service name:

```powershell
Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:5000/api/lab/servers/2" -ContentType "application/json" -Body '{"name":"Medplum","serverType":"FHIR Server","description":"FHIR R4 API server","host":"medplum","port":8103,"baseUrl":"http://medplum:8103/fhir/R4","protocol":"FHIR","enabled":true}'
```

The expected Medplum server values are:

```text
host    = medplum
baseUrl = http://medplum:8103/fhir/R4
```

Optionally verify container-to-container reachability before retrying sync:

```powershell
docker-compose --env-file .env -f deploy\docker-compose.yml exec lab-app python -c "import urllib.request; print(urllib.request.urlopen('http://medplum:8103/fhir/R4/metadata').status)"
```

The smoke check can still report Medplum as healthy while sync fails if the
stored Lab Server `baseUrl` is wrong. Docker-backed smoke checks use the
Compose service URL internally, while sync intentionally uses the persisted Lab
Server configuration.

## PowerShell CLI

Run commands from `repo`:

```powershell
.\deploy\lab.ps1 status
.\deploy\lab.ps1 start medplum
.\deploy\lab.ps1 start medplum-app
.\deploy\lab.ps1 restart lab-app
.\deploy\lab.ps1 smoke all
.\deploy\lab.ps1 logs oie -Lines 200
.\deploy\lab.ps1 stop all
```

Supported service names are `all`, `oie`, `medplum`, `medplum-app`,
`medplum-postgres`, `medplum-redis`, `gdt-bridge`, `dcm4chee`, `dcm4chee-db`,
`ldap`, `hl7tester`, `gdt-hospital`, and `lab-app`. The
logical services `gdt-bridge`, `hl7tester`, and `gdt-hospital` map to the
`lab-app` container. The `medplum` service name starts or recreates both the
Medplum API server and Web UI companion.

## Runtime Assumptions

- Docker Desktop is installed and running in Linux container mode.
- `docker compose` is available on `PATH`.
- The OIE runtime uses `nextgenhealthcare/connect:4.5.2` by default, matching
  the Open Integration Engine / Mirth-style naming used elsewhere in this repo.
- Image names and ports are intentionally overridable through environment
  variables before running Compose.
- The runtime is for local lab data only. Do not mount production patient data.

## Default Ports

Docker service names are resolvable only inside the `lab` network. Managed
Channels therefore use service endpoints such as `lab-app:6665`; a host or AP
outside Docker uses the separately published host port. Changing a published
port does not change the container endpoint.

| Flow / service | Docker-network endpoint | Host publication |
| --- | --- | --- |
| Lab app UI | `lab-app:5000` | `LAB_APP_PORT` (default `5000`) |
| HLAB order to OIE | `oie:6600` | `OIE_ORDER_INGRESS_HOST_PORT` (default `6600`) |
| AP result to OIE | `oie:6661` | `OIE_AP_RESULT_INGRESS_HOST_PORT` (default `6661`) |
| OIE result to HLAB | `lab-app:6665` via `HLAB_RESULT_LISTENER_PORT` | none by default |
| OIE Management HTTP | `oie:8080` | `OIE_HTTP_PORT` (default `18080`) |
| OIE Management HTTPS | `oie:8443` | `OIE_HTTPS_PORT` (default `10443`) |
| Medplum FHIR/API | `medplum:8103` | `MEDPLUM_PORT` (default `8103`) |
| Medplum Web UI | `medplum-app:3000` | `MEDPLUM_APP_PORT` (default `3000`) |
| dcm4chee UI | `dcm4chee:8080` | `DCM4CHEE_HTTP_PORT` (default `8082`) |
| dcm4chee DICOM | `dcm4chee:11112` | `DCM4CHEE_DICOM_PORT` (default `11112`) |
| dcm4chee HL7 Patient sync | `dcm4chee:2575` | `DCM4CHEE_HL7_PORT` (default `2575`) |

For the full Healthcare Lab -> dcm4chee MWL -> AP -> C-STORE -> Healthcare Lab
verification procedure, see
[`docs/dcm4chee-production-e2e-verification.md`](../docs/dcm4chee-production-e2e-verification.md).
That SOP also covers the simulated AP PDF/DICOM return path used to verify the
Healthcare Lab frontend without a live AP.

Override ports with the matching variables in `docker-compose.yml`, for
example `LAB_APP_PORT`, `OIE_AP_RESULT_INGRESS_HOST_PORT`, or `MEDPLUM_PORT`.
The Compose runtime
maps the host `LAB_APP_PORT` to the lab app container port and sets
`LAB_APP_HOST=0.0.0.0` inside the container so Flask accepts the forwarded
connection.

### OIE/HLAB port migration

`OIE_MLLP_RESULT_PORT` previously had two conflicting meanings: the OIE `6661`
host publication and the HLAB `6665` listener. It is deprecated. For one
migration window, Compose accepts `OIE_MLLP_RESULT_HOST` and
`OIE_MLLP_RESULT_PORT` only as fallbacks for the HLAB listener when the new
`HLAB_RESULT_LISTENER_HOST` and `HLAB_RESULT_LISTENER_PORT` values are absent.
The legacy values never configure an OIE host publication. Migrate `.env` to:

```text
HLAB_RESULT_LISTENER_HOST=0.0.0.0
HLAB_RESULT_LISTENER_PORT=6665
OIE_AP_RESULT_INGRESS_HOST_PORT=6661
OIE_ORDER_INGRESS_HOST_PORT=6600
```

The AP connects to the Docker host's published AP-result port. The managed ORU
Channel continues to send to `lab-app:6665`, never to `127.0.0.1:6665` (which
would refer to the OIE container itself).

### Applying endpoint changes

Use the action matching the layer that changed:

| Change | Required action |
| --- | --- |
| Managed Channel destination, queue, retry, timeout, MLLP, or ACK validation | Preview, Apply, and redeploy the Channel |
| `HLAB_RESULT_LISTENER_HOST` or `HLAB_RESULT_LISTENER_PORT` | Recreate/restart `lab-app`, then use listener Retry if its runtime status is degraded |
| `OIE_AP_RESULT_INGRESS_HOST_PORT`, `OIE_ORDER_INGRESS_HOST_PORT`, `OIE_HTTP_PORT`, or `OIE_HTTPS_PORT` | Recreate `oie`; Channel redeploy alone cannot change a Compose publication |
| Temporary listener failure with unchanged settings | Restore the dependency and use listener Retry/restart; do not recreate OIE or discard its queue |

For Compose environment or port changes, `restart` in `deploy/lab.ps1` performs
container recreation. After changing the ORU endpoint or durable-delivery
settings, apply the managed `HLAB_ORU_TO_HLAB` definition as well. Its required
contract queues connection failures and ACK response timeouts, retries every
10 seconds indefinitely, retains 1000 messages, uses 5000 ms send/response
timeouts, and validates the returned HL7 ACK before marking delivery complete.

Open the local Medplum Web UI at:

```text
http://127.0.0.1:3000
```

Use that UI to create OAuth client credentials for this local Medplum runtime.
Those credentials are the ones that should be copied into `MEDPLUM_CLIENT_ID`
and `MEDPLUM_CLIENT_SECRET` for `lab-app`.
