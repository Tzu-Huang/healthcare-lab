# Configuration Ownership Matrix

Healthcare Lab assigns every supported configuration key to exactly one owner.
The executable registry in `backend/configuration_ownership.py` is the
machine-checked source of truth; this document explains how to interpret it.

| Category | Owner and examples | Persistence/bootstrap | Activation |
|---|---|---|---|
| `deployment-only` | Docker Compose owns images, networks, volumes, bind mounts, host-published ports, and container database identities. Examples: `LAB_APP_IMAGE`, `GDT_BRIDGE_HOST_PATH`, `OIE_HTTP_PORT`, `DCM4CHEE_DICOM_PORT`, `MEDPLUM_POSTGRES_DB`. | Never copied into application settings. | Recreate the affected container. |
| `runtime-persisted` | Integration-specific typed profiles own behavioral endpoints, protocol identities, timeouts, enabled state, and runtime options. Examples: `MEDPLUM_CLIENT_ID`, `GDT_BRIDGE_FILENAME_PROFILE`, `DCM4CHEE_DIMSE_HOST`, `OPENEMR_DB_HOST`. | Eligible environment values seed a missing profile once; persisted values then remain authoritative. | The matrix registry identifies next-read, watcher/listener retry, or restart behavior. |
| `secret` | Either Compose service configuration or the matching typed integration profile owns passwords, client secrets, and private-key material. | Application-owned secrets seed only a missing profile and are structurally separated from public profile data. Deployment secrets remain deployment-only. | Next effective read or container recreation, according to owner. |
| `derived/default` | A supported local topology or compatibility projection supplies the value. Examples: `OIE_MLLP_RESULT_HOST`, `ECG_FILE_BASE_URL`, `DCM4CHEE_LDAP_URL`. | Not an independently editable persisted value unless a later typed profile explicitly replaces the derivation. | Recomputed at the documented runtime boundary. |

## Complete key matrix

The following table is generated conceptually from the closed registry. Each
line lists keys sharing the exact same owner, bootstrap, and activation policy.

