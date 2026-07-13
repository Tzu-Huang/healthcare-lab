# Lab Deployment Runtime

This folder contains the first local runtime scaffold for the Healthcare
Interoperability Lab Console. It targets Docker Desktop on Windows.

## Services

`docker-compose.yml` defines the managed lab surface used by ZAC-8:

- `oie`: Open Integration Engine / Mirth-style HL7 engine.
- `medplum`: FHIR server backed by Postgres and Redis.
- `medplum-app`: Medplum Web UI for the same local Medplum runtime.
- `openemr`: OpenEMR backed by MariaDB.
- `lab-app`: this Flask app, representing GDT Bridge, HL7Tester, and GDT
  Hospital logical services.
- `dcm4chee`: DICOM archive backed by Postgres.

The GDT bridge shared folder is mounted at `/data/gdt-bridge` in both `lab-app`
and `openemr`, so the default app configuration can use one shared folder
contract. By default Docker Compose binds the repo-local `instance/gdt-bridge`
folder from the developer machine into that container path. Set
`GDT_BRIDGE_HOST_PATH` in the repo-root `.env` file to use another computer
folder, then restart `lab-app` and `openemr`.

Inside Healthcare Lab's GDT page, the **Shared Folder** setting controls the
path the Flask app reads and writes. In Docker this should normally remain
`/data/gdt-bridge`; the actual Windows folder is controlled by the Compose
bind mount through `GDT_BRIDGE_HOST_PATH`.

The lab app also points its OpenEMR database settings at `openemr-db` by
default.

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

Supported service names are `all`, `oie`, `medplum`, `medplum-app`, `openemr`,
`gdt-bridge`, `dcm4chee`, `hl7tester`, `gdt-hospital`, and `lab-app`. The
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

| Service | Port |
| --- | --- |
| Lab app UI | `5000` via `LAB_APP_PORT` |
| Lab app HL7 listener | `6671` |
| OIE HTTP | `18080` |
| OIE HTTPS | `10443` |
| OIE inbound MLLP | container network `6671` |
| OIE result listener | host `6661` |
| OIE order listener | host `6600` |
| Medplum FHIR/API | `8103` |
| Medplum Web UI | `3000` |
| OpenEMR | `8088` |
| dcm4chee UI | `8082` |
| dcm4chee DICOM | `11112` |
| dcm4chee HL7 Patient sync | `2575` |

For the full Healthcare Lab -> dcm4chee MWL -> AP -> C-STORE -> Healthcare Lab
verification procedure, see
[`docs/dcm4chee-production-e2e-verification.md`](../docs/dcm4chee-production-e2e-verification.md).
That SOP also covers the simulated AP PDF/DICOM return path used to verify the
Healthcare Lab frontend without a live AP.

Override ports with the matching variables in `docker-compose.yml`, for
example `LAB_APP_PORT`, `OPENEMR_PORT`, or `MEDPLUM_PORT`. The Compose runtime
maps the host `LAB_APP_PORT` to the lab app container port and sets
`LAB_APP_HOST=0.0.0.0` inside the container so Flask accepts the forwarded
connection.

Open the local Medplum Web UI at:

```text
http://127.0.0.1:3000
```

Use that UI to create OAuth client credentials for this local Medplum runtime.
Those credentials are the ones that should be copied into `MEDPLUM_CLIENT_ID`
and `MEDPLUM_CLIENT_SECRET` for `lab-app`.
