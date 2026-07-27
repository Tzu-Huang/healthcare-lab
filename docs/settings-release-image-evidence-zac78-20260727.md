# ZAC-78 v1.1.1 release-image fresh-install evidence (2026-07-27)

## Published image

- GitHub release: `v1.1.1`
- Release target: `54e60d0e69d25c256474d9d0a5c790b1d9b7599e`
- GitHub Actions run: `30242203066`
- Image: `ghcr.io/tzu-huang/healthcare-lab:1.1.1`
- Image revision label:
  `54e60d0e69d25c256474d9d0a5c790b1d9b7599e`
- Platform: `linux/amd64`

The release workflow passed product tests, image build/publication, anonymous
GHCR inspection for all aliases, container health, and the immutable Settings
readiness smoke test.

## Isolation

The local rerun used:

- Compose project and explicit network `zac78-release-111`;
- fresh project-scoped volumes;
- an isolated empty GDT host directory;
- application port `15111` and distinct alternate ports for every other host
  publication;
- no application integration credentials or clinical data.

Read-only pre-flight identified the normal `interoperability-lab` project. The
rerun did not stop, recreate, mount, or modify its container, network, port
5000 publication, or retained volumes.

## Fresh-install result

Compose rendered with `ghcr.io/tzu-huang/healthcare-lab:1.1.1` and converged
without a repository `.env` or optional credential values.

- `lab-app` became healthy on port `15111`.
- `dcm4chee-storage-init` completed with exit code 0.
- The full OIE, Medplum, dcm4chee, and application stack started on isolated
  resources.
- `GET /api/settings/readiness` returned HTTP 200 with `success: true`,
  `complete: false`, and next action `configure` for Medplum.
- Medplum was `needs-setup`.
- OIE and dcm4chee were `ready`.
- GDT Bridge and AP / External Devices were `disabled`.
- Deployment & Diagnostics was `ready`.

The public Medplum profile reported `clientSecret.configured: false`. The
public dcm4chee profile reported password, token, and client secret as
`configured: false`; certificate/private-key references were unconfigured; and
the effective local TLS projection was `tlsEnabled: false` /
`tlsVerify: false`.

## Safety and cleanup

Bounded `lab-app` logs did not contain Authorization bearer headers,
`MEDPLUM_CLIENT_SECRET`, Patient resource bodies, or raw HL7 `MSH` segments.
No screenshots or clinical payloads were retained.

The disposable containers, one-shot container, network, and all project-scoped
volumes were removed. Post-cleanup inspection found no
`zac78-release-111` resources, while `interoperability-lab-lab-app-1`
continued running.