| Keys | Category | Owner | Bootstrap | Activation |
|---|---|---|---|---|
| `DCM4CHEE_DB_IMAGE`, `DCM4CHEE_DB_NAME`, `DCM4CHEE_DB_USER`, `DCM4CHEE_DICOM_PORT`, `DCM4CHEE_HTTP_PORT`, `DCM4CHEE_IMAGE`, `DCM4CHEE_LDAP_IMAGE`, `DCM4CHEE_STORAGE_DIR`, `GDT_BRIDGE_HOST_PATH`, `LAB_APP_IMAGE`, `LAB_APP_PORT`, `MEDPLUM_ALLOWED_ORIGINS`, `MEDPLUM_APP_BASE_URL`, `MEDPLUM_APP_IMAGE`, `MEDPLUM_APP_PORT`, `MEDPLUM_BASE_URL`, `MEDPLUM_IMAGE`, `MEDPLUM_PORT`, `MEDPLUM_POSTGRES_DB`, `MEDPLUM_POSTGRES_IMAGE`, `MEDPLUM_POSTGRES_USER`, `MEDPLUM_PUBLIC_BASE_URL`, `MEDPLUM_REDIS_IMAGE`, `OIE_DATABASE`, `OIE_HTTPS_PORT`, `OIE_HTTP_PORT`, `OIE_IMAGE`, `OIE_AP_RESULT_INGRESS_HOST_PORT`, `OIE_ORDER_INGRESS_HOST_PORT`, `STORAGE_DIR` | deployment-only | Docker Compose | never | container recreation |
| `DCM4CHEE_DB_PASSWORD`, `DCM4CHEE_LDAP_ROOTPASS`, `MEDPLUM_POSTGRES_PASSWORD`, `MEDPLUM_RECAPTCHA_SECRET_KEY` | secret | Docker Compose service | never | container recreation |
| `MEDPLUM_CLIENT_SECRET`, `OPENEMR_DB_PASSWORD` | secret | typed integration settings | seed missing profile once | next effective read |
| `DCM4CHEE_PRIVATE_KEY_PATH` | secret | typed dcm4chee settings | seed missing profile once | next effective read |
| `MEDPLUM_CLIENT_ID`, `MEDPLUM_SCOPE`, `MEDPLUM_TOKEN_URL`, `MEDPLUM_AUTH_GRACE_SECONDS`, `MEDPLUM_TIMEOUT_SECONDS`, `MEDPLUM_WEB_UI_URL` | runtime-persisted | typed Medplum settings | seed missing profile once | next effective read |
| `OPENEMR_DB_HOST`, `OPENEMR_DB_NAME`, `OPENEMR_DB_PORT`, `OPENEMR_DB_USER`, `OPENEMR_GDT_PROCEDURE_CODES` | runtime-persisted | typed OpenEMR settings | seed missing profile once | next effective read |
| `GDT_BRIDGE_FILENAME_PROFILE`, `GDT_BRIDGE_IMPORT_SUCCESS_MODE`, `GDT_BRIDGE_RECEIVER_ID`, `GDT_BRIDGE_SENDER_ID`, `GDT_BRIDGE_STABLE_SECONDS`, `GDT_BRIDGE_WATCH_POLL_SECONDS` | runtime-persisted | typed GDT settings | seed missing profile once | immediate serialized watcher reload or application restart |
| `DCM4CHEE_AUTH_MODE`, `DCM4CHEE_CALLED_AE_TITLE`, `DCM4CHEE_CALLING_AE_TITLE`, `DCM4CHEE_CERTIFICATE_PATH`, `DCM4CHEE_DEFAULT_SCHEDULED_STATION_AE_TITLE`, `DCM4CHEE_DICOMWEB_BASE_URL`, `DCM4CHEE_DIMSE_HOST`, `DCM4CHEE_DIMSE_PORT`, `DCM4CHEE_DISPLAY_NAME`, `DCM4CHEE_ENVIRONMENT_NAME`, `DCM4CHEE_HL7_HOST`, `DCM4CHEE_HL7_PORT`, `DCM4CHEE_HL7_RECEIVING_APPLICATION`, `DCM4CHEE_HL7_RECEIVING_FACILITY`, `DCM4CHEE_HL7_SENDING_APPLICATION`, `DCM4CHEE_HL7_SENDING_FACILITY`, `DCM4CHEE_MWL_AE_TITLE`, `DCM4CHEE_PATIENT_ASSIGNING_AUTHORITY`, `DCM4CHEE_PROFILE_NAME`, `DCM4CHEE_QIDO_RS_URL`, `DCM4CHEE_STOW_RS_URL`, `DCM4CHEE_TLS_ENABLED`, `DCM4CHEE_TLS_VERIFY`, `DCM4CHEE_TOKEN_URL`, `DCM4CHEE_UID_ROOT`, `DCM4CHEE_USERNAME`, `DCM4CHEE_VIEWER_STUDY_URL_TEMPLATE`, `DCM4CHEE_WADO_RS_URL`, `DCM4CHEE_WEB_UI_URL` | runtime-persisted | typed dcm4chee settings | seed missing profile once | next effective read |
| `HLAB_RESULT_LISTENER_HOST`, `HLAB_RESULT_LISTENER_PORT`, `OIE_MLLP_ORDER_HOST`, `OIE_MLLP_ORDER_PORT` | runtime-persisted | typed OIE settings | existing OIE profile | listener retry or app restart |
| `OIE_BOOTSTRAP_MODE`, `OIE_BOOTSTRAP_RETRY_INTERVAL_SECONDS`, `OIE_BOOTSTRAP_TIMEOUT_SECONDS` | derived/default | lab-app startup policy | process environment/default | app restart |
| `OIE_MLLP_RESULT_HOST`, `OIE_MLLP_RESULT_PORT` | derived/default | HLAB listener compatibility projection | derived from `HLAB_RESULT_LISTENER_*` | app restart |
| `ECG_FILE_BASE_URL` | derived/default | AP-facing result projection | safe local default | next effective read |
| `MEDPLUM_RECAPTCHA_SITE_KEY` | derived/default | Medplum deployment | Compose safe local default | container recreation |
| `DCM4CHEE_LDAP_BASE_DN`, `DCM4CHEE_LDAP_URL` | derived/default | dcm4chee deployment topology | Compose topology default | container recreation |

Persisted values are authoritative after bootstrap. A process restart never
merges changed environment values into an existing typed profile. Public APIs,
logs, exceptions, diagnostics, and audits expose only whether a secret is
configured; SQLite file permissions are the current at-rest protection.

The GDT profile also owns its enabled state and application-visible path.
Supported Docker deployments fix that application path at `/data/gdt-bridge`;
the host bind mount remains the deployment-only `GDT_BRIDGE_HOST_PATH`.

## Typed settings extension contract

Later Settings issues must register a closed integration profile with explicit
field and secret allowlists, a complete validator, public and effective
projections, and bootstrap mapping. Runtime consumers receive the effective
reader through application composition; they must not read migrated values from
`os.environ`, Flask request state, Lab Server inventory, or raw settings SQL.

`PUT /api/settings/profiles/<profile-type>` accepts complete typed `fields` and
optional write-only `secrets`. Omitted or blank secret replacements preserve the
stored value. Removal uses the distinct
`DELETE /api/settings/profiles/<profile-type>/secrets/<field>` operation.
Responses expose only `{ "configured": true|false }` for secrets. Validation
errors contain bounded codes and field paths but never rejected values.

The current SQLite deployment does not provide application-managed encryption
at rest. Secrets are kept in a structurally separate table and excluded from
all public projections and audits; operators must protect the database file and
its backups with deployment filesystem controls.
