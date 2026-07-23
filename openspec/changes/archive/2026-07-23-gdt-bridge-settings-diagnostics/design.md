## Context

Healthcare Lab already has GDT order export, result import, filename filtering, post-success handling, and a background inbound watcher. Their configuration is not yet owned by the shared typed-settings boundary or exposed through the modular Settings workspace. The supported Docker topology mounts a host directory into the application at `/data/gdt-bridge`; operators need to understand both sides of that boundary without granting the application authority to rewrite deployment files.

This change crosses persistence, API, application composition, watcher lifecycle, filesystem access, readiness aggregation, and frontend modules. Filesystem diagnostics must be useful while never exposing message contents or filenames that could carry PHI.

## Goals / Non-Goals

**Goals:**

- Establish one persisted, validated GDT Bridge runtime profile and migrate runtime consumers to its effective projection.
- Give operators a GDT-owned Settings form with clear application-path and deployment-path semantics.
- Diagnose path, directory, permission, probe, and watcher states with bounded PHI-safe output.
- Apply safe changes immediately and return exact `restart-required` guidance when lifecycle constraints prevent reload.
- Preserve deterministic startup and existing GDT order/result behavior.

**Non-Goals:**

- Editing Compose, changing bind mounts, or recreating containers.
- Browsing or displaying arbitrary bridge files, filenames, or message contents.
- Provisioning paths outside the documented bridge directory tree.
- Redesigning GDT payload parsing or order/result persistence.

## Decisions

### Use a named typed GDT Bridge profile

Add a registered profile with `enabled`, fixed/effective application path, receiver ID, sender ID, filename profile, import-success mode, poll interval, and stable-file interval. Persist runtime behavior; keep the host bind mount deployment-owned. Seed a missing profile once from eligible legacy environment values and supported local defaults.

This uses the ZAC-71 ownership and audit boundary instead of adding GDT-specific raw SQL or continuing direct environment reads. A generic key/value store was rejected because it would bypass typed validation and ownership.

### Keep the Docker application path fixed

For the supported Docker runtime, the effective application-visible root is `/data/gdt-bridge`. The Settings API may expose a discovered host bind-mount path as read-only deployment metadata, but mutations cannot change it. Discovery failure is represented as unavailable metadata, not as a GDT runtime failure.

Allowing the UI to rewrite Compose was rejected because container recreation and host path ownership belong to deployment tooling.

### Isolate filesystem operations behind a bounded bridge service

The service resolves only documented child directories under the effective bridge root. Provisioning is a separate explicit mutation and creates only those directories. The write probe creates a generated empty diagnostic file in the documented probe location, verifies it, and deletes it in a `finally` path. Responses report check identifiers and bounded states, never enumerated filenames or file content.

Reusing normal import/export files for probing was rejected because it risks mutating operator data and exposing PHI.

### Separate persisted intent from watcher effectiveness

Saving a profile commits first. A lifecycle coordinator then compares the prior effective profile with the new one. If the watcher can safely stop, rebuild its dependencies, and restart in-process, it returns an immediate activation result. If the current hosting mode cannot guarantee a safe transition, it preserves the saved profile and returns `restart-required` with application-restart or container-recreation guidance.

The watcher reads one immutable effective-profile snapshot per scan. Startup constructs the watcher from persisted settings before it begins polling, keeping startup deterministic and avoiding mid-scan configuration changes.

### Register GDT-owned readiness and diagnostics

The GDT module owns its form, API adapter, readiness provider, diagnostic rendering, and styles. Disabled profiles report `disabled`. Enabled profiles combine valid persistence, bounded filesystem checks, and watcher effectiveness into the shared readiness vocabulary.

Putting GDT logic in the Settings shell was rejected because it would violate the module ownership contract created by ZAC-72.

## Risks / Trade-offs

- [Host bind-mount discovery varies by runtime] → Treat it as optional read-only deployment metadata and keep `/data/gdt-bridge` authoritative inside supported Docker.
- [Write probes can leave artifacts after abrupt process termination] → Use unique diagnostic names, empty files, `finally` cleanup, and ignore diagnostic patterns in watcher eligibility.
- [Watcher restart can race with an active scan] → Serialize lifecycle transitions and let an active scan finish or return `restart-required` when quiescence cannot be guaranteed.
- [Persisted settings can differ from the running watcher] → Return activation metadata and readiness `restart-required` until effective state converges.
- [Filesystem exceptions can leak sensitive paths] → Map exceptions to allowlisted codes and directory roles; do not return arbitrary exception strings.

## Migration Plan

1. Register and migrate the GDT Bridge profile schema with safe defaults and one-time legacy environment bootstrap.
2. Add effective-profile composition while retaining compatibility adapters for existing GDT call sites.
3. Move bridge services and watcher construction to the effective profile.
4. Add diagnostics, provisioning, readiness, and Settings APIs.
5. Register the GDT frontend module and tests.
6. Roll back by reverting application code; persisted profile data remains additive and can be ignored by the previous version.

## Open Questions

- Which currently supported host/runtime combinations can reliably expose bind-mount source metadata without Docker-socket access?
- Does every production hosting mode support safe watcher quiescence, or should the first implementation conservatively require application restart for path and filename-profile changes?
