# define-managed-hlab-channel-templates

Define complete validated OIE 4.5.2 templates for Healthcare Lab managed ORM and ORU routes.

## Integration handoff

ZAC-48 must receive the AP host from an explicit persisted Settings field before
it composes `HLAB_ORM_TO_AP`; the operator export address is canonical evidence,
not a product default. This change intentionally leaves the ZAC-46 Management
API client, ZAC-49 runtime, ZAC-50 UI, Docker configuration, SQLite schema, and
all live OIE Channels unchanged.
