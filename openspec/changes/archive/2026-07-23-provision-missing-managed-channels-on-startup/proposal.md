## Why

A clean Healthcare Lab deployment starts lab-app and OIE without the two approved managed Channels, so operators must open Settings and provision them manually before ORM and ORU traffic can flow. Startup should safely converge only absent Healthcare Lab-owned Channels while preserving the existing fail-closed treatment of drift, conflicts, and external Channels.

## What Changes

- Seed the desired mappings for `HLAB_ORM_TO_AP` (`OIE:6600 -> AP:6671`) and `HLAB_ORU_TO_HLAB` (`OIE:6661 -> lab-app:6665`) in a fresh OIE Settings profile.
- Add an explicit startup bootstrap mode with `create-missing` as the default and `off` as the opt-out.
- Start one bootstrap worker per lab-app runtime independently of browser requests, while keeping the HTTP application available during OIE readiness delays and failures.
- Wait for the OIE Management API with configurable bounded timeout and retry interval.
- Reuse managed-Channel ownership classification and guarded single-target lifecycle operations to create, rediscover, persist, deploy, and verify only Channels classified as missing.
- Treat unchanged Channels as restart no-ops, create only a missing member of a partial pair, and never update drifted Channels or mutate conflicted/external Channels.
- Record bounded, secret-safe lifecycle evidence with the `startup-bootstrap` actor and add automated coverage for clean, repeated, partial, delayed, timeout, and conflict startup paths.

## Capabilities

### New Capabilities

- `healthcare-lab-oie-startup-bootstrap`: Defines bootstrap configuration, runtime execution, bounded readiness, create-missing convergence, deployment verification, failure isolation, and startup evidence.

### Modified Capabilities

- `healthcare-lab-oie-settings-profile`: A fresh profile now persists desired mapping intent for both canonical managed Channels and bootstrap-safe actor metadata.
- `healthcare-lab-oie-managed-channel-lifecycle`: The existing prohibition on automatic startup mutation is narrowed to permit guarded creation and deployment of missing managed Channels in `create-missing` mode while preserving all ownership and drift protections.

## Impact

The change affects application configuration, repeatable SQLite startup maintenance, OIE lifecycle orchestration and audit actor selection, runtime startup composition, Docker/operational configuration documentation, and focused unit/integration tests. It uses the existing OIE 4.5.2 Management API client and managed-Channel templates; it adds no new external dependency and does not change browser lifecycle APIs.
