## Context

The release Compose file already supplies pinned image and local topology fallbacks, but `lab-app.env_file` names `../.env` unconditionally. Docker Compose therefore rejects the supported deployment when the file is absent, even though `deploy/lab.ps1` conditionally adds `--env-file` only when it exists. Documentation reinforces the obsolete requirement to copy `.env.example`, which currently mixes deployment controls with application-owned Medplum, GDT, dcm4chee, OIE, and AP values.

ZAC-71 and ZAC-73 through ZAC-76 established typed persisted settings, create-only legacy bootstrap, secret-safe projections, integration readiness, and guided Settings sections. ZAC-77 connects that foundation to the release entry point. Existing installations must retain their environment-seeded values, while clean installations must reach the UI using safe defaults and receive an explicit setup handoff.

The deployment is a trusted local/internal lab. The web application may use its existing bounded Docker operation adapter but must not gain authority to rewrite Compose, persist deployment overrides, or execute arbitrary commands.

## Goals / Non-Goals

**Goals:**

- Make direct Compose and wrapper commands work without a repository-root `.env`.
- Preserve explicit advanced image, port, bind-mount, database/security, and external-bootstrap overrides.
- Preserve create-only migration of eligible legacy runtime values and persisted-profile precedence.
- Provision supported mutable directories without YAML editing.
- Surface incomplete required readiness on Dashboard and navigate to the owning Settings section.
- Keep all generated output and diagnostics secret-safe.
- Provide executable contracts for clean install, upgrade, recreate, and override paths.

**Non-Goals:**

- Public Internet deployment, production authentication, or a production secrets manager.
- Automatic creation of external Medplum OAuth clients or other external-system identities.
- Moving deployment-only settings into application persistence.
- Letting the web application edit Compose or invoke arbitrary Docker commands.
- Automatically restarting or recreating services when application Settings change.

## Decisions

### Remove the mandatory Compose env-file declaration

`deploy/docker-compose.yml` will rely on `${KEY:-fallback}` interpolation and will not declare the repository-root `.env` as a required service `env_file`. Docker Compose will continue to load a conventional root `.env` automatically for interpolation when present, and the wrapper will explicitly pass it when present so invocation from any working directory remains deterministic.

Alternative considered: keep `env_file` with a Compose `required: false` attribute. Rejected because support varies by Compose version and it would inject the entire mixed file into `lab-app`, preserving the wrong ownership boundary.

### Keep deployment overrides in Compose and application settings in typed persistence

`.env.example` will become an advanced deployment template. It will retain image selection, host publications, bind-mount selection, service database credentials/security hardening, and explicitly documented one-time compatibility/bootstrap inputs. Normal application endpoints and credentials will be configured through Settings and omitted from Quick Start.

The closed configuration ownership registry remains authoritative. Any retained environment key must have exactly one deployment, bootstrap, secret, or derived owner and explicit activation semantics.

Alternative considered: remove all legacy runtime keys immediately. Rejected because existing installations require a non-lossy migration window.

### Preserve create-only bootstrap precedence

Startup composition will continue to present eligible environment values to typed profile bootstrap. A missing profile may be created from those values and safe defaults; an existing profile is never merged with changed environment input. Bootstrap errors remain bounded and value-free. Tests will cover an old `.env` migrating once, a later environment change not overriding the profile, and persistence after container recreation.

Alternative considered: treat environment as a permanent override above persisted Settings. Rejected because UI saves would become non-authoritative and restart behavior would be surprising.

### Provision directories in the supported wrapper and retain application validation

The wrapper will resolve and create only the known repository-local instance/GDT directories needed by the default bind-mount contract before `start` or whole-stack `restart`. An explicit advanced `GDT_BRIDGE_HOST_PATH` remains operator-owned; the wrapper may validate or create that exact configured path using bounded path rules but will never edit YAML. The application retains its explicit GDT directory validation/provision action for application-level subdirectories.

Alternative considered: replace the GDT bind mount with only a named volume. Rejected because shared-folder exchange with external GDT software requires a host-visible path.

### Add a Dashboard notice, not an unconditional redirect

Dashboard initialization will request the existing `/api/settings/readiness` projection. If required setup is incomplete, it will display a prominent, accessible notice whose action navigates to Settings and activates the `nextAction.sectionId`. The Dashboard remains usable and readiness failure degrades to a bounded unavailable message rather than blocking startup. No wizard cursor or sensitive values are stored in browser storage.

Alternative considered: automatically redirect every incomplete instance to Settings. Rejected because it hides service health and can trap operators when a readiness provider is temporarily degraded.

### Test commands as contracts without exposing values

Compose tests will render configuration with a deliberately absent env file and with bounded override fixtures. Wrapper tests will use a fake Docker executable or command adapter to inspect argument arrays and directory effects without starting services. Output assertions will use canary secrets and require their absence from stdout, stderr, diagnostics, and generated evidence.

## Risks / Trade-offs

- [Risk] Compose's implicit `.env` lookup changes with the caller's working directory. → The wrapper always uses absolute Compose and optional env-file paths; direct commands are documented from repository root.
- [Risk] Reducing `.env.example` accidentally removes a migration input still needed by existing installations. → Drive the reduction from the ownership registry and add a legacy migration fixture before removing documentation.
- [Risk] Creating an operator-supplied bind path could target an unsafe location. → Resolve the exact path, reject empty/root/broad targets, and limit recursive creation to the configured directory without deletion or movement.
- [Risk] A Dashboard readiness call delays or destabilizes initial rendering. → Reuse the bounded readiness endpoint asynchronously and keep Dashboard activation independent of its success.
- [Risk] Local default database passwords are mistaken for production security. → Label them local-only and place hardening overrides in Advanced deployment documentation.

## Migration Plan

1. Add failing deployment and frontend contract tests for no-`.env`, wrapper arguments, legacy bootstrap, recreate persistence, readiness notice, and canary redaction.
2. Remove mandatory service `env_file`, normalize Compose fallbacks, and provision the default directory contract in the wrapper.
3. Reduce and reorganize `.env.example` while keeping supported legacy bootstrap inputs and configuration ownership synchronized.
4. Add the Dashboard readiness notice and section-targeted Settings navigation.
5. Update root and deployment Quick Start, upgrade, precedence, advanced override, backup, and rollback documentation.
6. Validate focused tests, the complete regression suite, rendered Compose variants, strict OpenSpec validation, and diff hygiene.

Rollback may restore the prior Compose and UI behavior without rolling back the database. Typed profiles and migrated settings remain forward-compatible; operators can temporarily restore an existing `.env` and prior release assets while retaining named volumes and the instance database.

## Open Questions

- Whether explicit advanced GDT paths should be created automatically or only validated with an actionable error should be settled while specifying wrapper path-safety tests.
- The final compatibility window for legacy application environment keys should be documented with a future removal issue rather than silently inferred.
