# ZAC-79 fresh-start verification evidence — 2026-07-27

## Tested state

- Branch: `fix/ZAC-79_fix-fresh-start-compose-secrets-and-dcm4chee-tls-defaults`
- Product commit: `9f33c12`
- Local image: `healthcare-lab:zac79-local`
- Image revision label: `9f33c12`
- Docker Engine: `29.5.2`
- Docker Compose: `5.1.3`
- Host: Windows with Docker Desktop
- Credentials and patient data: none

## Isolation

Read-only pre-flight found an existing `interoperability-lab` project, network,
volumes, and application publication on host port `5000`. The verification did
not reuse, stop, restart, or remove any of those resources.

The disposable run used:

- Compose project and network `zac79-noenv-20260727`;
- fresh project-scoped volumes;
- an isolated synthetic GDT directory;
- application port `15079` and distinct alternate ports for every other host
  publication;
- no application integration credential values;
- a local image built from the exact tested product commit.

## Result

Compose rendered and converged without a repository `.env` or optional
application credential environment variables. `lab-app` became healthy and
`GET /api/settings/readiness` returned HTTP 200 with:

- overall `complete: false`;
- next action `configure` for `medplum`;
- Medplum `needs-setup`;
- OIE and dcm4chee `ready`;
- GDT Bridge and AP / External Devices `disabled`;
- Deployment & Diagnostics `ready`.

The public Medplum profile reported `clientSecret.configured: false`. The public
dcm4chee profile reported password, token, and client secret as
`configured: false`, and its local security projection contained
`tlsEnabled: false` and `tlsVerify: false`.

Bounded `lab-app` logs showed only normal Gunicorn startup. No credential,
patient, raw-message, FHIR-body, or arbitrary upstream-response evidence was
retained.

## Cleanup and remaining release boundary

The disposable containers, network, and project-scoped volumes were removed
with the exact project and override files used for startup. Follow-up inspection
confirmed that the disposable network and volumes no longer existed.

This local-image run proves the source and Compose fixes but does not satisfy the
immutable release-image gate. The default release bundle still selects
`ghcr.io/tzu-huang/healthcare-lab:1.0.1`; ZAC-79 remains blocked on publishing
and selecting a new verified semantic-version image before the ZAC-78
fresh-install closure gate can pass.
