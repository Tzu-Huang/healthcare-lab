# Lab Deployment Runtime

This folder contains the supported v1.0.0 Docker runtime for the Healthcare
Interoperability Lab Console. It targets `linux/amd64` containers through
Docker Desktop on Windows or an equivalent trusted Linux Docker host.

## Release Quick Start

Download and extract the GitHub Release source archive so the tracked Compose
and environment-template files are available. No host Python installation and
no application source mount are required.

```powershell
.\deploy\lab.ps1 start
.\deploy\lab.ps1 status
Invoke-WebRequest http://127.0.0.1:5000/ -UseBasicParsing
```

No `.env`, host-folder preparation, or YAML edit is required for the normal
local start. The wrapper creates the bounded default GDT bridge root and Compose
uses pinned images, local ports, and persistent storage defaults. Open the
Dashboard; an incomplete setup notice leads to the authoritative Settings
section for application connections and credentials.

The release image is public, so pulling does not require a GitHub token. Copy
`.env.example` to `.env` only for an Advanced deployment override such as an
immutable image, host port, bind path, or service database hardening value. See
[the container release guide](../docs/container-release.md) for tags,
persistence, backup, upgrade, and rollback.

> **Security boundary:** `lab-app` mounts `/var/run/docker.sock` so its
> Dashboard can inspect and control Compose services. Access to that socket is
> effectively host Docker administration. Run this stack only on a trusted
> local machine or internal lab; do not expose it directly to the public
> Internet or use production patient data. v1.0.0 does not claim ARM,
> multi-replica, regulated production, built-in TLS, or application
> authentication support.

## Services

`docker-compose.yml` defines the managed lab surface used by ZAC-8:

- `oie`: Open Integration Engine / Mirth-style HL7 engine.
- `medplum`: FHIR server backed by Postgres and Redis.
- `medplum-app`: Medplum Web UI for the same local Medplum runtime.
- `lab-app`: this Flask app, representing GDT Bridge, HL7Tester, and GDT
  Hospital logical services.
- `dcm4chee`: DICOM archive backed by Postgres.

The GDT bridge shared folder is mounted at `/data/gdt-bridge` in `lab-app`.
By default Docker Compose binds the repo-local `instance/gdt-bridge` folder.
The wrapper creates that root before start. Set `GDT_BRIDGE_HOST_PATH` in an
optional `.env` to use another dedicated host folder; the wrapper resolves and
creates only that exact safe path, rejecting filesystem and repository roots.

Inside Healthcare Lab's GDT page, the **Shared Folder** setting controls the
path the Flask app reads and writes. In Docker this should normally remain
`/data/gdt-bridge`; the actual Windows folder is controlled by the Compose
bind mount through `GDT_BRIDGE_HOST_PATH`. The application provisions and
validates its supported bridge subdirectory contract. Orders are written to
`inbox/`, and returned device/AP data is read from `outbox/`.

OpenEMR and MariaDB are not part of the default runtime. An external OpenEMR
procedure-order source can still be configured with the optional `OPENEMR_DB_*`
settings in the repo-root `.env` file.

## Medplum Auth Runtime

Configure Healthcare Lab's Medplum FHIR URL, browser URL, OAuth client ID,
write-only client secret, scope, token URL, and timeouts in **Settings →
Medplum**. Save-and-test reports metadata, OAuth, and authenticated-read stages
separately. The persisted typed profile is authoritative after restart and
container recreation; public APIs and diagnostics expose only whether the
secret is configured.

For an existing installation only, legacy `MEDPLUM_CLIENT_*`, scope, token URL,
and timeout values in a local `.env` remain a supported one-time bootstrap
source. Compose passes that fixed allowlist to `lab-app`; it seeds only a
missing profile and never overwrites a profile already saved in Settings.

The local Medplum Web UI sends a reCAPTCHA site key during account
registration. `docker-compose.yml` sets matching server and app defaults so
the local registration flow is not blocked by a site-key mismatch. The
`MEDPLUM_RECAPTCHA_SECRET_KEY` default is blank for local lab use, so Medplum
does not verify the Google token. Set both reCAPTCHA values explicitly before
using this runtime outside a local developer lab.

The wrapper passes the repo-root `.env` explicitly only when it exists. Its
`restart` action recreates containers so Advanced deployment changes load into
the new process.

To rotate the client secret:

1. Open **Settings → Medplum**.
2. Enter the non-blank replacement secret and save.
3. Run Save-and-test or the Lab Console Medplum smoke check.
4. Confirm token acquisition separately from any remaining resource failure.

## Troubleshooting Medplum Sync

If Patient, Order, or FHIR workflow sync fails with:

```text
Medplum request failed: [Errno 111] Connection refused
```

first check **Settings → Medplum**. The typed profile is the canonical owner;
for the Compose runtime its internal FHIR URL should use
`http://medplum:8103/fhir/R4`. A URL such as
`http://127.0.0.1:8103/fhir/R4` points back to the `lab-app` container.

The expected Medplum server values are:

```text
host    = medplum
baseUrl = http://medplum:8103/fhir/R4
```

Optionally verify container-to-container reachability before retrying sync:

```powershell
docker compose -f deploy\docker-compose.yml exec lab-app python -c "import urllib.request; print(urllib.request.urlopen('http://medplum:8103/fhir/R4/metadata').status)"
```

The Lab Server inventory remains a compatibility presentation and operation
surface; it is not a second writable owner for the application connection.

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
- The supported application platform is `linux/amd64`.
- Docker Compose is the supported end-user startup path; host Python startup is
  for development only.
- The OIE runtime uses `nextgenhealthcare/connect:4.5.2` by default, matching
  the Open Integration Engine / Mirth-style naming used elsewhere in this repo.
- Release defaults are pinned by digest. Image names and ports remain
  intentionally overridable through environment variables, but overrides are
  outside the verified v1.0.0 matrix.
- The runtime is for local lab data only. Do not mount production patient data.

## Default Ports

Docker service names are resolvable only inside the `lab` network. Managed
Channels therefore use service endpoints such as `lab-app:6665`; a host or AP
outside Docker uses the separately published host port. Changing a published
port does not change the container endpoint.

Keep the dcm4chee DIMSE and HL7 hosts set to `dcm4chee` and its DICOMweb URLs
on `http://dcm4chee:8080` for Compose. Inside lab-app, `127.0.0.1` refers to
lab-app itself. Only the browser-facing `DCM4CHEE_WEB_UI_URL` uses the
published host port by default.

| Flow / service | Docker-network endpoint | Host publication |
| --- | --- | --- |
| Lab app UI | `lab-app:5000` | `LAB_APP_PORT` (default `5000`) |
| HLAB order to OIE | `oie:6600` | `OIE_ORDER_INGRESS_HOST_PORT` (default `6600`) |
| AP result to OIE | `oie:6661` | `OIE_AP_RESULT_INGRESS_HOST_PORT` (default `6661`) |
| OIE result to HLAB | `lab-app:6665` via `HLAB_RESULT_LISTENER_PORT` | none by default |
| OIE Management HTTP | `oie:8080` | `OIE_HTTP_PORT` (default `8080`) |
| OIE Management HTTPS | `oie:8443` | `OIE_HTTPS_PORT` (default `8443`) |
| Medplum FHIR/API | `medplum:8103` | `MEDPLUM_PORT` (default `8103`) |
| Medplum Web UI | `medplum-app:3000` | `MEDPLUM_APP_PORT` (default `3000`) |
| dcm4chee UI | `dcm4chee:8080` | `DCM4CHEE_HTTP_PORT` (default `8082`) |
| dcm4chee DICOM | `dcm4chee:11112` | `DCM4CHEE_DICOM_PORT` (default `11112`) |
| dcm4chee HL7 Patient sync | `dcm4chee:2575` | `DCM4CHEE_HL7_HOST_PORT` (default `2575`) |

## OIE Managed Channel Startup Bootstrap

The single-worker `lab-app` runtime starts one background bootstrap run before
it serves the first browser request. The default mode, `create-missing`, waits
up to 120 seconds for the authenticated OIE 4.5.2 Management API, retrying
every 2 seconds. Once OIE is ready it evaluates the two fixed routes separately:

Fresh profiles target the OIE Client API base at `https://oie:8443` using the
image's `admin` / `admin` local-lab credentials and local self-signed TLS mode.
OIE 4.5.2 does not expose the Client API on its HTTP port.

| Managed Channel | Route |
| --- | --- |
| `HLAB_ORM_TO_AP` | `OIE:6600 -> hl7tester:6671` |
| `HLAB_ORU_TO_HLAB` | `OIE:6661 -> lab-app:6665` |

Bootstrap also recovers identity when the `lab-app-instance` mapping state and
OIE appdata have different retention histories:

| lab-app mapping | OIE Channel | Startup result |
| --- | --- | --- |
| retained | retained | No mapping or OIE mutation |
| retained | missing after OIE appdata reset | Recreate, bind, deploy, and verify only the missing Channel |
| empty after lab-app state reset | retained | Rebind exactly one valid owned Channel without changing its deployment state |
| empty | missing | Create, bind, deploy, and verify a new Channel |

Recovery requires one exact Healthcare Lab ownership marker and logical type,
a parseable owned payload, the expected listener route, and no duplicate,
same-name external, or listener-port claimant. Channel name alone is never
ownership evidence. Ambiguous, malformed, stale, or conflicting evidence is a
bounded no-mutation outcome. A recovered stopped or undeployed Channel remains
stopped or undeployed; bootstrap deploys only a Channel it created during that
run. Repeated restarts are idempotent, and a blocker for one logical type does
not broaden or prevent safe reconciliation of the other.

Configure the bounded startup behavior in `.env`:

```text
OIE_BOOTSTRAP_MODE=create-missing
OIE_BOOTSTRAP_TIMEOUT_SECONDS=120
OIE_BOOTSTRAP_RETRY_INTERVAL_SECONDS=2
```

Set `OIE_BOOTSTRAP_MODE=off` and recreate `lab-app` to disable readiness checks,
identity recovery, and automatic creation. This is also the rollback switch;
disabling bootstrap does not clear recovered mappings or delete, deploy, or
undeploy Channels. Bootstrap timeout or failure never makes the lab-app HTTP
service unhealthy. Inspect the Settings managed-Channel inventory and lifecycle
audit history for bounded `startup-bootstrap` evidence. For blocked recovery,
preserve both volumes, resolve duplicate markers, malformed payloads, external
name/port ownership, or stale identity explicitly, then restart `lab-app` for a
fresh bounded attempt. Never rename an external Channel as a recovery shortcut.

The supported container uses one Gunicorn worker. Multiple workers or replicas
require leader election and are outside this bootstrap contract.

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
Save those credentials in **Settings → Medplum**. The client secret is
write-only and is not copied into Compose or browser storage.
